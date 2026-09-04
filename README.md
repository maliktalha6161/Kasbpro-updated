# KasbPro - Business & Customer Relationship Management System

KasbPro is an AI-powered web-based Business Management and Customer Relationship Management (CRM) application designed to streamline daily operational workflows, financial tracking, supplier management, and automated client interactions.

---

## Key Features

* **Dashboard & Analytics:** Real-time visual tracking of business performance, key metrics, and financial reporting graphs.
* **Billing & Invoicing:** Automated customer billing system with PDF/print options and transaction logging.
* **Customer Management:** Comprehensive customer profile tracking, interaction history, and contact management.
* **Supplier & Inventory System:** Inventory tracking, stock updates, and supplier records.
* **AI Assistant:** Integrated Gemini AI-powered operational assistant (`ai-assistant.html`) to assist with routine queries and administrative tasks.
* **Authentication & Security:** User authentication flows with login, signup, and password recovery features.

---

## Tech Stack

* **Frontend:** HTML5, CSS3, JavaScript (ES6+)
* **Backend:** Python (Flask)
* **Database:** MySQL (`kasbpro_dump.sql`)
* **AI Integration:** Google Gemini AI API

---

## Project Structure

```text
├── backups/               # Database backup files
├── static / css / js      # Modular UI styles and logic files
├── templates / html       # Interface templates (Dashboard, Billing, Reports, etc.)
├── app.py                 # Primary Flask application server
├── database.py            # MySQL database connection handler
├── generate_sql_dump.py   # Database dump utility
├── kasbpro_dump.sql       # Database scheme and initial data
├── seed.py                # Database seeding script
└── requirements.txt       # Python dependencies
