# Inventory System — Dunder Mifflin

Flask/Jinja inventory application using **SQLite only**. The app does not connect to MySQL or require phpMyAdmin. Its database file is selected with `SQLITE_PATH`.

## Requirements

- Python 3.10 or later
- An existing SQLite database file, such as `dunder_inventory_demo.sqlite3`

## Run locally on Windows

Open PowerShell in this project folder and point `SQLITE_PATH` to your existing SQLite database:

```powershell
Set-Location "C:\Users\Ain\Documents\ChatGPT\InventorySystem"
python -m pip install -r requirements.txt
$env:SQLITE_PATH = ".\dunder_inventory_demo.sqlite3"
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_urlsafe(48))")
python inventory_system.py
```

Then open `http://127.0.0.1:5000`.

`schema.sql` is only for creating a **new, empty** SQLite database. Do not run it against an existing database; it creates tables. For an existing database, set `SQLITE_PATH` to that file and leave its contents intact. `flask --app inventory_system seed-demo` is only for an empty development database and is disabled in production.

## PythonAnywhere

Set `SQLITE_PATH` in the WSGI configuration to the existing database file, for example `/home/YOUR_USERNAME/dunder_inventory_demo.sqlite3`. Do not set `DB_BACKEND` or MySQL connection variables; the application is SQLite-only. See [PYTHONANYWHERE_DEPLOYMENT.md](PYTHONANYWHERE_DEPLOYMENT.md) for the WSGI and static-file settings.

Keep the SQLite file private and outside GitHub because it contains account emails and password hashes. The repository's `.gitignore` excludes `*.sqlite` and `*.sqlite3`.

## Application structure

The main Python entry point is `inventory_system.py`; `app.py` remains a compatibility launcher. Domain classes and services live under `inventory_system_core/`, and reusable UI components live under `templates/components/`.

## Email alerts

Low-stock transitions are recorded in SQLite and the app attempts an email using `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_STARTTLS`, and `MAIL_FROM`. The database de-duplicates alerts by item and low-stock episode; SMTP itself cannot guarantee exactly-once delivery if the mail server accepts a message but its response is lost.

## Implemented requirements

- Role-based authenticated access for Office Personnel and Inventory Administrators.
- Inventory quantities, reorder thresholds, suppliers, and shelves.
- Supply requests with required dates and pending, approved, declined, and fulfilled statuses.
- Stock-in and stock-out recording, request fulfillment, quantity validation, and transaction history.
- Low-stock episode tracking and email alert attempts.
- Item, supplier, shelf, and team account management.

GitHub Pages cannot run this Flask application or its SQLite database. Host the complete application on a Python/WSGI host such as PythonAnywhere.
