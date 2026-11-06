# Inventory System — Dunder Mifflin

A Flask + MySQL implementation of the Figma screens and Midterm Lab mini-SRS.

## Requirements

- Python 3.10 or later
- MySQL 8.0+ or MariaDB 10.4+
- MySQL enabled through XAMPP or another local service

## Run locally on Windows

1. Start MySQL in XAMPP.
2. In phpMyAdmin, import `schema.sql`. It creates the `inventory_system` database and tables.
3. In PowerShell, from this project folder:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   $env:DB_HOST = "127.0.0.1"
   $env:DB_PORT = "3306"
   $env:DB_NAME = "inventory_system"
   $env:SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
   flask --app inventory_system seed-demo
   python inventory_system.py
   ```

4. Open `http://127.0.0.1:5000`.

Set `DB_HOST`, `DB_PORT`, `DB_USER`, and `DB_PASS` in your local environment if your MySQL setup uses values other than the local defaults.

`seed-demo` only runs while the `users` table is empty. It generates temporary passwords and prints them once in the terminal; save them locally. Set `SEED_ADMIN_PASSWORD` and `SEED_PERSONNEL_PASSWORD` before seeding if you want to choose local demo passwords. Seeding is disabled when `APP_ENV=production`. Never reuse demo credentials on a public deployment.

The main Python entry point is `inventory_system.py`; `app.py` remains as a compatibility launcher for older PyCharm run configurations. The staff member is modeled as `OfficePersonnel`; there is no duplicate `User` domain class. The `users` SQL table stores password hashes and links each account to either an `OfficePersonnel` or `InventoryAdmin` record.

## Existing MySQL database

The application now defaults to the `inventory_system` database. To keep existing data in `dunder_inventory`, back up the database and run [`DATABASE_RENAME.sql`](DATABASE_RENAME.sql) in phpMyAdmin. The script moves the tables without deleting the old database. Verify the application against `inventory_system` before removing the old schema. For a fresh install, import `schema.sql` instead; do not run both paths on the same tables.

## GitHub Pages and cloud hosting

GitHub Pages only serves static files. This application currently renders its pages with Flask/Jinja and uses Flask routes, sessions, and MySQL queries, so the current app cannot be deployed unchanged to Pages. The static Pages frontend and an HTTP API must be separated from the Flask/MySQL backend before the complete interactive system can be published. Host the API and MySQL with separate cloud services, keep their credentials in those providers' secret stores, and configure the frontend with only the public API base URL. See [`PAGES_DEPLOYMENT.md`](PAGES_DEPLOYMENT.md) for the deployment split and remaining setup steps.

`.env` and environment-specific files are ignored by Git. The repository includes only the non-secret [`.env.example`](.env.example) template; copy it to `.env` locally and fill in local values without committing it.

Each mini-SRS entity has its own module under `inventory_system_core/`: `item.py`, `supplier.py`, `shelf.py`, `office_personnel.py`, `inventory_admin.py`, `transaction_log.py`, and `low_stock_alert.py`. Shared database and workflow logic live in `database.py` and `services.py`. The files in `templates/components/` are reusable navigation, top-bar, flash-message, and UI macro components.

## Email alerts

Low-stock transitions create one durable, de-duplicated `low_stock_alert` record per item and low-stock episode. The app attempts an email immediately after the database transaction commits. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_STARTTLS=1`, and `MAIL_FROM` in the environment to deliver messages. Email status and a delivery error are retained on the alert record. The database guarantees one alert record per low-stock episode; standard SMTP cannot guarantee exactly-once delivery if a remote mail server accepts a message but its response is lost.

## Implemented requirements

- Role-based authenticated access for Office Personnel and Inventory Administrators.
- Current item quantities, minimum reorder thresholds, supplier and shelf associations.
- Supply requests with required dates and pending/approved/declined/fulfilled statuses.
- Admin stock-in and stock-out recording, request fulfillment, quantity validation and transaction history.
- Low-stock episode tracking and email alert attempts.
- Item, supplier, shelf and team account management.

The schema follows the supplied data dictionary and adds `users`, archive fields and low-stock episode fields to support authentication, safe history retention and idempotent alert records. The app is an MVP for local coursework use; deploy behind a production WSGI server and HTTPS before exposing it to a network.
