"""
KasbPro · app.py
Flask back-end implementing FR-01 … FR-07 from the project report,
plus the new Reports & Suppliers modules.

Run:
    pip install -r requirements.txt
    python seed.py       # creates/refreshes the kasbpro MySQL DB with dummy data
    python app.py        # http://localhost:5001
"""

import os
import json
import datetime as dt
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import pymysql
import google.generativeai as genai
from dotenv import load_dotenv
from flask import (
    Flask, request, jsonify, session, send_from_directory, abort, Response
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import init_db, get_connection, write_audit

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-3.1-flash-lite"

# Flask setup
HERE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=HERE, static_url_path="")
app.config["SECRET_KEY"] = os.environ.get(
    "KASBPRO_SECRET", "dev-secret-change-me-in-production"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Ensure schema exists on first run (creates DB + tables if missing).
init_db()


# Static and HTML routes
@app.route("/")
def root():
    return send_from_directory(HERE, "3main.html")


@app.route("/<path:path>")
def static_files(path):
    # serve any HTML / CSS / JS file by name; 404 if missing
    if os.path.isfile(os.path.join(HERE, path)):
        return send_from_directory(HERE, path)
    abort(404)


# Authentication helpers
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_connection()
    try:
        u = conn.execute(
            "SELECT id, full_name, email, role FROM users WHERE id = ?", (uid,)
        ).fetchone()
    finally:
        conn.close()
    return dict(u) if u else None


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        u = current_user()
        if not u:
            return jsonify(success=False, message="Authentication required"), 401
        request.user = u
        return f(*a, **kw)
    return wrapper


def owner_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if request.user["role"] != "owner":
            return jsonify(success=False, message="Owner role required"), 403
        return f(*a, **kw)
    return wrapper


def owner_or_admin_edit_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if request.user["role"] not in ("admin", "owner"):
            return jsonify(success=False, message="Owner or admin role required"), 403
        return f(*a, **kw)
    return wrapper


def owner_or_admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if request.user["role"] not in ("admin", "owner"):
            return jsonify(success=False, message="Owner or admin role required"), 403
        return f(*a, **kw)
    return wrapper


def billing_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if request.user["role"] not in ("admin", "staff"):
            return jsonify(success=False, message="Billing role required"), 403
        return f(*a, **kw)
    return wrapper


# Authentication
@app.post("/api/auth/register")
def api_register():
    data = request.get_json(force=True) or {}
    full_name = (data.get("full_name") or "").strip()
    email     = (data.get("email") or "").strip().lower()
    password  = data.get("password") or ""
    role      = (data.get("role") or "owner").lower()

    if role not in ("admin", "owner", "staff"):
        return jsonify(success=False, message="Invalid role"), 400
    if not (full_name and email and password):
        return jsonify(success=False, message="All fields are required"), 400
    if len(password) < 6:
        return jsonify(success=False, message="Password must be ≥ 6 chars"), 400

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return jsonify(success=False, message="Email already registered"), 409

        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (?,?,?,?)",
            (full_name, email, generate_password_hash(password), role),
        )
        conn.commit()
        return jsonify(success=True, message="Account created")
    finally:
        conn.close()


@app.post("/api/auth/login")
def api_login():
    data = request.get_json(force=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    conn = get_connection()
    try:
        u = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if not u or not check_password_hash(u["password_hash"], password):
        return jsonify(success=False, message="Invalid credentials"), 401

    session.clear()
    session["user_id"] = u["id"]
    return jsonify(
        success=True,
        user={
            "id":        u["id"],
            "full_name": u["full_name"],
            "email":     u["email"],
            "role":      u["role"],
        },
    )


@app.post("/api/auth/logout")
def api_logout():
    session.clear()
    return jsonify(success=True)


@app.get("/api/auth/me")
def api_me():
    u = current_user()
    if not u:
        return jsonify(success=False), 401
    return jsonify(success=True, user=u)


# Categories and inventory CRUD
@app.get("/api/categories")
@login_required
def api_categories_list():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, created_at FROM categories ORDER BY name"
        ).fetchall()
    finally:
        conn.close()

    categories = []
    for row in rows:
        category = dict(row)
        if category.get("created_at"):
            category["created_at"] = category["created_at"].isoformat()
        categories.append(category)
    return jsonify(success=True, categories=categories)


@app.post("/api/categories")
@owner_or_admin_edit_required
def api_categories_create():
    name = ((request.get_json(force=True) or {}).get("name") or "").strip()
    if not name:
        return jsonify(success=False, message="Category name is required"), 400
    if len(name) > 60:
        return jsonify(success=False, message="Category name must be 60 characters or fewer"), 400

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if existing:
            return jsonify(success=False, message="Category already exists"), 409

        cur = conn.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        category_id = cur.lastrowid
        write_audit(cur, request.user, "CREATE", "categories", category_id, name)
        conn.commit()
        return jsonify(success=True, id=category_id, name=name)
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify(success=False, message="Category already exists"), 409
    finally:
        conn.close()


