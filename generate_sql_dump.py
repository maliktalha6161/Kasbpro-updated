"""
Generate `kasbpro_dump.sql` — a ready-to-import MySQL dump that contains the
full KasbPro schema plus realistic dummy data (users, products, suppliers,
customers, ~120 invoices over the last 30 days, audit-log).

Usage:
    python generate_sql_dump.py

The dump can then be loaded with any of:
    • phpMyAdmin → Import tab
    • MySQL Workbench → Server → Data Import → Import from Self-Contained File
    • CLI:   mysql -u root -p < kasbpro_dump.sql
"""

import random
import datetime as dt
from werkzeug.security import generate_password_hash

from database import SCHEMA_STATEMENTS, DB_NAME
from seed import PRODUCTS, CUSTOMERS, SUPPLIERS


def esc(v):
    """Tiny SQL value escaper. Good enough for trusted seed data."""
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return f"{v}"
    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def _loyalty(total):
    if total >= 1000:
        return "Gold"
    if total >= 300:
        return "Silver"
    return "Bronze"


def build_sql():
    out = []
    p = out.append

    p("-- KasbPro MySQL dump")
    p(f"-- Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    p("-- Import with phpMyAdmin, MySQL Workbench, or the MySQL CLI.")
    p("")
    p(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
      "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;")
    p(f"USE `{DB_NAME}`;")
    p("")
    p("SET FOREIGN_KEY_CHECKS = 0;")
    for t in ("audit_log", "invoice_items", "invoices",
              "customers", "suppliers", "products", "categories", "users"):
        p(f"DROP TABLE IF EXISTS `{t}`;")
    p("")

    # Schema
    for stmt in SCHEMA_STATEMENTS:
        clean = " ".join(stmt.split()).strip().rstrip(";")
        p(clean + ";")
    p("")
    p("SET FOREIGN_KEY_CHECKS = 1;")
    p("")

    # Users
    p("-- Users")
    admin_hash = generate_password_hash("admin123")
    owner_hash = generate_password_hash("owner123")
    p("INSERT INTO users (id, full_name, email, password_hash, role) VALUES")
    p(f"  (1, 'Farhan Asif',   'admin@kasbpro.com', {esc(admin_hash)}, 'admin'),")
    p(f"  (2, 'Muhammad Saad', 'owner@kasbpro.com', {esc(owner_hash)}, 'owner');")
    p("")

    # Categories
    p("-- Categories")
    category_names = sorted({category for _, _, category, _, _, _ in PRODUCTS} | {"Other"})
    p("INSERT INTO categories (name) VALUES")
    p(",\n".join(f"  ({esc(category)})" for category in category_names) + ";")
    p("")

    # Products
    p("-- Products")
    p("INSERT INTO products (id, name, sku, category, price, stock, low_stock_threshold) VALUES")
    rows = []
    for i, (name, sku, cat, price, stock, low) in enumerate(PRODUCTS, start=1):
        rows.append(f"  ({i}, {esc(name)}, {esc(sku)}, {esc(cat)}, {price}, {stock}, {low})")
    p(",\n".join(rows) + ";")
    p("")

    # Suppliers
    p("-- Suppliers")
    p("INSERT INTO suppliers (id, name, contact, phone, email, address, notes) VALUES")
    rows = []
    for i, (name, contact, phone, email, address, notes) in enumerate(SUPPLIERS, start=1):
        rows.append(
            f"  ({i}, {esc(name)}, {esc(contact)}, {esc(phone)}, "
            f"{esc(email)}, {esc(address)}, {esc(notes)})"
        )
    p(",\n".join(rows) + ";")
    p("")

    # Customers
    p("-- Customers; totals and loyalty are backfilled after invoices.")
    p("INSERT INTO customers (id, name, phone, email) VALUES")
    rows = []
    for i, (name, phone, email) in enumerate(CUSTOMERS, start=1):
        rows.append(f"  ({i}, {esc(name)}, {esc(phone)}, {esc(email)})")
    p(",\n".join(rows) + ";")
    p("")

    # Invoices and line items
    p("-- Invoices and line items over the last 30 days")
    rng = random.Random(42)
    customer_ids = list(range(1, len(CUSTOMERS) + 1))
    product_lookup = [
        (i + 1, name, price)
        for i, (name, sku, cat, price, stock, low) in enumerate(PRODUCTS)
    ]
    stocks = {i + 1: stock for i, (n, s, c, p_, stock, lo) in enumerate(PRODUCTS)}

    inv_rows = []
    item_rows = []
    cust_totals = {c: {"total": 0.0, "visits": 0, "last": None} for c in customer_ids}

    invoice_id = 0
    today = dt.date.today()

    for days_ago in range(29, -1, -1):
        weekday = (today - dt.timedelta(days=days_ago)).weekday()
        n_invoices = rng.randint(2, 5) if weekday < 5 else rng.randint(4, 7)

        for _ in range(n_invoices):
            invoice_id += 1
            ts_dt = (dt.datetime.now() - dt.timedelta(
                days=days_ago,
                hours=rng.randint(0, 12),
                minutes=rng.randint(0, 59),
            ))
            ts = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
            cid = rng.choice(customer_ids) if rng.random() < 0.85 else None
            n_items = rng.randint(1, 5)
            picks = rng.sample(product_lookup, k=n_items)

            subtotal = 0.0
            picked_items = []
            for (pid, pname, price) in picks:
                qty = rng.randint(1, 4)
                lt = round(price * qty, 2)
                subtotal += lt
                picked_items.append((pid, pname, qty, price, lt))
                stocks[pid] = max(stocks[pid] - qty, 0)

            total = round(subtotal, 2)
            inv_no = (
                f"INV-{ts.replace(' ', '').replace('-', '').replace(':', '')[:15]}"
                f"-{rng.randint(10, 99)}"
            )

            inv_rows.append(
                f"  ({invoice_id}, {esc(inv_no)}, {cid if cid else 'NULL'}, "
                f"{subtotal}, 0.00, {total}, 'Paid', 1, {esc(ts)})"
            )

            for (pid, pname, qty, price, lt) in picked_items:
                item_rows.append(
                    f"  ({invoice_id}, {pid}, {esc(pname)}, {qty}, {price}, {lt})"
                )

            if cid:
                cust_totals[cid]["total"] += total
                cust_totals[cid]["visits"] += 1
                if (cust_totals[cid]["last"] is None
                        or cust_totals[cid]["last"] < ts):
                    cust_totals[cid]["last"] = ts

    p("INSERT INTO invoices "
      "(id, invoice_number, customer_id, subtotal, tax, total, status, created_by, created_at) VALUES")
    p(",\n".join(inv_rows) + ";")
    p("")

    p("INSERT INTO invoice_items "
      "(invoice_id, product_id, product_name, quantity, unit_price, line_total) VALUES")
    p(",\n".join(item_rows) + ";")
    p("")

    # Updated stock figures
    p("-- Updated stock figures after the simulated sales")
    for pid, stock in stocks.items():
        p(f"UPDATE products SET stock = {stock} WHERE id = {pid};")
    p("")
    p("-- Force a few items to low/out-of-stock so dashboard widgets have signal")
    p("UPDATE products SET stock = 5  WHERE name = 'Sugar (1kg)';")
    p("UPDATE products SET stock = 8  WHERE name = 'Eggs (dozen)';")
    p("UPDATE products SET stock = 12 WHERE name = 'Wheat Flour (10kg)';")
    p("UPDATE products SET stock = 0  WHERE name = 'Soap Bar';")
    p("UPDATE products SET stock = 0  WHERE name = 'Cheese Block (200g)';")
    p("")

    # Customer totals & loyalty
    p("-- Roll-up customer totals + loyalty tiers")
    for cid, info in cust_totals.items():
        tier = _loyalty(info["total"])
        last = esc(info["last"]) if info["last"] else "NULL"
        p(
            f"UPDATE customers SET "
            f"total_purchases = {round(info['total'], 2)}, "
            f"visit_count     = {info['visits']}, "
            f"last_visit      = {last}, "
            f"loyalty_tier    = '{tier}' "
            f"WHERE id = {cid};"
        )
    p("")

    # Audit row
    p("-- Audit log seed entry")
    p(
        "INSERT INTO audit_log (user_id, user_email, action, table_name, details) VALUES "
        "(1, 'admin@kasbpro.com', 'SEED', 'system', 'Database seeded from SQL dump');"
    )

    p("")
    p("-- ✓ Dump complete — log in with:")
    p("--      admin@kasbpro.com / admin123  (admin, full CRUD)")
    p("--      owner@kasbpro.com / owner123  (owner, read-only)")
    p("")

    return "\n".join(out)


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    sql = build_sql()
    out_path = os.path.join(here, "kasbpro_dump.sql")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(sql)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"✓ Wrote {out_path}  ({size_kb:.1f} KB)")
