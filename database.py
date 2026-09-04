"""
KasbPro · database.py
MySQL schema + connection helpers (PyMySQL driver).

Connection settings come from environment variables (with sensible
local-dev defaults), so the same code runs in development, on a class-
mate's laptop, or on a production server:

    KASBPRO_MYSQL_HOST       (default: localhost)
    KASBPRO_MYSQL_PORT       (default: 3306)
    KASBPRO_MYSQL_USER       (default: root)
    KASBPRO_MYSQL_PASSWORD   (default: '')
    KASBPRO_MYSQL_DB         (default: kasbpro)

Every table maps directly to one of the functional requirements
(FR-01 … FR-07) plus two new ones for Suppliers and Reports.
"""

import os
import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager


# Database configuration from environment variables
DB_HOST     = os.environ.get("KASBPRO_MYSQL_HOST", "localhost")
DB_PORT     = int(os.environ.get("KASBPRO_MYSQL_PORT", "3306"))
DB_USER     = os.environ.get("KASBPRO_MYSQL_USER", "root")
DB_PASSWORD = os.environ.get("KASBPRO_MYSQL_PASSWORD", "")
DB_NAME     = os.environ.get("KASBPRO_MYSQL_DB", "kasbpro")


# SQLite-compatible MySQL wrappers
# They translate placeholders and return dict-like rows.
def _q(sql: str) -> str:
    """Replace `?` placeholders with `%s` but skip `?` inside string literals."""
    if "?" not in sql:
        return sql
    out, in_string, str_ch = [], False, ""
    for ch in sql:
        if in_string:
            out.append(ch)
            if ch == str_ch:
                in_string = False
        else:
            if ch in ("'", '"'):
                in_string, str_ch = True, ch
                out.append(ch)
            elif ch == "?":
                out.append("%s")
            else:
                out.append(ch)
    return "".join(out)


class _Cursor:
    """Quack-alike for sqlite3.Cursor."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        self._raw.execute(_q(sql), params)
        return self

    def executemany(self, sql, seq):
        self._raw.executemany(_q(sql), seq)
        return self

    def fetchone(self):
        return self._raw.fetchone()

    def fetchall(self):
        return self._raw.fetchall()

    @property
    def lastrowid(self):
        return self._raw.lastrowid

    @property
    def rowcount(self):
        return self._raw.rowcount

    def close(self):
        self._raw.close()


class _Conn:
    """Quack-alike for sqlite3.Connection (only what app.py uses)."""

    def __init__(self, raw):
        self._raw = raw

    # SQLite-style sugar: conn.execute(sql, params) returns a cursor.
    def execute(self, sql, params=()):
        cur = _Cursor(self._raw.cursor(DictCursor))
        cur.execute(sql, params)
        return cur

    def cursor(self):
        return _Cursor(self._raw.cursor(DictCursor))

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        try:
            self._raw.close()
        except Exception:
            pass

    # support `with get_connection() as conn:`
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# Connection helpers
def _raw_connect(database=DB_NAME):
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=database,
        autocommit=False,
        charset="utf8mb4",
    )


def get_connection():
    """Return a wrapped MySQL connection that mimics the old SQLite API."""
    return _Conn(_raw_connect())


def ensure_database():
    """Create the KasbPro database if it does not yet exist."""
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                "DEFAULT CHARACTER SET utf8mb4 "
                "DEFAULT COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_cursor(commit: bool = False):
    """Context manager — opens a connection, yields a cursor, optionally commits."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