@app.delete("/api/categories/<int:category_id>")
@owner_required
def api_categories_delete(category_id):
    conn = get_connection()
    try:
        category = conn.execute(
            "SELECT id, name FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if not category:
            return jsonify(success=False, message="Category not found"), 404
        if category["name"].lower() == "other":
            return jsonify(success=False, message="The Other category cannot be deleted"), 400

        product_count = conn.execute(
            "SELECT COUNT(*) AS n FROM products WHERE category = ? AND is_deleted = 0",
            (category["name"],),
        ).fetchone()["n"]
        if product_count:
            return jsonify(
                success=False,
                message=f"Cannot delete — {product_count} products are using this category",
            ), 409

        cur = conn.cursor()
        cur.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        write_audit(cur, request.user, "DELETE", "categories", category_id, category["name"])
        conn.commit()
        return jsonify(success=True)
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()


@app.get("/api/products")
@login_required
def api_products_list():
    q = (request.args.get("q") or "").strip().lower()
    conn = get_connection()
    try:
        rows = conn.execute(
                """SELECT p.*, s.name AS supplier_name
                    FROM products p
                    LEFT JOIN suppliers s ON s.id = p.supplier_id
                    WHERE p.is_deleted = 0 ORDER BY p.name"""
        ).fetchall()
    finally:
        conn.close()

    items = [dict(r) for r in rows]
    # Stringify Decimal so JSON serialises predictably for JS (it just sees numbers).
    for p in items:
        p["price"] = float(p["price"])

    if q:
        items = [
            p for p in items
            if q in p["name"].lower() or q in (p.get("sku") or "").lower()
        ]

    # derived status field
    for p in items:
        if p["stock"] == 0:
            p["status"] = "Out of stock"
        elif p["stock"] <= p["low_stock_threshold"]:
            p["status"] = "Low stock"
        else:
            p["status"] = "In stock"

    return jsonify(success=True, products=items)


@app.post("/api/products")
@owner_or_admin_edit_required
def api_products_create():
    d = request.get_json(force=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify(success=False, message="Name is required"), 400
    supplier_id = d.get("supplier_id") or None
    if supplier_id is not None:
        supplier_id = int(supplier_id)
    category = (d.get("category") or "Other").strip()

    conn = get_connection()
    try:
        category_row = conn.execute(
            "SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (category,)
        ).fetchone()
        if not category_row:
            return jsonify(success=False, message="Selected category does not exist"), 400
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO products
                                 (name, sku, category, price, stock, low_stock_threshold, supplier_id)
                             VALUES (?,?,?,?,?,?,?)""",
            (
                name,
                (d.get("sku") or "").strip() or None,
                category,
                float(d.get("price") or 0),
                int(d.get("stock") or 0),
                int(d.get("low_stock_threshold") or 10),
                supplier_id,
            ),
        )
        pid = cur.lastrowid
        write_audit(cur, request.user, "CREATE", "products", pid, name)
        conn.commit()
        return jsonify(success=True, id=pid)
    except pymysql.err.IntegrityError as e:
        return jsonify(success=False, message=f"Duplicate SKU: {e.args[1] if len(e.args)>1 else e}"), 409
    except Exception as e:
        return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()


@app.put("/api/products/<int:pid>")
@owner_or_admin_edit_required
def api_products_update(pid):
    d = request.get_json(force=True) or {}
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM products WHERE id = ? AND is_deleted = 0", (pid,)
        ).fetchone()
        if not existing:
            return jsonify(success=False, message="Product not found"), 404

        category = (d.get("category") or existing["category"]).strip()
        category_row = conn.execute(
            "SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (category,)
        ).fetchone()
        if not category_row:
            return jsonify(success=False, message="Selected category does not exist"), 400

        supplier_id = d.get("supplier_id", existing["supplier_id"]) or None
        if supplier_id is not None:
            supplier_id = int(supplier_id)

        cur = conn.cursor()
        try:
            cur.execute(
                """UPDATE products SET
                     name = ?, sku = ?, category = ?,
                     price = ?, stock = ?, low_stock_threshold = ?, supplier_id = ?
                   WHERE id = ?""",
                (
                    (d.get("name") or existing["name"]).strip(),
                    (d.get("sku") or existing["sku"] or "").strip() or None,
                    category,
                    float(d.get("price", existing["price"])),
                    int(d.get("stock", existing["stock"])),
                    int(d.get("low_stock_threshold", existing["low_stock_threshold"])),
                    supplier_id,
                    pid,
                ),
            )
            write_audit(cur, request.user, "UPDATE", "products", pid)
            conn.commit()
            return jsonify(success=True)
        except pymysql.err.IntegrityError as e:
            conn.rollback()
            return jsonify(success=False,
                           message=f"Duplicate SKU: {e.args[1] if len(e.args) > 1 else e}"), 409
        except Exception as e:
            conn.rollback()
            return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()


@app.delete("/api/products/<int:pid>")
@owner_required
def api_products_delete(pid):
    """
    Smart delete (fix for HTTP-500 bug):
      * If the product has NEVER been on an invoice, hard-delete it.
      * If it has been on an invoice, soft-delete it (is_deleted = 1) so
        historical reports & line-items keep working.
    Either way the user sees a successful delete.
    """
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM products WHERE id = ? AND is_deleted = 0", (pid,)
        ).fetchone()
        if not existing:
            return jsonify(success=False, message="Product not found"), 404

        ref = conn.execute(
            "SELECT COUNT(*) AS n FROM invoice_items WHERE product_id = ?", (pid,)
        ).fetchone()["n"]

        cur = conn.cursor()
        if ref == 0:
            cur.execute("DELETE FROM products WHERE id = ?", (pid,))
            write_audit(cur, request.user, "DELETE", "products", pid,
                        f"Hard-delete: {existing['name']}")
        else:
            cur.execute(
                "UPDATE products SET is_deleted = 1 WHERE id = ?", (pid,)
            )
            write_audit(cur, request.user, "ARCHIVE", "products", pid,
                        f"Soft-delete ({ref} invoice refs): {existing['name']}")
        conn.commit()
        return jsonify(success=True)
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()

def _loyalty_tier(total: float) -> str:
    if total >= 1000:
        return "Gold"
    if total >= 300:
        return "Silver"
    return "Bronze"


@app.get("/api/customers")
@login_required
def api_customers_list():
    q = (request.args.get("q") or "").strip().lower()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM customers WHERE is_deleted = 0 ORDER BY name"
        ).fetchall()
    finally:
        conn.close()

    items = [dict(r) for r in rows]
    for c in items:
        c["total_purchases"] = float(c["total_purchases"])
        for field in ("created_at", "last_visit"):
            if hasattr(c.get(field), "isoformat"):
                c[field] = c[field].isoformat()

    if q:
        items = [
            c for c in items
            if q in c["name"].lower() or q in (c.get("phone") or "").lower()
        ]
    return jsonify(success=True, customers=items)


@app.post("/api/customers")
@login_required
def api_customers_create():
    d = request.get_json(force=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify(success=False, message="Name is required"), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO customers (name, phone, email, loyalty_tier)
               VALUES (?,?,?,?)""",
            (
                name,
                (d.get("phone") or "").strip() or None,
                (d.get("email") or "").strip() or None,
                "Bronze",
            ),
        )
        cid = cur.lastrowid
        write_audit(cur, request.user, "CREATE", "customers", cid, name)
        conn.commit()
        return jsonify(success=True, id=cid)
    except pymysql.err.IntegrityError:
        return jsonify(success=False, message="Phone already exists"), 409
    finally:
        conn.close()


@app.put("/api/customers/<int:cid>")
@owner_or_admin_edit_required
def api_customers_update(cid):
    d = request.get_json(force=True) or {}
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM customers WHERE id = ? AND is_deleted = 0", (cid,)
        ).fetchone()
        if not existing:
            return jsonify(success=False, message="Customer not found"), 404
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE customers SET name = ?, phone = ?, email = ? WHERE id = ?",
                (
                    (d.get("name") or existing["name"]).strip(),
                    (d.get("phone") or existing["phone"] or "").strip() or None,
                    (d.get("email") or existing["email"] or "").strip() or None,
                    cid,
                ),
            )
            write_audit(cur, request.user, "UPDATE", "customers", cid)
            conn.commit()
            return jsonify(success=True)
        except pymysql.err.IntegrityError:
            conn.rollback()
            return jsonify(success=False, message="Phone already exists"), 409
        except Exception as e:
            conn.rollback()
            return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()


