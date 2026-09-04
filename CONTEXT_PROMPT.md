Copy everything between the two `=====` lines below into a new Claude chat
on your Windows PC. Before pasting, edit the **Folder path** line to point
at wherever you've placed the project on Windows (e.g. `C:\Users\Saad\Documents\Final Year Project`).

Hi Claude — I'm Muhammad Saad (call me Buddy). I'm continuing a Final Year
Project called **KasbPro**. You have no memory of our previous sessions, so
this message contains everything you need. Please read it fully, confirm
you've understood, and ask before making any structural changes.

## 0. Where the project lives

- **Folder path (mac, where it was last edited):** `/Users/saad/Documents/Documents/Final Year Project`
- **Folder path (Windows, where we're working now):** `<EDIT THIS — e.g. C:\Users\Saad\Documents\Final Year Project>`

Please open / mount that folder before doing anything else, so you can
read and edit the files directly.

## 1. What KasbPro is

A Smart Business Management web app for small retail stores — basically a
lightweight POS + CRM + inventory + analytics tool. Built as my Final Year
Project at Government Jinnah Islamia Graduate College, Sialkot.

The functional requirements from my project report are FR-01 … FR-07:

| FR    | Feature                                              |
|-------|------------------------------------------------------|
| FR-01 | Role-based authentication (Admin / Owner)            |
| FR-02 | Inventory Management                                 |
| FR-03 | Digital Billing (POS invoices)                       |
| FR-04 | Automated stock deduction on each sale               |
| FR-05 | AI sales analytics + chat assistant                  |
| FR-06 | Customer CRM with loyalty tiers (Bronze/Silver/Gold) |
| FR-07 | System maintenance (backup, users, audit log)        |

Plus two **new** modules added in the last session: **Suppliers** and
**Reports** (date-ranged sales analytics + CSV export).

## 2. Tech stack

- **Backend:** Python 3.10+ with Flask 3 (single `app.py`, ~30 REST routes).
- **Database:** MySQL 5.7+ / 8.x (or MariaDB 10.4+ which is wire-compatible),
  accessed via PyMySQL. It used to be SQLite — fully migrated to MySQL.
- **Frontend:** Vanilla HTML + CSS + JavaScript, no build step.
  Chart.js loaded from CDN. Font Awesome icons. Plus Jakarta Sans font.
- **Auth:** Flask sessions (cookie), password hashing via Werkzeug.
- **Theme colors:** Primary blue `#2563eb`, dark blue `#1e3a8a`,
  green `#10b981`, off-white background `#f4f7fe`, cards `white` with
  18 px radius and subtle shadow.

## 3. Project folder layout

Every file sits in one folder (no subdirectories — easy to deploy):

```
Final Year Project/
├── app.py                  # Flask backend, all /api/* routes (~800 lines)
├── database.py             # MySQL connection wrapper + schema (PyMySQL)
├── seed.py                 # Wipes & re-creates DB with dummy data
├── generate_sql_dump.py    # Script that produces kasbpro_dump.sql
├── kasbpro_dump.sql        # Ready-to-import SQL dump (~38 KB, schema + data)
├── requirements.txt        # Flask, Werkzeug, PyMySQL
├── SETUP.md                # End-user install instructions
├── HANDOFF_PROMPT.md       # Earlier/longer version of this prompt
├── CONTEXT_PROMPT.md       # (this file)
├── common.js               # Shared auth guard, role gating, modals, API client
│
│   ──── Public pages (pre-login) ────
├── 3main.html  3main.css  3main.js          # Landing page
├── 1sign.html  1sign.css  1sign.js          # Sign-up with role picker
├── 2login.html 2login.css 2login.js         # Login
├── 5forgot.html 5forgot.css 5forgot.js      # Forgot password
├── 6home.html  6home.css  6home.js          # About Us
│
│   ──── Protected pages (post-login) ────
├── dashboard.html  dashboard.css            # Dashboard (stats + chart)
├── inventory.html                           # Inventory CRUD
├── customers.html                           # Customer CRM
├── suppliers.html                           # Vendor CRUD (NEW)
├── billing.html                             # POS + invoice history
├── reports.html                             # Date-range reports + CSV (NEW)
├── ai-assistant.html                        # Rule-based AI chat
└── 4graph.html  4graph.js                   # Legacy chart helper
```

`dashboard.css` is the **shared** stylesheet for every protected page.

## 4. Database schema (MySQL, InnoDB, utf8mb4)

Tables: `users`, `products`, `customers`, `suppliers`, `invoices`,
`invoice_items`, `audit_log`.

Key design notes:
- `products` and `customers` have an `is_deleted TINYINT(1)` column for
  **soft delete**. All list queries filter `WHERE is_deleted = 0`.
- `invoice_items.product_id` is nullable with `ON DELETE SET NULL`, and
  `invoices.customer_id` is nullable with `ON DELETE SET NULL`. That
  makes deletes safe and preserves historical invoice line items.
- Money columns are `DECIMAL(10,2)` / `DECIMAL(12,2)` — not floats.
- `audit_log` records every mutating action: CREATE / UPDATE / DELETE /
  ARCHIVE / BACKUP / SEED.

## 5. Connection settings

`database.py` reads these env vars, with local-dev defaults that match a
typical XAMPP setup:

| Variable                 | Default     |
|--------------------------|-------------|
| `KASBPRO_MYSQL_HOST`     | `localhost` |
| `KASBPRO_MYSQL_PORT`     | `3306`      |
| `KASBPRO_MYSQL_USER`     | `root`      |
| `KASBPRO_MYSQL_PASSWORD` | *(empty)*   |
| `KASBPRO_MYSQL_DB`       | `kasbpro`   |

The database is auto-created on first run via `CREATE DATABASE IF NOT EXISTS`.

## 6. Demo credentials

| Role  | Email               | Password   | Powers                                            |
|-------|---------------------|------------|---------------------------------------------------|
| Admin | admin@kasbpro.com   | admin123   | Full CRUD, system backup, audit log               |
| Owner | owner@kasbpro.com   | owner123   | Read-only; sees a banner at the bottom of pages   |

## 7. How to run on Windows

1. Install MySQL — easiest path is XAMPP, which starts MariaDB from the
   XAMPP Control Panel. Default user `root`, empty password.
2. Open <http://localhost/phpmyadmin> → **Import** tab → choose
   `kasbpro_dump.sql` (already in the project folder) → click **Go**.
   That creates the `kasbpro` database with all tables + dummy data.
3. From a Command Prompt or PowerShell in the project folder:
   ```
   pip install -r requirements.txt
   python app.py
   ```
4. Visit <http://localhost:5001> and log in with the admin credentials.

Alternative to step 2: `python seed.py` does the same thing through
Python (useful if phpMyAdmin isn't available).

## 8. What's already built and working

End-to-end CRUD across all modules. Specifically:

- **Login / Signup / Forgot** — front-end + back-end via `/api/auth/*`.
- **Dashboard** — live stats from `/api/dashboard/stats` (today's sales,
  est. profit, customers today, inventory value), 7-day revenue line
  chart, low-stock alert list, recent sales table, admin-only Quick
  Actions panel + Run Backup link.
- **Inventory** — 25 seeded products. Search, Add, Edit, Delete
  (smart hard/soft based on invoice references). Status pills (In stock /
  Low stock / Out of stock) derived from `stock` vs `low_stock_threshold`.
- **Customers** — 15 seeded customers. CRUD + loyalty tier pills.
- **Suppliers** (NEW) — 5 seeded vendors. CRUD with a Notes textarea.
- **Billing** — 120 seeded invoices over the last 30 days. POS modal
  (`openPOS()`) lets you build a cart, picks a customer (or walk-in),
  generates an invoice atomically inside a MySQL transaction that
  deducts stock and bumps customer totals + loyalty tier.
- **Reports** (NEW) — date pickers + Last 7/30/90 quick buttons, 4
  summary stat cards (Revenue, Invoices, Avg Invoice, Best Day), line
  chart for daily revenue, doughnut chart for sales by category, top
  products + top customers tables, working CSV export.
- **AI Assistant** — rule-based chat (today's sales / low stock / top
  sellers / business summary / customer visits). Real data, real SQL.

## 9. Code patterns I want you to keep using

- **Toasts:** `kasbpro_toast(message, kind)` — kinds: `info` `ok` `err` `warn`.
- **Confirm dialog:** `await kasbpro_confirm(message)` — returns boolean.
- **Form modal:** `await kasbpro_modal({title, fields, submit, initial})`.
  Field types: `text` `number` `email` `select` (needs `options`) `textarea`.
  Returns the values object or `null` on cancel.
- **Role gating:** put `data-perm="canCreate|canEdit|canDelete"` or
  `data-role="admin|owner"` on any element. `kasbpro_applyRoleUI()` will
  hide or disable it based on the logged-in role. Call it on
  DOMContentLoaded and after any DOM injection.
- **API calls:** `await api('/api/path', { method, body })`. It handles
  JSON, 401 redirects to login, and error throwing.
- **Boot block** in every protected page's inline `<script>`:
  ```js
  (async () => {
      const ok = await kasbpro_hydrateSession();
      if (!ok) return kasbpro_requireAuth();
      kasbpro_applyRoleUI();
      // … page-specific setup
  })();
  ```

## 10. What changed in the previous session (full delta)

**Asks I had:**
1. Migrate from SQLite to MySQL — **done**.
2. Fix HTTP 500 when deleting products / customers / billing rows — **done**.
3. Fix mobile responsiveness — horizontal scroll was disabled so
   right-side columns were hidden on phones — **done**.
4. Free to add more pages if they make the app more reliable / engaging — **added Reports + Suppliers**.

**Implementation summary of those changes:**

- **`database.py`** — rewritten with PyMySQL. Includes a small `_Conn` /
  `_Cursor` wrapper that mimics sqlite3's API and a `_q()` helper that
  translates SQLite-style `?` placeholders to MySQL `%s`, so most of
  `app.py` stayed close to the original SQLite version. Schema is in
  `SCHEMA_STATEMENTS` (list of CREATE TABLE statements).
  `ensure_database()` creates the `kasbpro` DB itself. `init_db()` runs
  on every Flask startup.
- **`app.py`** — same routes as before plus new endpoints:
  - `GET/POST/PUT/DELETE /api/suppliers` and `/api/suppliers/<sid>`
  - `GET /api/reports/sales` (returns `summary`, `daily`, `by_category`,
    `top_products`, `top_customers`)
  - `GET /api/reports/export.csv` (streams CSV)
  - Delete endpoints for products / customers now check `COUNT(*) FROM
    invoice_items WHERE product_id = ?` (or `FROM invoices WHERE customer_id`)
    first. Hard-delete if zero refs, soft-delete (`is_deleted=1`) if
    any. **This was the HTTP-500 fix.**
  - Date functions use `DATE()` / `CURDATE()` (MySQL). The old
    `GROUP_CONCAT(a || ' x ' || b, ', ')` became
    `GROUP_CONCAT(CONCAT(a, ' x ', b) SEPARATOR ', ')`.
  - System backup writes a JSON snapshot of every table (we can't
    `shutil.copy2` a MySQL data file like we could with SQLite).
  - `decimal.Decimal` values returned by PyMySQL are cast to `float()`
    before `jsonify`.
- **`dashboard.css`** — new `.data-table-wrap` helper with
  `overflow-x: auto`, momentum scrolling, subtle scrollbar, rounded
  corners. Tables in inventory/customers/billing/suppliers/reports got
  `min-width: 720px` under 992px viewport and `min-width: 680px` under
  540px so columns stay legible while the wrapper handles horizontal
  swipe.
- **`inventory.html`, `customers.html`, `billing.html`** — replaced
  `<div class="card" style="margin-bottom: 0; overflow: hidden;">`
  with `<div class="card" ...><div class="data-table-wrap"><table>…`.
- **`reports.html` (NEW)** — full Reports page (see above).
- **`suppliers.html` (NEW)** — Suppliers page with same look as
  inventory / customers.
- **Sidebar nav** — every protected page lists all 7 items in the same
  order: Dashboard · Inventory · Customers · Suppliers · Billing ·
  Reports · AI Assistant. Truck icon for Suppliers (`fa-truck`),
  file-chart-column for Reports.
- **`seed.py`** — updated to MySQL placeholder style, also seeds 5
  suppliers. Uses `GREATEST(stock - ?, 0)` instead of SQLite's
  `MAX(stock - ?, 0)`.
- **`kasbpro_dump.sql` (NEW, 38 KB)** — full schema + dummy data
  (2 users, 25 products, 5 suppliers, 15 customers, 120 invoices, 359
  line items, 25 stock-adjust updates, 15 customer-rollup updates).
  Import via phpMyAdmin / Workbench / `mysql` CLI.
- **`generate_sql_dump.py` (NEW)** — script that produced the dump
  above. Re-run any time we change the seed data.

## 11. Open / nice-to-have items (not done yet)

Suggest these to me if you think they fit the project:

- Audit-log viewer page (`/api/audit-log` exists, no UI yet).
- User management page (`/api/users` exists, no UI yet).
- Bulk product import via CSV upload.
- Email/SMS receipt sending from the POS modal.
- "Restore deleted" view for soft-deleted products/customers.
- Real LLM-backed AI assistant (currently rule-based).
- Print-friendly invoice receipt view.

## 12. Things to be careful of

- The folder may still contain some older legacy uploads with names
  like `1sign.html`, `2login.html` etc. that look similar but are
  **different content** — they were uploaded as references. The ones
  inside the actual project folder are the canonical versions; don't
  diff against the others.
- Don't reintroduce `overflow: hidden;` on table cards — that was the
  mobile-scroll bug.
- Keep the soft-delete behaviour. Never just `DELETE FROM products
  WHERE id = ?` without first checking invoice references — that was
  what caused the original HTTP 500.
- All money values are `DECIMAL` in DB; PyMySQL returns them as
  `decimal.Decimal`. Cast to `float()` before `jsonify`.
- Port is `5001` (not 5000) because macOS reserves 5000 for AirPlay.
  Override with `PORT=8080 python app.py` if needed.

Please confirm you've read this, list the files you can see in the
project folder, and then ask what I'd like to work on first.