# MySQL schema. Notes on the changes from the old SQLite schema:
#   * INTEGER PRIMARY KEY AUTOINCREMENT → INT AUTO_INCREMENT PRIMARY KEY
#   * TEXT          → VARCHAR(N) for indexed/unique columns, TEXT for free-form
#   * REAL          → DECIMAL(N,2) for money (avoids float rounding bugs)
#   * Added `is_deleted` on products & customers (soft-delete, fixes the 500
#     errors when deleting an item that's referenced by an old invoice).
#   * invoice_items.product_id is now nullable + ON DELETE SET NULL so the
#     same delete works at the DB level too — belt + suspenders.
#   * New `suppliers` table for the new Suppliers page.
SCHEMA_STATEMENTS = [
    # Users
    """
    CREATE TABLE IF NOT EXISTS users (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        full_name     VARCHAR(120) NOT NULL,
        email         VARCHAR(190) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role          ENUM('admin','owner','staff') NOT NULL,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # Product categories
    """
    CREATE TABLE IF NOT EXISTS categories (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        name       VARCHAR(60) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # Products with soft delete
    """
    CREATE TABLE IF NOT EXISTS products (
        id                  INT AUTO_INCREMENT PRIMARY KEY,
        name                VARCHAR(160) NOT NULL,
        sku                 VARCHAR(80)  UNIQUE,
        category            VARCHAR(60)  NOT NULL DEFAULT 'General',
        price               DECIMAL(10,2) NOT NULL DEFAULT 0,
        stock               INT NOT NULL DEFAULT 0,
        low_stock_threshold INT NOT NULL DEFAULT 10,
        supplier_id         INT NULL,
        is_deleted          TINYINT(1) NOT NULL DEFAULT 0,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_products_name      (name),
        INDEX idx_products_category  (category),
        INDEX idx_products_deleted   (is_deleted),
        INDEX idx_products_supplier  (supplier_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # Customers with soft delete
    """
    CREATE TABLE IF NOT EXISTS customers (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        name            VARCHAR(160)  NOT NULL,
        phone           VARCHAR(40)   UNIQUE,
        email           VARCHAR(190),
        total_purchases DECIMAL(12,2) NOT NULL DEFAULT 0,
        visit_count     INT NOT NULL DEFAULT 0,
        loyalty_tier    VARCHAR(20)   NOT NULL DEFAULT 'Bronze',
        last_visit      TIMESTAMP NULL DEFAULT NULL,
        is_deleted      TINYINT(1)    NOT NULL DEFAULT 0,
        created_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_customers_phone   (phone),
        INDEX idx_customers_deleted (is_deleted)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # Suppliers
    """
    CREATE TABLE IF NOT EXISTS suppliers (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        name        VARCHAR(160) NOT NULL,
        contact     VARCHAR(160),
        phone       VARCHAR(40),
        email       VARCHAR(190),
        address     VARCHAR(255),
        notes       TEXT,
        is_deleted  TINYINT(1) NOT NULL DEFAULT 0,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_suppliers_name    (name),
        INDEX idx_suppliers_deleted (is_deleted)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # Invoices
    """
    CREATE TABLE IF NOT EXISTS invoices (
        id             INT AUTO_INCREMENT PRIMARY KEY,
        invoice_number VARCHAR(64) NOT NULL UNIQUE,
        customer_id    INT NULL,
        subtotal       DECIMAL(12,2) NOT NULL DEFAULT 0,
        tax            DECIMAL(12,2) NOT NULL DEFAULT 0,
        total          DECIMAL(12,2) NOT NULL DEFAULT 0,
        status         ENUM('Paid','Pending','Cancelled') NOT NULL DEFAULT 'Paid',
        created_by     INT NOT NULL,
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by)  REFERENCES users(id),
        INDEX idx_invoices_date     (created_at),
        INDEX idx_invoices_customer (customer_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # Invoice line items
    """
    CREATE TABLE IF NOT EXISTS invoice_items (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        invoice_id   INT NOT NULL,
        product_id   INT NULL,
        product_name VARCHAR(160) NOT NULL,
        quantity     INT NOT NULL,
        unit_price   DECIMAL(10,2) NOT NULL,
        line_total   DECIMAL(12,2) NOT NULL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
        INDEX idx_items_invoice (invoice_id),
        INDEX idx_items_product (product_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,

    # Audit log
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        user_id     INT NULL,
        user_email  VARCHAR(190),
        action      VARCHAR(40) NOT NULL,
        table_name  VARCHAR(40),
        record_id   INT NULL,
        details     TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
        INDEX idx_audit_date (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def init_db():
    """Create database + all tables. Safe to call on every startup."""
    ensure_database()
    conn = get_connection()
    try:
        cur = conn.cursor()
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
        cur.execute(
            "INSERT IGNORE INTO categories (name) VALUES (?)", ("Other",)
        )
        cur.execute(
            """INSERT IGNORE INTO categories (name)
               SELECT DISTINCT category FROM products
               WHERE category IS NOT NULL AND TRIM(category) <> ''"""
        )
        cur.execute(
            "ALTER TABLE users MODIFY role ENUM('admin','owner','staff') NOT NULL"
        )
        has_supplier_id = cur.execute(
            """SELECT COUNT(*) AS n FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'products'
                 AND COLUMN_NAME = 'supplier_id'""",
            (DB_NAME,),
        ).fetchone()["n"]
        if not has_supplier_id:
            cur.execute(
                """ALTER TABLE products
                   ADD COLUMN supplier_id INT NULL,
                   ADD INDEX idx_products_supplier (supplier_id),
                   ADD CONSTRAINT fk_products_supplier FOREIGN KEY (supplier_id)
                   REFERENCES suppliers(id) ON DELETE SET NULL"""
            )
        has_supplier_fk = cur.execute(
            """SELECT COUNT(*) AS n FROM information_schema.KEY_COLUMN_USAGE
               WHERE TABLE_SCHEMA = ? AND TABLE_NAME = 'products'
                 AND COLUMN_NAME = 'supplier_id' AND REFERENCED_TABLE_NAME = 'suppliers'""",
            (DB_NAME,),
        ).fetchone()["n"]
        if not has_supplier_fk:
            cur.execute(
                """ALTER TABLE products ADD CONSTRAINT fk_products_supplier
                   FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL"""
            )
        conn.commit()
    finally:
        conn.close()


def reset_db():
    """Drop tables then recreate. Used by seed.py.

    We DROP TABLES (with FK checks off) instead of dropping the database so
    the existing connection / user permissions stay intact.
    """
    ensure_database()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur._raw.execute("SET FOREIGN_KEY_CHECKS = 0")
        for t in ("audit_log", "invoice_items", "invoices",
              "customers", "suppliers", "products", "categories", "users"):
            cur._raw.execute(f"DROP TABLE IF EXISTS `{t}`")
        cur._raw.execute("SET FOREIGN_KEY_CHECKS = 1")
        for stmt in SCHEMA_STATEMENTS:
            cur._raw.execute(stmt)
        cur._raw.execute("INSERT IGNORE INTO categories (name) VALUES ('Other')")
        conn.commit()
    finally:
        conn.close()


# Audit helper used by request handlers
def write_audit(cur, user, action, table=None, record_id=None, details=None):
    """Log every mutating action so Admins can see who did what."""
    cur.execute(
        """
        INSERT INTO audit_log (user_id, user_email, action, table_name, record_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user["id"] if user else None,
            user["email"] if user else None,
            action,
            table,
            record_id,
            details,
        ),
    )


if __name__ == "__main__":
    init_db()
    print(f"✓ KasbPro DB initialised → mysql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
