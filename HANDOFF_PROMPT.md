# KasbPro — Context Handoff Prompt

Copy everything between the `=== BEGIN ===` and `=== END ===` lines into a fresh
Claude conversation on your Windows PC. That single message gives Claude the
full picture of the project, what's already built, what changed in our last
session, and where to pick up.

---

=== BEGIN ===

Hi Claude — I'm continuing work on my Final Year Project called **KasbPro**.
You won't have memory of our previous sessions, so I'm pasting the full
context below. Please read it carefully before suggesting any changes,
and ask me to confirm before you make any structural edits.

## 1. What KasbPro is

A Smart Business Management web app for small retail stores — basically a
lightweight POS + CRM + inventory + analytics tool. Built as a Final Year
Project at Government Jinnah Islamia Graduate College, Sialkot.

The functional requirements from my project report are FR-01 … FR-07:

| FR    | Feature                       |
|-------|-------------------------------|
| FR-01 | Role-based authentication (Admin / Owner) |
| FR-02 | Inventory Management          |
| FR-03 | Digital Billing (POS invoices) |
| FR-04 | Automated stock deduction on each sale |
| FR-05 | AI sales analytics + chat assistant |
| FR-06 | Customer CRM with loyalty tiers |
| FR-07 | System maintenance (backup, users, audit log) |

Plus two **new** modules added in the last session: **Suppliers** and
**Reports** (date-ranged sales analytics + CSV export).

## 2. Tech stack

- **Backend:** Python 3.10+ with Flask 3 (single `app.py`, ~30 REST routes).
- **Database:** MySQL 5.7+ / 8.x (or MariaDB 10.4+ — wire-compatible),
  accessed via PyMySQL. Used to be SQLite — fully migrated to MySQL.
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
├── app.py                  # Flask backend, all /api/* routes
├── database.py             # MySQL connection wrapper + schema (PyMySQL)
├── seed.py                 # Wipes & re-creates DB with dummy data
├── generate_sql_dump.py    # Generates kasbpro_dump.sql
├── kasbpro_dump.sql        # Ready-to-import SQL dump (schema + dummy data)
├── requirements.txt        # Flask, Werkzeug, PyMySQL
├── SETUP.md                # Run / install instructions
├── HANDOFF_PROMPT.md       # (this file)
├── common.js               # Shared auth guard, role gating, modal helpers, API client
│
│   ──── Public pages (pre-login) ────
├── 3main.html  3main.css  3main.js          # Landing page
├── 1sign.html  1sign.css  1sign.js          # Sign-up with role picker
├── 2login.html 2login.css 2login.js         # Login
├── 5forgot.html 5forgot.css 5forgot.js      # Forgot password
├── 6home.html  6home.css  6home.js          # About Us
│
│   ──── Protected pages (post-login) ────
├── dashboard.html  dashboard.css            # Dashboard (live stats + chart)
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
  `invoices.customer_id` is nullable with `ON DELETE SET NULL`.
  This makes deletes safe and preserves invoice history.
- Money columns are `DECIMAL(10,2)` / `DECIMAL(12,2)` (not floats).
- `audit_log` records every mutating action (CREATE / UPDATE / DELETE / ARCHIVE / BACKUP / SEED).

## 5. Connection settings

`database.py` reads these env vars, with local-dev defaults:

| Variable                 | Default     |
|--------------------------|-------------|
| `KASBPRO_MYSQL_HOST`     | `localhost` |
| `KASBPRO_MYSQL_PORT`     | `3306`      |
| `KASBPRO_MYSQL_USER`     | `root`      |
| `KASBPRO_MYSQL_PASSWORD` | *(empty)*   |
| `KASBPRO_MYSQL_DB`       | `kasbpro`   |

The database is auto-created on first run (`CREATE DATABASE IF NOT EXISTS`).

## 6. Demo credentials

| Role  | Email               | Password   | Powers                                        |
|-------|---------------------|------------|-----------------------------------------------|
| Admin | admin@kasbpro.com   | admin123   | Full CRUD, system backup, audit log           |
| Owner | owner@kasbpro.com   | owner123   | Read-only; sees a banner at the bottom of every protected page |

## 7. How to run on Windows

1. Install MySQL — I'm using XAMPP, so MySQL/MariaDB starts from the XAMPP
   Control Panel. Default user `root`, empty password.
2. Open phpMyAdmin → **Import** tab → choose `kasbpro_dump.sql` → click **Go**.
   That creates the `kasbpro` database with all tables + dummy data.
3. From a Command Prompt or PowerShell in the project folder:
   ```
   pip install -r requirements.txt
   python app.py
   ```
4. Visit <http://localhost:5001> and log in.
   (Port 5001 because macOS uses 5000 for AirPlay; works on Windows too.)

If I prefer Python over phpMyAdmin: `python seed.py` does the same thing.

## 8. What I asked for and what got built in the previous session

**Asks:**
1. Migrate from SQLite to MySQL — done.
2. Fix HTTP 500 error when clicking Delete in Product / Inventory /
   Customer / Billing — done (smart hard/soft delete).
3. Fix mobile responsiveness — horizontal scroll was disabled so right-side
   columns were hidden on phones — done.
4. Free to add more pages if they make the app more reliable / engaging —
   added Reports + Suppliers.

**Implementation summary:**

