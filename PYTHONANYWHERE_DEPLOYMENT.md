# PythonAnywhere Free Demo Deployment

This guide deploys the Flask/Jinja application with a separate SQLite copy of
the local MySQL data. The MySQL backend remains available for local use. The
migration script only reads MySQL and refuses to overwrite an existing SQLite
file.

## 1. Create a SQLite copy locally

Keep your existing MySQL database and its export as backups. Start MySQL in
XAMPP and set the source connection values in PowerShell from this project
folder:

```powershell
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
$env:DB_NAME = "dunder_inventory"
$env:DB_USER = "root"
$env:DB_PASS = ""
python migrate_mysql_to_sqlite.py --output .\dunder_inventory_demo.sqlite3
```

Use your actual local MySQL username/password if they differ. The script
prints row counts for all nine tables and checks foreign keys. It performs
SELECTs only on MySQL. The output file is a separate demo copy and is ignored
by Git (`*.sqlite3`). Do not commit this database file because it contains
account email addresses and password hashes.

If the output path already exists, the script stops without overwriting it.
Choose a new output name or move the old demo copy aside before creating a new
one.

## 2. Upload the project and SQLite file

Push the code changes to the GitHub repository, then in PythonAnywhere use a
Bash console to clone or pull the repository into a folder such as
`/home/YOUR_USERNAME/InventorySystem`. Do not upload the local `.venv` folder.

Upload `dunder_inventory_demo.sqlite3` separately using PythonAnywhere's Files
page, placing it at `/home/YOUR_USERNAME/dunder_inventory_demo.sqlite3`. Keep
the MySQL export and local MySQL database on your own computer.

## 3. Create the web app and virtual environment

In PythonAnywhere, open **Web → Add a new web app**, choose the free
`YOUR_USERNAME.pythonanywhere.com` domain, then select manual configuration and
Python 3.13. In a Bash console, create and populate a virtual environment:

```bash
mkvirtualenv --python=/usr/bin/python3.13 inventory-system
workon inventory-system
cd ~/InventorySystem
pip install -r requirements.txt
```

On the Web tab, set the virtualenv to
`/home/YOUR_USERNAME/.virtualenvs/inventory-system`.

## 4. Configure the WSGI file

Open the WSGI configuration file linked from the Web tab. Replace its Flask
section with the following, substituting your PythonAnywhere username and a
new secret generated for the hosted app:

```python
import os
import sys

project_home = "/home/YOUR_USERNAME/InventorySystem"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["APP_ENV"] = "production"
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_PATH"] = "/home/YOUR_USERNAME/dunder_inventory_demo.sqlite3"
os.environ["SECRET_KEY"] = "REPLACE_WITH_A_LONG_RANDOM_SECRET"

from inventory_system import app as application
```

Generate the secret in a local PowerShell window with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Keep the secret in the private PythonAnywhere WSGI configuration, never in
GitHub. The production setting enables secure session cookies. PythonAnywhere
loads this app through WSGI; do not start it with `python inventory_system.py`
on the host.

## 5. Serve static files and reload

On the Web tab, add a static files mapping:

- URL: `/static/`
- Directory: `/home/YOUR_USERNAME/InventorySystem/static`

Save the WSGI file, then click **Reload** on the Web tab. The public URL is
`https://YOUR_USERNAME.pythonanywhere.com`.

## 6. Verify the demo

Check both staff and admin login, session continuity, inventory, suppliers,
shelves, supply requests, approvals, cancellations, fulfillment, transaction
history, and low-stock records. Compare the printed MySQL/SQLite row counts
before uploading. Do not run `seed-demo` against the migrated database.

PythonAnywhere Free includes one web app and one worker, and its free accounts
have a 512 MiB disk quota. SQLite runs on PythonAnywhere's filesystem and can
be slower than MySQL; this is intended for a low-traffic coursework demo, not
production use. Free-account outbound internet is restricted, so SMTP email
alerts may not deliver. Keep the local MySQL database and export as the
authoritative backup.