@app.delete("/api/customers/<int:cid>")
@owner_required
def api_customers_delete(cid):
    """Smart delete — same approach as products. (FR-06)"""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM customers WHERE id = ? AND is_deleted = 0", (cid,)
        ).fetchone()
        if not existing:
            return jsonify(success=False, message="Customer not found"), 404

        ref = conn.execute(
            "SELECT COUNT(*) AS n FROM invoices WHERE customer_id = ?", (cid,)
        ).fetchone()["n"]

        cur = conn.cursor()
        if ref == 0:
            cur.execute("DELETE FROM customers WHERE id = ?", (cid,))
            write_audit(cur, request.user, "DELETE", "customers", cid,
                        f"Hard-delete: {existing['name']}")
        else:
            cur.execute(
                "UPDATE customers SET is_deleted = 1 WHERE id = ?", (cid,)
            )
            write_audit(cur, request.user, "ARCHIVE", "customers", cid,
                        f"Soft-delete ({ref} invoice refs): {existing['name']}")
        conn.commit()
        return jsonify(success=True)
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()


# Supplier CRUD
@app.get("/api/suppliers")
@login_required
def api_suppliers_list():
    q = (request.args.get("q") or "").strip().lower()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM suppliers WHERE is_deleted = 0 ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    items = [dict(r) for r in rows]
    if q:
        items = [
            s for s in items
            if q in (s["name"] or "").lower()
               or q in (s.get("contact") or "").lower()
               or q in (s.get("phone") or "").lower()
        ]
    return jsonify(success=True, suppliers=items)


