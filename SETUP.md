# KasbPro — Setup & Run

Smart Business Management for Retail Stores.
Final Year Project — Government Jinnah Islamia Graduate College, Sialkot.

The stack is **Python + Flask + MySQL**. This guide walks you through running it on Windows, macOS, Linux or WSL/Ubuntu.

---

## 1. Prerequisites

* Python 3.10 or newer
* `pip` (ships with Python)
* **MySQL Server 5.7+ or MySQL 8.x** (or MariaDB 10.4+, which is wire-compatible)

Verify:

```
python --version
pip --version
mysql --version
```

### Installing MySQL

* **Windows** — Download the MySQL Installer from <https://dev.mysql.com/downloads/installer/>. Pick "MySQL Server" + "MySQL Workbench" during setup.
* **macOS** — `brew install mysql` then `brew services start mysql`.
* **Ubuntu / WSL** — `sudo apt update && sudo apt install -y mysql-server` then `sudo service mysql start`.
* **XAMPP users** — XAMPP ships MariaDB; just start the "MySQL" module from the XAMPP control panel and you're good.

After install, make sure the server is running and you can connect:

```
mysql -u root -p
```

---

## 2. Install Python deps

From the project folder (the one containing `app.py`):

```
pip install -r requirements.txt
```

That installs `Flask`, `Werkzeug` and `PyMySQL`.

If you prefer an isolated virtual environment (recommended):

