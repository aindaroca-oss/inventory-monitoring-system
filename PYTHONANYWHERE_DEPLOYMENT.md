# PythonAnywhere Deployment — SQLite Only

The Flask application now uses SQLite exclusively. Its database file is separate from the source code and is never recreated by app startup. Keep the existing PythonAnywhere SQLite file at its current path; do not run `schema.sql` against it or upload another file over it.

## 1. Update the code

Push the project changes to GitHub, then open a PythonAnywhere Bash console and pull the repository:

```bash
cd ~/InventorySystem
git pull origin main
```

If the repository has not been cloned on PythonAnywhere yet, clone it once instead:

```bash
git clone https://github.com/aindaroca-oss/inventory-monitoring-system.git ~/InventorySystem
```

## 2. Install the app requirements

Use the Python version selected on the Web tab. For Python 3.13:

```bash
mkvirtualenv --python=/usr/bin/python3.13 inventory-system
workon inventory-system
cd ~/InventorySystem
pip install -r requirements.txt
```

If the `inventory-system` virtualenv already exists, just run `workon inventory-system` and install the requirements again.

## 3. Set up the WSGI file

On the Web tab, open the WSGI configuration file and set the project path, runtime mode, SQLite path, and a private session secret before importing the Flask app:

```python
import os
import sys

project_home = "/home/YOUR_USERNAME/InventorySystem"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ["APP_ENV"] = "production"
os.environ["SQLITE_PATH"] = "/home/YOUR_USERNAME/dunder_inventory_demo.sqlite3"
os.environ["SECRET_KEY"] = "PASTE_A_NEW_PRIVATE_RANDOM_SECRET_HERE"

from inventory_system import app as application
```

Replace `YOUR_USERNAME` with the PythonAnywhere account username. Keep the secret in the private WSGI file; never put it in the repository. The app no longer uses `DB_BACKEND`, `DB_HOST`, or any MySQL settings.

If your existing SQLite database is already at a different path, use its current path in `SQLITE_PATH`. Do not upload a second database over it.

## 4. Configure static files and reload

On the Web tab, set the virtualenv to `/home/YOUR_USERNAME/.virtualenvs/inventory-system` and add this static files mapping:

- URL: `/static/`
- Directory: `/home/YOUR_USERNAME/InventorySystem/static`

Save the WSGI file and click **Reload**. The public URL is `https://YOUR_USERNAME.pythonanywhere.com` (or the regional domain shown on your PythonAnywhere account).

## 5. Verify the deployment

Check staff and admin login, session continuity, inventory, suppliers, shelves, supply requests, approvals, cancellations, fulfillment, transaction history, and low-stock records. If the site returns an error, check **Web → Log files → error log** first.

The Free plan is intended for a small demonstration. SQLite uses the account filesystem, and PythonAnywhere Free has limited CPU, disk, and worker capacity. SMTP email delivery may also be limited by free-account outbound-network restrictions. Keep a separate backup of the SQLite file.