- **`database.py`** — rewritten with PyMySQL. Includes a small `_Conn` /
  `_Cursor` wrapper that mimics sqlite3's API and a `_q()` helper that
  translates SQLite-style `?` placeholders to MySQL `%s`, so most of
  `app.py` stayed close to the original. Schema is in `SCHEMA_STATEMENTS`
  (a list of CREATE TABLE statements). `ensure_database()` creates the
  `kasbpro` DB itself. `init_db()` runs on every Flask startup.
- **`app.py`** — same routes as before plus new endpoints:
  - `GET/POST/PUT/DELETE /api/suppliers` and `/api/suppliers/<sid>`
  - `GET /api/reports/sales` (returns summary, daily breakdown,
    by_category, top_products, top_customers)
  - `GET /api/reports/export.csv` (streams CSV)
  - The delete endpoints for products / customers now check for invoice
    references first — hard-delete if none, soft-delete (`is_deleted=1`)
    if any. This was the HTTP-500 fix.
  - Date functions use `DATE()` / `CURDATE()` (MySQL). The old
    `GROUP_CONCAT(a || ' x ' || b, ', ')` became
    `GROUP_CONCAT(CONCAT(a, ' x ', b) SEPARATOR ', ')`.
  - The system backup now writes a JSON snapshot of every table (because
    we can't `shutil.copy2` a MySQL data file like we could with SQLite).
- **`dashboard.css`** — new `.data-table-wrap` helper with
  `overflow-x: auto`, momentum scrolling, subtle scrollbar styling, and
  rounded corners that match the wrapping card. Tables in inventory /
  customers / billing / suppliers / reports got a `min-width: 720px` under
  992px viewport and `min-width: 680px` under 540px so columns stay
  legible while the wrapper handles horizontal swipe.
- **`inventory.html`, `customers.html`, `billing.html`** — replaced
  `<div class="card" style="margin-bottom: 0; overflow: hidden;">` with
  `<div class="card" ...><div class="data-table-wrap"><table>…` so the
  fix is applied.
- **`reports.html` (NEW)** — date pickers + Last 7/30/90 quick buttons,
  4 summary stat cards (Revenue, Invoices, Avg Invoice, Best Day), line
  chart for daily revenue, doughnut chart for by-category, two
  data-tables for top products / top customers, Export CSV button.
- **`suppliers.html` (NEW)** — supplier CRUD with the same look as the
  inventory / customers pages. Stats cards on top (Total, With Email,
  With Phone), search pill, Add Supplier modal with a textarea for Notes.
- **Sidebar nav** — every protected page now lists all 7 items in the
  same order: Dashboard · Inventory · Customers · Suppliers · Billing ·
  Reports · AI Assistant. Truck icon for Suppliers
  (`fa-truck`), file-chart-column for Reports.
- **`seed.py`** — updated to MySQL placeholder style and now also seeds
  5 suppliers. Uses `GREATEST(stock - ?, 0)` instead of SQLite's
  `MAX(stock - ?, 0)`.
- **`kasbpro_dump.sql` (NEW, 38 KB)** — full schema + dummy data
  (2 users, 25 products, 5 suppliers, 15 customers, 120 invoices, 359
  line items, 25 stock-adjust updates, 15 customer-rollup updates). Import
  via phpMyAdmin / Workbench / `mysql` CLI.
- **`generate_sql_dump.py` (NEW)** — script that produced the dump above.
  Run it again any time we change the seed data.

## 9. Notable code patterns I want you to keep using

- **All UI text and toasts go through `kasbpro_toast(message, kind)`**
  defined in `common.js`. Kinds: `info`, `ok`, `err`, `warn`.
- **Confirm modals go through `kasbpro_confirm(message)`** which returns
  a promise resolving to `true`/`false`.
- **Form modals go through `kasbpro_modal({title, fields, submit, initial})`**.
  Field types: `text`, `number`, `email`, `select` (with `options`),
  `textarea`. The promise resolves to the form values or `null` on cancel.
- **Role gating** — on every protected page, the inline `<script>` block
  calls `kasbpro_hydrateSession()` first, bails to login if not auth'd,
  then `kasbpro_applyRoleUI()` which hides/disables anything with a
  `data-perm="canCreate|canEdit|canDelete"` or `data-role="admin|owner"`
  attribute that the current role can't use.
- **API calls** — always use `await api('/api/path', { method, body })`.
  It handles JSON, 401 redirects, and error toasts.

## 10. Open / nice-to-have items (not done yet)

These didn't come up explicitly but would round out the project if you
suggest them:

- Audit-log viewer page (the backend `/api/audit-log` already exists,
  no UI for it yet).
- User management page (the backend `/api/users` exists, no UI).
- Bulk product import via CSV upload.
- Email/SMS receipt sending from the POS modal.
- "Restore deleted" view for soft-deleted products/customers.
- Real authentication for the AI assistant (currently rule-based).

## 11. Things to be careful of

- The folder still contains some older legacy files at the *workspace
  root* called `1sign.html`, `2login.html`, etc. with **different
  content** than the ones in this project — they were uploaded earlier
  as references. The ones in this project's folder are the canonical
  versions; don't accidentally diff against the others.
- Don't reintroduce the old `overflow: hidden;` style on table cards —
  that was the mobile-scroll bug.
- Keep the soft-delete behaviour. Never just `DELETE FROM products WHERE
  id = ?` without first checking for invoice references — that's what
  triggered the original HTTP 500.
- All money values are `DECIMAL` in DB; PyMySQL returns them as
  `decimal.Decimal`. We cast to `float()` before `jsonify`.

Please confirm you've read this, and then tell me what you'd like to
work on first. My current todo list is in the "Open items" section above.

=== END ===
