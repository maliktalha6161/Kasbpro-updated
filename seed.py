"""
KasbPro · seed.py
Wipes & re-creates the MySQL database with realistic dummy data so the
dashboard, charts and reports all have signal at first launch.

Run:  python seed.py
"""

import random
import datetime as dt
from werkzeug.security import generate_password_hash

from database import reset_db, get_connection


# Reference data
PRODUCTS = [
    # name, sku, category, price, starting_stock, low_threshold
    ("Milk (1L)",          "SKU-MILK-1L",   "Dairy",      2.50, 180, 15),
    ("Yogurt (500g)",      "SKU-YOG-500",   "Dairy",      1.80, 120, 10),
    ("Cheese Block (200g)","SKU-CHZ-200",   "Dairy",      4.20,  90,  8),
    ("Eggs (dozen)",       "SKU-EGG-12",    "Dairy",      3.20,  80, 12),

    ("Bread Loaf",         "SKU-BRD-LOAF",  "Bakery",     1.80, 140, 12),
    ("Buns (pack of 6)",   "SKU-BUN-6",     "Bakery",     2.10, 100, 10),

    ("Sugar (1kg)",        "SKU-SUG-1KG",   "Pantry",     1.20,  80, 15),
    ("Wheat Flour (10kg)", "SKU-WFL-10K",   "Pantry",     8.50,  90, 10),
    ("Rice (5kg)",         "SKU-RIC-5K",    "Pantry",     9.80, 130, 10),
    ("Cooking Oil (5L)",   "SKU-OIL-5L",    "Pantry",    12.00, 100, 10),
    ("Salt (1kg)",         "SKU-SLT-1K",    "Pantry",     0.80, 160, 20),
    ("Tea (250g)",         "SKU-TEA-250",   "Pantry",     3.40, 130, 15),
    ("Coffee (200g)",      "SKU-COF-200",   "Pantry",     5.60,  90, 10),
    ("Lentils (1kg)",      "SKU-LEN-1K",    "Pantry",     2.20, 140, 15),

    ("Soap Bar",           "SKU-SOAP-BAR",  "Household",  0.95, 150, 20),
    ("Detergent (1kg)",    "SKU-DET-1K",    "Household",  3.50,  90, 10),
    ("Shampoo (250ml)",    "SKU-SHM-250",   "Household",  4.20, 110, 10),
    ("Toothpaste (100g)",  "SKU-TPT-100",   "Household",  1.90, 120, 15),

    ("Coca-Cola (1.5L)",   "SKU-COK-1.5",   "Beverages",  1.50, 170, 20),
    ("Mineral Water (1L)", "SKU-WTR-1L",    "Beverages",  0.60, 220, 30),
    ("Juice Pack (1L)",    "SKU-JUC-1L",    "Beverages",  2.00, 130, 15),

    ("Biscuits (pack)",    "SKU-BIS-PK",    "Snacks",     1.10, 200, 25),
    ("Chips (large)",      "SKU-CHP-LG",    "Snacks",     1.40, 150, 20),
    ("Chocolate Bar",      "SKU-CHC-BR",    "Snacks",     0.90, 230, 30),
    ("Cookies (200g)",     "SKU-CKE-200",   "Snacks",     1.70, 140, 15),
]


CUSTOMERS = [
    ("Sarah Lee",     "+92 300 1234567", "sarah.lee@example.com"),
    ("Michael Chen",  "+92 321 7654321", "m.chen@example.com"),
    ("Aisha Khan",    "+92 333 9876543", "aisha.k@example.com"),
    ("Ahmed Raza",    "+92 345 5556677", None),
    ("Fatima Noor",   "+92 312 1112223", "fatima@example.com"),
    ("Ali Hassan",    "+92 301 8889990", None),
    ("Zara Sheikh",   "+92 322 4445556", "zara.s@example.com"),
    ("Bilal Ahmed",   "+92 304 7778881", None),
    ("Hira Malik",    "+92 313 9990001", "hira.m@example.com"),
    ("Usman Tariq",   "+92 346 2223334", None),
    ("Saima Aslam",   "+92 311 5556668", "saima@example.com"),
    ("Imran Akhtar",  "+92 323 8881112", None),
    ("Nadia Iqbal",   "+92 305 3334445", "nadia.i@example.com"),
    ("Tariq Mahmood", "+92 308 6667778", None),
    ("Sana Yousaf",   "+92 314 1110002", "sana@example.com"),
]


SUPPLIERS = [
    ("Sunrise Dairy Co.",   "Mr. Hamza",  "+92 300 1112233", "orders@sunrisedairy.com",
     "Plot 17, Industrial Estate, Lahore",
     "Primary dairy supplier — weekly Tuesday delivery."),
    ("Punjab Grain Mills",  "Ms. Anum",   "+92 322 4445566", "sales@punjabgrains.pk",
     "Mill Road, Faisalabad",
     "Rice, wheat flour, lentils. Net-30 terms."),
    ("Hashmi Beverages",    "Mr. Kashif", "+92 311 9876543", "kashif@hashmibev.com",
     "Korangi, Karachi",
     "Soft drinks, juice, mineral water."),
    ("Crispy Snacks Ltd.",  "Mr. Tariq",  "+92 345 1234567", "info@crispysnacks.com",
     "I-9 Industrial Area, Islamabad",
     "Biscuits, chips, cookies."),
    ("Cleanwave Household", "Ms. Sehrish","+92 333 2223344", "orders@cleanwave.pk",
     "SITE Area, Karachi",
     "Soaps, detergent, shampoo, toothpaste."),
]