@app.post("/api/suppliers")
@owner_or_admin_edit_required
def api_suppliers_create():
    d = request.get_json(force=True) or {}
    name = (d.get("name") or "").strip()
    if not name:
        return jsonify(success=False, message="Name is required"), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO suppliers (name, contact, phone, email, address, notes)
               VALUES (?,?,?,?,?,?)""",
            (
                name,
                (d.get("contact") or "").strip() or None,
                (d.get("phone")   or "").strip() or None,
                (d.get("email")   or "").strip() or None,
                (d.get("address") or "").strip() or None,
                (d.get("notes")   or "").strip() or None,
            ),
        )
        sid = cur.lastrowid
        write_audit(cur, request.user, "CREATE", "suppliers", sid, name)
        conn.commit()
        return jsonify(success=True, id=sid)
    finally:
        conn.close()


@app.put("/api/suppliers/<int:sid>")
@owner_or_admin_edit_required
def api_suppliers_update(sid):
    d = request.get_json(force=True) or {}
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM suppliers WHERE id = ? AND is_deleted = 0", (sid,)
        ).fetchone()
        if not existing:
            return jsonify(success=False, message="Supplier not found"), 404
        cur = conn.cursor()
        cur.execute(
            """UPDATE suppliers SET name = ?, contact = ?, phone = ?,
                                    email = ?, address = ?, notes = ?
               WHERE id = ?""",
            (
                (d.get("name")    or existing["name"]).strip(),
                (d.get("contact") or existing["contact"] or "").strip() or None,
                (d.get("phone")   or existing["phone"]   or "").strip() or None,
                (d.get("email")   or existing["email"]   or "").strip() or None,
                (d.get("address") or existing["address"] or "").strip() or None,
                (d.get("notes")   or existing["notes"]   or "").strip() or None,
                sid,
            ),
        )
        write_audit(cur, request.user, "UPDATE", "suppliers", sid)
        conn.commit()
        return jsonify(success=True)
    finally:
        conn.close()


@app.delete("/api/suppliers/<int:sid>")
@owner_required
def api_suppliers_delete(sid):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM suppliers WHERE id = ? AND is_deleted = 0", (sid,)
        ).fetchone()
        if not existing:
            return jsonify(success=False, message="Supplier not found"), 404
        cur = conn.cursor()
        cur.execute("DELETE FROM suppliers WHERE id = ?", (sid,))
        write_audit(cur, request.user, "DELETE", "suppliers", sid,
                    f"Deleted supplier: {existing['name']}")
        conn.commit()
        return jsonify(success=True)
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()


# Digital billing and stock updates
@app.get("/api/invoices")
@login_required
def api_invoices_list():
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT i.*, c.name AS customer_name,
                      (SELECT SUM(quantity) FROM invoice_items WHERE invoice_id = i.id) AS item_count
               FROM invoices i
               LEFT JOIN customers c ON c.id = i.customer_id
               ORDER BY i.created_at DESC
               LIMIT 200"""
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("subtotal", "tax", "total"):
            d[k] = float(d[k]) if d[k] is not None else 0.0
        d["item_count"] = int(d["item_count"] or 0)
        d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M:%S") if d.get("created_at") else None
        out.append(d)
    return jsonify(success=True, invoices=out)


@app.get("/api/invoices/<int:iid>")
@login_required
def api_invoice_detail(iid):
    conn = get_connection()
    try:
        inv = conn.execute(
            """SELECT i.*, c.name AS customer_name
               FROM invoices i LEFT JOIN customers c ON c.id = i.customer_id
               WHERE i.id = ?""",
            (iid,),
        ).fetchone()
        if not inv:
            return jsonify(success=False, message="Not found"), 404
        items = conn.execute(
            "SELECT * FROM invoice_items WHERE invoice_id = ?", (iid,)
        ).fetchall()
    finally:
        conn.close()

    inv = dict(inv)
    for k in ("subtotal", "tax", "total"):
        inv[k] = float(inv[k]) if inv[k] is not None else 0.0
    if inv.get("created_at"):
        inv["created_at"] = inv["created_at"].strftime("%Y-%m-%d %H:%M:%S")

    items_out = []
    for it in items:
        d = dict(it)
        d["unit_price"] = float(d["unit_price"])
        d["line_total"] = float(d["line_total"])
        items_out.append(d)

    return jsonify(success=True, invoice=inv, items=items_out)