```
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

---

## 3. Configure database credentials

KasbPro reads connection settings from environment variables. All have sensible local-dev defaults so on a typical XAMPP setup you don't have to set anything.

| Variable                  | Default     | What it is                              |
| ------------------------- | ----------- | --------------------------------------- |
| `KASBPRO_MYSQL_HOST`      | `localhost` | DB host                                 |
| `KASBPRO_MYSQL_PORT`      | `3306`      | DB port                                 |
| `KASBPRO_MYSQL_USER`      | `root`      | DB user                                 |
| `KASBPRO_MYSQL_PASSWORD`  | *(empty)*   | DB password                             |
| `KASBPRO_MYSQL_DB`        | `kasbpro`   | Database name (auto-created if missing) |

Setting them:

* **macOS / Linux / WSL** — `export KASBPRO_MYSQL_PASSWORD=mysecret`
* **Windows (cmd)**      — `set KASBPRO_MYSQL_PASSWORD=mysecret`
* **Windows (PowerShell)** — `$env:KASBPRO_MYSQL_PASSWORD = "mysecret"`

You do **not** need to create the `kasbpro` database manually — `database.py` will create it on first run.

---

## 4. Seed the database with dummy data

You have **two options** — pick whichever feels easier:

### Option A — Import the ready-made SQL dump (fastest)

The file `kasbpro_dump.sql` already contains the full schema **and** ~640 lines of dummy data. No Python required.

* **phpMyAdmin (XAMPP, MAMP, Laragon)** — Open <http://localhost/phpmyadmin>, click the **Import** tab in the top bar, choose `kasbpro_dump.sql`, scroll down and click **Go**.
* **MySQL Workbench** — *Server → Data Import → Import from Self-Contained File*, pick `kasbpro_dump.sql`, target schema = `kasbpro`, *Start Import*.
* **CLI** — from the project folder:
  ```
  mysql -u root -p < kasbpro_dump.sql
  ```

### Option B — Run the Python seeder

```
python seed.py
```

Both options give you exactly the same data:

* **2 users** — one Admin, one Owner
* **25 products** across 6 categories
* **5 suppliers** (vendor contacts for the new Suppliers page)
* **15 customers** with phone numbers
* **120 invoices** with 359 line items spread over the last 30 days so analytics charts have signal
* A handful of items pre-set as Low-stock or Out-of-stock so the dashboard widgets show real alerts

Re-running either step is **destructive** — it drops and recreates everything.

---

## 5. Run the server

```
python app.py
```

Open <http://localhost:5001> in your browser. (macOS reserves port 5000 for AirPlay Receiver, so KasbPro defaults to 5001. Override with `PORT=8080 python app.py`.)

---

## 6. Demo credentials

| Role  | Email               | Password |
| ----- | ------------------- | -------- |
| Admin | admin@kasbpro.com   | admin123 |
| Owner | owner@kasbpro.com   | owner123 |

* **Admin** can add, edit and delete inventory, customers, suppliers and invoices, trigger system backups, and view the audit log.
* **Owner** is read-only. Every Add/Edit/Delete control is hidden, and a "Read-only mode" banner sits at the bottom of the screen.

---

## 7. What's implemented

| FR    | Feature                  | Endpoint(s)                                                              |
| ----- | ------------------------ | ------------------------------------------------------------------------ |
| FR-01 | Role-based Authentication| `POST /api/auth/register`, `/login`, `/logout`, `GET /api/auth/me`       |
| FR-02 | Inventory Management     | `GET/POST/PUT/DELETE /api/products`                                      |
| FR-03 | Digital Billing (POS)    | `POST /api/invoices`, `GET /api/invoices`, `GET /api/invoices/<id>`      |
| FR-04 | Automated Stock Update   | Stock is deducted atomically inside the `POST /api/invoices` transaction |
| FR-05 | AI Sales Analytics       | `GET /api/dashboard/stats`, `/api/analytics/top-sellers`, `/api/ai/chat` |
| FR-06 | Customer CRM             | `GET/POST/PUT/DELETE /api/customers` (loyalty tier auto-computed)        |
| FR-07 | System Maintenance       | `POST /api/system/backup`, `GET /api/users`, `GET /api/audit-log`        |
| NEW   | Suppliers                | `GET/POST/PUT/DELETE /api/suppliers`                                     |
| NEW   | Reports & CSV export     | `GET /api/reports/sales`, `GET /api/reports/export.csv`                  |

Every mutating API call writes to the `audit_log` table so an Admin can later see who did what (FR-07).

---

## 8. What changed in this revision

1. **SQLite → MySQL.** `database.py` now talks to a MySQL server via PyMySQL. A thin wrapper translates SQLite-style `?` placeholders to MySQL `%s` so the rest of the codebase stays close to the original.
2. **Delete bug fixed.** Deleting a product/customer that had historical invoice references previously crashed with HTTP 500 because of a foreign-key violation. The DELETE handlers now intelligently hard-delete if no references exist or soft-delete (`is_deleted = 1`) if they do — the user always sees a successful delete, and historical reports stay intact.
3. **Mobile horizontal scroll restored.** Tables on Inventory / Customers / Billing / Suppliers / Reports are now wrapped in `.data-table-wrap` with `overflow-x: auto` and a 720 px `min-width` so all columns stay readable on phones.
4. **Two new pages.** Reports (date-ranged sales analytics, trend chart, category breakdown, top products/customers, CSV export) and Suppliers (vendor CRUD).
5. **Sidebar updated everywhere** so all seven nav items appear consistently.

---

## 9. Project layout

```
outputs/
├── app.py             # Flask back-end (all /api/* routes)
├── database.py        # MySQL connection + schema (PyMySQL)
├── seed.py            # Wipes & re-creates DB with dummy data
├── requirements.txt
├── SETUP.md           # ← you are here
├── backups/           # Generated by FR-07 backup endpoint
│
├── common.js          # Shared auth guard, role gating, modal helpers, HTTP client
│
├── 3main.html  3main.css  3main.js          # Public landing
├── 1sign.html  1sign.css  1sign.js          # Sign-up with role picker
├── 2login.html 2login.css 2login.js         # Login
├── 5forgot.html 5forgot.css 5forgot.js      # Forgot password
├── 6home.html  6home.css  6home.js          # About Us (public)
│
├── dashboard.html  dashboard.css            # Dashboard (live stats + chart)
├── inventory.html                           # Inventory CRUD
├── customers.html                           # Customer CRM
├── suppliers.html                           # Suppliers CRUD (NEW)
├── billing.html                             # POS + invoice history
├── reports.html                             # Date-ranged reports + CSV (NEW)
├── ai-assistant.html                        # AI chat
└── 4graph.html  4graph.js                   # Legacy chart helper
```

---

## 10. Production deployment

The Flask dev server is fine for evaluation. For production use a proper WSGI host:

```
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

…and put nginx in front. Be sure to set:

* `KASBPRO_SECRET=<random hex>` so the Flask session cookie is signed properly
* `KASBPRO_MYSQL_HOST/USER/PASSWORD/DB` so the app reaches the real DB

---

## 11. Resetting / troubleshooting

| Symptom                                       | Fix                                                              |
| --------------------------------------------- | ---------------------------------------------------------------- |
| `Access denied for user 'root'@'localhost'`   | Wrong password — set `KASBPRO_MYSQL_PASSWORD`                    |
| `Can't connect to MySQL server`               | MySQL isn't running. Start it (XAMPP control panel / brew / svc) |
| "Invalid credentials" at login                | You haven't seeded — run `python seed.py`                        |
| Dashboard shows zeros                         | Same as above                                                    |
| Front-end redirects to login                  | Session expired — log in again                                   |
| Want to start over                            | `python seed.py` wipes & re-creates the schema                   |
| Owner sees Add buttons                        | Hard-refresh the page (cached JS) — `Ctrl+Shift+R`               |
| Mobile table still cut off                    | Hard-refresh; old `dashboard.css` cached                         |