def _loyalty(total):
    if total >= 1000:
        return "Gold"
    if total >= 300:
        return "Silver"
    return "Bronze"


def seed():
    reset_db()
    conn = get_connection()
    cur = conn.cursor()

    # Users
    cur.execute(
        "INSERT INTO users (full_name, email, password_hash, role) VALUES (?,?,?,?)",
        ("Farhan Asif", "admin@kasbpro.com",
         generate_password_hash("admin123"), "admin"),
    )
    admin_id = cur.lastrowid

    cur.execute(
        "INSERT INTO users (full_name, email, password_hash, role) VALUES (?,?,?,?)",
        ("Muhammad Saad", "owner@kasbpro.com",
         generate_password_hash("owner123"), "owner"),
    )

    # Categories
    category_names = sorted({category for _, _, category, _, _, _ in PRODUCTS} | {"Other"})
    for category in category_names:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (category,))

    # Products
    for name, sku, cat, price, stock, low in PRODUCTS:
        cur.execute(
            """INSERT INTO products
               (name, sku, category, price, stock, low_stock_threshold)
               VALUES (?,?,?,?,?,?)""",
            (name, sku, cat, price, stock, low),
        )

    # Suppliers
    for name, contact, phone, email, address, notes in SUPPLIERS:
        cur.execute(
            """INSERT INTO suppliers (name, contact, phone, email, address, notes)
               VALUES (?,?,?,?,?,?)""",
            (name, contact, phone, email, address, notes),
        )

    # Customers
    customer_ids = []
    for name, phone, email in CUSTOMERS:
        cur.execute(
            "INSERT INTO customers (name, phone, email) VALUES (?,?,?)",
            (name, phone, email),
        )
        customer_ids.append(cur.lastrowid)

    # Invoices over the last 30 days
    all_products = cur.execute(
        "SELECT id, name, price FROM products"
    ).fetchall()

    rng = random.Random(42)                       # deterministic seed

    for days_ago in range(29, -1, -1):
        weekday = (dt.date.today() - dt.timedelta(days=days_ago)).weekday()
        n_invoices = rng.randint(2, 5) if weekday < 5 else rng.randint(4, 7)

        for _ in range(n_invoices):
            ts = (dt.datetime.now() - dt.timedelta(
                days=days_ago,
                hours=rng.randint(0, 12),
                minutes=rng.randint(0, 59),
            )).strftime("%Y-%m-%d %H:%M:%S")

            cid = rng.choice(customer_ids) if rng.random() < 0.85 else None
            n_items = rng.randint(1, 5)
            picks = rng.sample(all_products, k=n_items)

            subtotal = 0.0
            items = []
            for p in picks:
                qty = rng.randint(1, 4)
                price = float(p["price"])
                lt = round(price * qty, 2)
                subtotal += lt
                items.append((p["id"], p["name"], qty, price, lt))

            total = round(subtotal, 2)
            inv_no = f"INV-{ts.replace(' ', '').replace('-','').replace(':','')[:15]}-{rng.randint(10,99)}"

            cur.execute(
                """INSERT INTO invoices
                     (invoice_number, customer_id, subtotal, tax, total,
                      status, created_by, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (inv_no, cid, subtotal, 0.0, total, "Paid", admin_id, ts),
            )
            iid = cur.lastrowid
            for (pid, pname, qty, price, lt) in items:
                cur.execute(
                    """INSERT INTO invoice_items
                         (invoice_id, product_id, product_name, quantity,
                          unit_price, line_total)
                       VALUES (?,?,?,?,?,?)""",
                    (iid, pid, pname, qty, price, lt),
                )
                # Deduct stock — but stop at zero
                cur.execute(
                    "UPDATE products SET stock = GREATEST(stock - ?, 0) WHERE id = ?",
                    (qty, pid),
                )

            if cid:
                cur.execute(
                    """UPDATE customers SET
                         total_purchases = total_purchases + ?,
                         visit_count     = visit_count + 1,
                         last_visit      = ?
                       WHERE id = ?""",
                    (total, ts, cid),
                )

    # Recompute loyalty tiers
    for row in cur.execute("SELECT id, total_purchases FROM customers").fetchall():
        cur.execute(
            "UPDATE customers SET loyalty_tier = ? WHERE id = ?",
            (_loyalty(float(row["total_purchases"])), row["id"]),
        )

    # Force a few items to low/out-of-stock so dashboard widgets have signal
    cur.execute("UPDATE products SET stock = 5  WHERE name = 'Sugar (1kg)'")
    cur.execute("UPDATE products SET stock = 8  WHERE name = 'Eggs (dozen)'")
    cur.execute("UPDATE products SET stock = 12 WHERE name = 'Wheat Flour (10kg)'")
    cur.execute("UPDATE products SET stock = 0  WHERE name = 'Soap Bar'")
    cur.execute("UPDATE products SET stock = 0  WHERE name = 'Cheese Block (200g)'")

    # Audit row
    cur.execute(
        """INSERT INTO audit_log (user_id, user_email, action, table_name, details)
           VALUES (?,?,?,?,?)""",
        (admin_id, "admin@kasbpro.com", "SEED", "system", "Database seeded"),
    )

    conn.commit()
    conn.close()

    print("✓ Database seeded.")
    print("  Users:")
    print("    admin@kasbpro.com / admin123  (admin)")
    print("    owner@kasbpro.com / owner123  (owner)")


if __name__ == "__main__":
    seed()