@app.post("/api/invoices")
@billing_required
def api_invoices_create():
    """
    Atomic POS transaction:
      1) validate items + stock
      2) insert invoice + line items
      3) deduct stock on each product (FR-04)
      4) update customer totals + loyalty tier (FR-06)
      5) write audit
    """
    d = request.get_json(force=True) or {}
    customer_id = d.get("customer_id")        # may be None for walk-in
    items_in = d.get("items") or []
    if not items_in:
        return jsonify(success=False, message="No items in invoice"), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur._raw.execute("START TRANSACTION")

        subtotal = 0.0
        resolved = []

        
        for it in items_in:
            pid = int(it["product_id"])
            qty = int(it["quantity"])
            if qty <= 0:
                raise ValueError("Quantity must be positive")
            p = cur.execute(
                "SELECT * FROM products WHERE id = ? AND is_deleted = 0 FOR UPDATE",
                (pid,),
            ).fetchone()
            if not p:
                raise ValueError(f"Product {pid} not found")
            if p["stock"] < qty:
                raise ValueError(
                    f"Not enough stock for {p['name']} (have {p['stock']}, need {qty})"
                )
            unit_price = float(p["price"])
            line_total = round(unit_price * qty, 2)
            subtotal += line_total
            resolved.append({
                "product_id": pid,
                "name":       p["name"],
                "qty":        qty,
                "price":      unit_price,
                "line_total": line_total,
            })

        tax = round(subtotal * 0.0, 2)
        total = round(subtotal + tax, 2)
        now = dt.datetime.now()
        inv_no = f"INV-{now.strftime('%Y%m%d-%H%M%S')}-{now.microsecond // 1000:03d}"

        # 2) insert invoice
        cur.execute(
            """INSERT INTO invoices
                 (invoice_number, customer_id, subtotal, tax, total, status, created_by)
               VALUES (?,?,?,?,?,?,?)""",
            (inv_no, customer_id, subtotal, tax, total, "Paid", request.user["id"]),
        )
        invoice_id = cur.lastrowid

        for r in resolved:
            cur.execute(
                """INSERT INTO invoice_items
                     (invoice_id, product_id, product_name, quantity, unit_price, line_total)
                   VALUES (?,?,?,?,?,?)""",
                (invoice_id, r["product_id"], r["name"], r["qty"], r["price"], r["line_total"]),
            )
            cur.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (r["qty"], r["product_id"]),
            )

        if customer_id:
            cur.execute(
                """UPDATE customers SET
                     total_purchases = total_purchases + ?,
                     visit_count     = visit_count + 1,
                     last_visit      = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (total, customer_id),
            )
            new_total = cur.execute(
                "SELECT total_purchases FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()["total_purchases"]
            cur.execute(
                "UPDATE customers SET loyalty_tier = ? WHERE id = ?",
                (_loyalty_tier(float(new_total)), customer_id),
            )

        write_audit(cur, request.user, "CREATE", "invoices", invoice_id, inv_no)
        conn.commit()
        return jsonify(success=True, id=invoice_id, invoice_number=inv_no, total=total)

    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()




@app.get("/api/dashboard/stats")
@owner_or_admin_required
def api_dashboard_stats():
    today    = dt.date.today().isoformat()
    week_ago = (dt.date.today() - dt.timedelta(days=6)).isoformat()

    conn = get_connection()
    try:
        today_sales = conn.execute(
            "SELECT COALESCE(SUM(total),0) AS s, COUNT(*) AS n "
            "FROM invoices WHERE DATE(created_at) = DATE(?)",
            (today,),
        ).fetchone()

        week_sales_rows = conn.execute(
            """SELECT DATE(created_at) AS d, COALESCE(SUM(total),0) AS t
               FROM invoices
               WHERE DATE(created_at) >= DATE(?)
               GROUP BY DATE(created_at)
               ORDER BY d""",
            (week_ago,),
        ).fetchall()

        total_customers = conn.execute(
            "SELECT COUNT(*) AS n FROM customers WHERE is_deleted = 0"
        ).fetchone()["n"]

        customers_today = conn.execute(
            "SELECT COUNT(DISTINCT customer_id) AS n FROM invoices "
            "WHERE DATE(created_at) = DATE(?) AND customer_id IS NOT NULL",
            (today,),
        ).fetchone()["n"]

        total_products = conn.execute(
            "SELECT COUNT(*) AS n FROM products WHERE is_deleted = 0"
        ).fetchone()["n"]

        low_stock = conn.execute(
            "SELECT name, stock FROM products "
            "WHERE is_deleted = 0 AND stock > 0 AND stock <= low_stock_threshold "
            "ORDER BY stock ASC LIMIT 10"
        ).fetchall()

        out_of_stock = conn.execute(
            "SELECT COUNT(*) AS n FROM products WHERE is_deleted = 0 AND stock = 0"
        ).fetchone()["n"]

        inv_value = conn.execute(
            "SELECT COALESCE(SUM(price * stock), 0) AS v FROM products WHERE is_deleted = 0"
        ).fetchone()["v"]

        recent_sales = conn.execute(
            """SELECT i.invoice_number, i.created_at, i.total,
                      COALESCE(c.name, 'Walk-in') AS customer,
                      (SELECT GROUP_CONCAT(CONCAT(product_name, ' x ', quantity) SEPARATOR ', ')
                         FROM invoice_items WHERE invoice_id = i.id) AS items
               FROM invoices i LEFT JOIN customers c ON c.id = i.customer_id
               ORDER BY i.created_at DESC LIMIT 5"""
        ).fetchall()

    finally:
        conn.close()

    
    today_total = float(today_sales["s"] or 0)
    profit = round(today_total * 0.35, 2)

    return jsonify(
        success=True,
        stats={
            "today_sales":     today_total,
            "today_invoices":  int(today_sales["n"] or 0),
            "profit":          profit,
            "total_customers": int(total_customers),
            "customers_today": int(customers_today),
            "total_products":  int(total_products),
            "out_of_stock":    int(out_of_stock),
            "inventory_value": round(float(inv_value or 0), 2),
            "low_stock":       [dict(r) for r in low_stock],
            "weekly_sales":    [
                {"date": r["d"].isoformat() if hasattr(r["d"], "isoformat") else str(r["d"]),
                 "total": float(r["t"])}
                for r in week_sales_rows
            ],
            "recent_sales":    [
                {
                    "invoice_number": r["invoice_number"],
                    "created_at":     r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                                      if r["created_at"] else None,
                    "total":          float(r["total"]),
                    "customer":       r["customer"],
                    "items":          r["items"],
                }
                for r in recent_sales
            ],
        },
    )


@app.get("/api/analytics/top-sellers")
@owner_or_admin_required
def api_top_sellers():
    days = int(request.args.get("days", 30))
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT ii.product_id, ii.product_name,
                      SUM(ii.quantity) AS units,
                      SUM(ii.line_total) AS revenue
               FROM invoice_items ii
               JOIN invoices i ON i.id = ii.invoice_id
               WHERE DATE(i.created_at) >= DATE(?)
               GROUP BY ii.product_id, ii.product_name
               ORDER BY units DESC LIMIT 10""",
            (since,),
        ).fetchall()
    finally:
        conn.close()
    return jsonify(success=True, top_sellers=[
        {"product_id": r["product_id"], "product_name": r["product_name"],
         "units": int(r["units"] or 0), "revenue": float(r["revenue"] or 0)}
        for r in rows
    ])


@app.post("/api/ai/chat")
@owner_or_admin_required
def api_ai_chat():
    """Rule-based assistant powered by real DB aggregates (FR-05)."""
    msg = ((request.get_json(force=True) or {}).get("message") or "").lower()
    conn = get_connection()
    try:
        if "today" in msg and "sale" in msg:
            r = conn.execute(
                "SELECT COALESCE(SUM(total),0) AS s, COUNT(*) AS n "
                "FROM invoices WHERE DATE(created_at) = CURDATE()"
            ).fetchone()
            yesterday = conn.execute(
                "SELECT COALESCE(SUM(total),0) AS s, COUNT(*) AS n "
                "FROM invoices WHERE DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
            ).fetchone()
            today_total = float(r["s"] or 0)
            yesterday_total = float(yesterday["s"] or 0)
            if yesterday_total:
                change = ((today_total - yesterday_total) / yesterday_total) * 100
                comparison = f"{'up' if change >= 0 else 'down'} {abs(change):.1f}% vs yesterday"
            else:
                comparison = "up 100.0% vs yesterday" if today_total else "unchanged (0.0%) vs yesterday"
            low_stock = conn.execute(
                "SELECT name, stock FROM products WHERE is_deleted = 0 "
                "AND stock <= low_stock_threshold ORDER BY stock ASC LIMIT 3"
            ).fetchall()
            ans = (
                f"Today's sales: Rs {today_total:.2f} across {int(r['n'])} invoices, "
                f"{comparison}."
            )
            if low_stock:
                items = ", ".join(f"{row['name']} ({row['stock']})" for row in low_stock)
                ans += f" Low stock: {items}."

        elif "stock" in msg or "low" in msg:
            rows = conn.execute(
                "SELECT name, stock FROM products WHERE is_deleted = 0 "
                "AND stock <= low_stock_threshold ORDER BY stock ASC LIMIT 8"
            ).fetchall()
            if rows:
                lines = ", ".join(f"{r['name']} ({r['stock']})" for r in rows)
                ans = f"Low / out-of-stock: {lines}."
            else:
                ans = "All products are above their low-stock threshold."

        elif "top" in msg or "best" in msg or "selling" in msg:
            rows = conn.execute(
                """SELECT product_name, SUM(quantity) AS q
                   FROM invoice_items
                   GROUP BY product_id, product_name
                   ORDER BY q DESC LIMIT 5"""
            ).fetchall()
            if rows:
                ans = "Top sellers: " + ", ".join(
                    f"{r['product_name']} ({int(r['q'])})" for r in rows
                )
            else:
                ans = "No sales yet."

        elif "summary" in msg or "overview" in msg or "business" in msg:
            week_ago = (dt.date.today() - dt.timedelta(days=6)).isoformat()
            r = conn.execute(
                "SELECT COALESCE(SUM(total),0) AS s, COUNT(*) AS n FROM invoices "
                "WHERE DATE(created_at) >= DATE(?)",
                (week_ago,),
            ).fetchone()
            nc = conn.execute(
                "SELECT COUNT(*) AS n FROM customers "
                "WHERE is_deleted = 0 AND DATE(created_at) >= DATE(?)",
                (week_ago,),
            ).fetchone()["n"]
            ans = (
                f"Last 7 days: Rs {float(r['s']):.2f} revenue across {int(r['n'])} invoices; "
                f"{int(nc)} new customers acquired."
            )

        elif "customer" in msg and ("today" in msg or "visit" in msg):
            n = conn.execute(
                "SELECT COUNT(DISTINCT customer_id) AS n FROM invoices "
                "WHERE DATE(created_at) = CURDATE() AND customer_id IS NOT NULL"
            ).fetchone()["n"]
            ans = f"{int(n)} distinct customers transacted today."

        else:
            print("DEBUG: Reached Gemini fallback branch", flush=True)
            generic_response = (
                "I can answer about sales, stock, top sellers, customer visits, "
                "or give a 7-day business summary. Try: \"today's sales\", "
                "\"low stock\", \"top sellers\", \"business summary\"."
            )
            try:
                today_data = conn.execute(
                    "SELECT COALESCE(SUM(total),0) AS total, COUNT(*) AS invoices "
                    "FROM invoices WHERE DATE(created_at) = CURDATE()"
                ).fetchone()
                yesterday_data = conn.execute(
                    "SELECT COALESCE(SUM(total),0) AS total "
                    "FROM invoices WHERE DATE(created_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
                ).fetchone()
                week_ago = (dt.date.today() - dt.timedelta(days=6)).isoformat()
                top_products = conn.execute(
                    """SELECT ii.product_name, SUM(ii.quantity) AS units
                       FROM invoice_items ii
                       JOIN invoices i ON i.id = ii.invoice_id
                       WHERE DATE(i.created_at) >= DATE(?)
                       GROUP BY ii.product_id, ii.product_name
                       ORDER BY units DESC LIMIT 3""",
                    (week_ago,),
                ).fetchall()
                low_stock = conn.execute(
                    "SELECT name, stock, low_stock_threshold FROM products "
                    "WHERE is_deleted = 0 AND stock <= low_stock_threshold "
                    "ORDER BY stock ASC"
                ).fetchall()
                customer_count = conn.execute(
                    "SELECT COUNT(*) AS total FROM customers WHERE is_deleted = 0"
                ).fetchone()

                snapshot = {
                    "today": {
                        "sales_total": float(today_data["total"] or 0),
                        "invoice_count": int(today_data["invoices"] or 0),
                    },
                    "yesterday_sales_total": float(yesterday_data["total"] or 0),
                    "top_3_products_this_week": [
                        {"product": row["product_name"], "units": int(row["units"] or 0)}
                        for row in top_products
                    ],
                    "low_stock_items": [
                        {
                            "product": row["name"],
                            "stock": int(row["stock"]),
                            "threshold": int(row["low_stock_threshold"]),
                        }
                        for row in low_stock
                    ],
                    "total_customers": int(customer_count["total"] or 0),
                }
                prompt = (
                    "You are a business assistant for a small retail store. "
                    "Answer ONLY using the provided business data and the user's question. "
                    "Always use 'Rs' as the currency symbol for Pakistani Rupees; "
                    "never use '$'. "
                    "Keep the response roughly 80-120 words. If the provided data does not "
                    "contain what is needed, say so honestly rather than making anything up.\n\n"
                    f"Business data:\n{json.dumps(snapshot, indent=2)}\n\n"
                    f"User question:\n{request.get_json(force=True).get('message', '')}"
                )
                model = genai.GenerativeModel(GEMINI_MODEL)
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(
                    model.generate_content,
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=400,
                        temperature=0.3,
                    ),
                    request_options={"timeout": 10},
                )
                try:
                    response = future.result(timeout=10)
                except FutureTimeoutError:
                    future.cancel()
                    raise TimeoutError("Gemini request timed out after 10 seconds")
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)
                print(f"DEBUG: Raw Gemini response: {response}", flush=True)
                ans = response.text.strip() or generic_response
            except Exception as e:
                print(f"DEBUG: Gemini call failed: {e!r}", flush=True)
                ans = generic_response
    finally:
        conn.close()
    return jsonify(success=True, response=ans)


def _parse_date(s, default):
    try:
        return dt.date.fromisoformat(s) if s else default
    except Exception:
        return default


@app.get("/api/reports/sales")
@owner_or_admin_required
def api_reports_sales():
    today = dt.date.today()
    start = _parse_date(request.args.get("start"), today - dt.timedelta(days=29))
    end   = _parse_date(request.args.get("end"),   today)

    conn = get_connection()
    try:
        summary = conn.execute(
            """SELECT COALESCE(SUM(total),0) AS revenue,
                      COUNT(*) AS invoices,
                      COALESCE(SUM(total) / NULLIF(COUNT(*),0), 0) AS avg_invoice
               FROM invoices
               WHERE DATE(created_at) BETWEEN DATE(?) AND DATE(?)""",
            (start.isoformat(), end.isoformat()),
        ).fetchone()

        daily = conn.execute(
            """SELECT DATE(created_at) AS d,
                      COALESCE(SUM(total),0) AS revenue,
                      COUNT(*) AS invoices
               FROM invoices
               WHERE DATE(created_at) BETWEEN DATE(?) AND DATE(?)
               GROUP BY DATE(created_at)
               ORDER BY d""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()

        by_category = conn.execute(
            """SELECT COALESCE(p.category, 'Unknown') AS category,
                      SUM(ii.quantity)   AS units,
                      SUM(ii.line_total) AS revenue
               FROM invoice_items ii
               JOIN invoices i ON i.id = ii.invoice_id
               LEFT JOIN products p ON p.id = ii.product_id
               WHERE DATE(i.created_at) BETWEEN DATE(?) AND DATE(?)
               GROUP BY category
               ORDER BY revenue DESC""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()

        top_products = conn.execute(
            """SELECT ii.product_name,
                      SUM(ii.quantity)   AS units,
                      SUM(ii.line_total) AS revenue
               FROM invoice_items ii
               JOIN invoices i ON i.id = ii.invoice_id
               WHERE DATE(i.created_at) BETWEEN DATE(?) AND DATE(?)
               GROUP BY ii.product_id, ii.product_name
               ORDER BY revenue DESC LIMIT 10""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()

        top_customers = conn.execute(
            """SELECT COALESCE(c.name, 'Walk-in') AS customer,
                      SUM(i.total)  AS revenue,
                      COUNT(*)      AS invoices
               FROM invoices i
               LEFT JOIN customers c ON c.id = i.customer_id
               WHERE DATE(i.created_at) BETWEEN DATE(?) AND DATE(?)
               GROUP BY i.customer_id, c.name
               ORDER BY revenue DESC LIMIT 10""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    finally:
        conn.close()

    return jsonify(
        success=True,
        start=start.isoformat(),
        end=end.isoformat(),
        summary={
            "revenue":     float(summary["revenue"] or 0),
            "invoices":    int(summary["invoices"] or 0),
            "avg_invoice": float(summary["avg_invoice"] or 0),
        },
        daily=[
            {"date": (r["d"].isoformat() if hasattr(r["d"], "isoformat") else str(r["d"])),
             "revenue": float(r["revenue"] or 0),
             "invoices": int(r["invoices"] or 0)}
            for r in daily
        ],
        by_category=[
            {"category": r["category"], "units": int(r["units"] or 0),
             "revenue": float(r["revenue"] or 0)}
            for r in by_category
        ],
        top_products=[
            {"product_name": r["product_name"], "units": int(r["units"] or 0),
             "revenue": float(r["revenue"] or 0)}
            for r in top_products
        ],
        top_customers=[
            {"customer": r["customer"], "revenue": float(r["revenue"] or 0),
             "invoices": int(r["invoices"] or 0)}
            for r in top_customers
        ],
    )


@app.get("/api/reports/export.csv")
@owner_or_admin_required
def api_reports_export():
    """Stream a CSV of every invoice in the date range."""
    today = dt.date.today()
    start = _parse_date(request.args.get("start"), today - dt.timedelta(days=29))
    end   = _parse_date(request.args.get("end"),   today)

    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT i.invoice_number, i.created_at, COALESCE(c.name,'Walk-in') AS customer,
                      i.subtotal, i.tax, i.total, i.status
               FROM invoices i
               LEFT JOIN customers c ON c.id = i.customer_id
               WHERE DATE(i.created_at) BETWEEN DATE(?) AND DATE(?)
               ORDER BY i.created_at""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    finally:
        conn.close()

    def gen():
        yield "Invoice,Date,Customer,Subtotal,Tax,Total,Status\n"
        for r in rows:
            ts = r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else ""
            # naive CSV escaping — wrap customer in quotes
            cust = (r["customer"] or "").replace('"', '""')
            yield (
                f'{r["invoice_number"]},{ts},"{cust}",'
                f'{float(r["subtotal"]):.2f},{float(r["tax"]):.2f},'
                f'{float(r["total"]):.2f},{r["status"]}\n'
            )

    fname = f"kasbpro_sales_{start.isoformat()}_to_{end.isoformat()}.csv"
    return Response(
        gen(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# System maintenance (owner only)
@app.post("/api/system/backup")
@owner_required
def api_backup():
    """Dump every table to a JSON snapshot inside ./backups/.

    SQLite let us copy the .db file with `shutil.copy2`, but MySQL stores
    data in the server's data directory which we usually can't reach from
    the app. A portable JSON dump works on every host & keeps Owners able
    to restore later if they want to.
    """
    backup_dir = os.path.join(HERE, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    fname = f"kasbpro_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    dest  = os.path.join(backup_dir, fname)

    conn = get_connection()
    try:
        snapshot = {}
        for t in ("users", "products", "customers", "suppliers",
                  "invoices", "invoice_items", "audit_log"):
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            snapshot[t] = [
                {k: (v.isoformat() if hasattr(v, "isoformat") else
                     float(v) if hasattr(v, "as_tuple") else v)
                 for k, v in row.items()}
                for row in rows
            ]
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, default=str)

        cur = conn.cursor()
        write_audit(cur, request.user, "BACKUP", "system", None, fname)
        conn.commit()
    finally:
        conn.close()

    return jsonify(success=True, file=fname)


@app.get("/api/users")
@owner_required
def api_users_list():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, full_name, email, role, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("created_at"):
            d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        out.append(d)
    return jsonify(success=True, users=out)


@app.delete("/api/users/<int:uid>")
@owner_required
def api_users_delete(uid):
    if uid == request.user["id"]:
        return jsonify(
            success=False,
            message="You cannot delete your own account while logged in",
        ), 400

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, full_name, email FROM users WHERE id = ?", (uid,)
        ).fetchone()
        if not existing:
            return jsonify(success=False, message="User not found"), 404

        cur = conn.cursor()
        write_audit(
            cur,
            request.user,
            "DELETE",
            "users",
            uid,
            f"Deleted user: {existing['email']}",
        )
        cur.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
        return jsonify(success=True)
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify(
            success=False,
            message="This user cannot be removed because they have invoice history",
        ), 409
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=str(e)), 400
    finally:
        conn.close()


@app.get("/api/audit-log")
@owner_required
def api_audit_log():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("created_at"):
            d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        out.append(d)
    return jsonify(success=True, log=out)


if __name__ == "__main__":
    # macOS reserves port 5000 for AirPlay Receiver, so we default to 5001.
    # Override with: PORT=8080 python app.py
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)
