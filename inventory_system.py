from __future__ import annotations

import hmac
import json
import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from inventory_system_core import (
    AuthenticationService,
    Database,
    InventoryAdmin,
    InventoryService,
    OfficePersonnel,
)
from inventory_system_core.database import DATABASE_ERROR_TYPES, INTEGRITY_ERROR_TYPES

PROJECT_ROOT = Path(__file__).resolve().parent
app = Flask(
    "Inventory System",
    template_folder=str(PROJECT_ROOT / "templates"),
    static_folder=str(PROJECT_ROOT / "static"),
)
configured_secret_key = os.getenv("SECRET_KEY")
if os.getenv("APP_ENV", "development").lower() == "production" and not configured_secret_key:
    raise RuntimeError("SECRET_KEY must be set when APP_ENV=production.")
app.secret_key = configured_secret_key or secrets.token_urlsafe(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("APP_ENV", "development").lower() == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,
)

database = Database()
authentication = AuthenticationService(database)
inventory = InventoryService(database)

def connect_db():
    return database.connect()


def one(sql: str, args: tuple = ()):
    return database.fetch_one(sql, args)


def all_rows(sql: str, args: tuple = ()):
    return database.fetch_all(sql, args)


def ensure_reference_archive_columns() -> None:
    """Add soft-archive fields to existing local databases after an app update."""
    with database.connect() as connection, connection.cursor() as cursor:
        for table in ("supplier", "shelf"):
            cursor.execute("""SELECT COUNT(*) n FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='archived_at'""", (table,))
            if not cursor.fetchone()["n"]:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN archived_at DATETIME NULL")
        cursor.execute("UPDATE supplier SET email='orders@staples-officesupplies.test' WHERE email='staples@example.test'")
        cursor.execute("UPDATE supplier SET email='sales@quilloffice.test' WHERE email='quill@example.test'")
        connection.commit()


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


@app.context_processor
def inject_globals():
    return {"csrf_token": csrf_token, "today": date.today()}


@app.template_filter("date_short")
def date_short(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}, {value.year}"


@app.template_filter("date_time")
def date_time(value: datetime) -> str:
    hour = value.hour % 12 or 12
    suffix = "AM" if value.hour < 12 else "PM"
    return f"{value.strftime('%b')} {value.day}, {value.year} · {hour}:{value.minute:02d} {suffix}"


def request_display_id(requested_at: datetime, first_log_id: int) -> str:
    return f"SOUT-{requested_at:%Y%m}{int(first_log_id):04d}"


def transaction_display_id(transaction_type: str, transaction_date: datetime, first_log_id: int) -> str:
    prefix = "SIN" if transaction_type == "Stock In" else "SOUT"
    return f"{prefix}-{transaction_date:%Y%m}{int(first_log_id):04d}"


def check_csrf() -> None:
    expected = session.get("csrf", "")
    supplied = request.form.get("csrf", "")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(400, "Your session expired. Refresh the page and try again.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("home"))
        if session["user"]["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def clean_text(name: str, max_length: int = 255, required: bool = True) -> str:
    value = request.form.get(name, "").strip()
    if (required and not value) or len(value) > max_length:
        raise ValueError(f"Enter a valid value for {name.replace('_', ' ')} (maximum {max_length} characters).")
    return value


def positive_int(name: str, minimum: int = 0) -> int:
    try:
        value = int(request.form.get(name, ""))
    except ValueError as exc:
        raise ValueError(f"Enter a valid number for {name.replace('_', ' ')}.") from exc
    if value < minimum:
        raise ValueError(f"{name.replace('_', ' ').capitalize()} must be at least {minimum}.")
    return value


@app.get("/")
def home():
    if "user" not in session:
        return render_template("login.html", login_error=None)
    page = request.args.get("page", "dashboard")
    allowed = {"dashboard", "inventory", "requests", "transactions", "suppliers", "team"}
    if page not in allowed:
        page = "dashboard"
    if session["user"]["role"] != "admin" and page in {"transactions", "suppliers", "team"}:
        page = "dashboard"
    user = session["user"]
    try:
        ensure_reference_archive_columns()
        request_submission = session.pop("request_submission", None) if page == "requests" and user["role"] == "personnel" else None
        stats = {
            "items": one("SELECT COUNT(*) n FROM item WHERE archived_at IS NULL")["n"],
            "qty": one("SELECT COALESCE(SUM(qty_on_hand),0) n FROM item WHERE archived_at IS NULL")["n"],
            "out_of_stock": one("SELECT COUNT(*) n FROM item WHERE archived_at IS NULL AND qty_on_hand=0")["n"],
            "low_stock": one("SELECT COUNT(*) n FROM item WHERE archived_at IS NULL AND qty_on_hand>0 AND qty_on_hand<=reorder_threshold")["n"],
        }
        if user["role"] == "personnel":
            request_counts = one("""SELECT
                    COALESCE(SUM(request_status='Pending'),0) pending,
                    COALESCE(SUM(request_status='Approved'),0) approved,
                    COALESCE(SUM(request_status='Fulfilled'),0) fulfilled
                FROM (
                    SELECT r.request_id,
                        CASE WHEN r.cancelled_at IS NOT NULL THEN 'Cancelled'
                             WHEN SUM(l.status='Pending')>0 THEN 'Pending'
                             WHEN SUM(l.status='Approved')>0 THEN 'Approved'
                             WHEN SUM(l.status='Declined')>0 THEN 'Declined'
                             ELSE 'Fulfilled' END request_status
                    FROM supply_request r JOIN transaction_log l ON l.request_id=r.request_id
                    WHERE r.personnel_id=%s AND l.transaction_type='Stock Out'
                    GROUP BY r.request_id
                ) request_statuses""", (user["personnel_id"],))
            stats["pending_requests"] = request_counts["pending"]
            stats["approved_requests"] = request_counts["approved"]
            stats["fulfilled_requests"] = request_counts["fulfilled"]
        else:
            stats["submitted"] = one("SELECT COUNT(*) n FROM supply_request")["n"]
            stats["pending_requests"] = one("SELECT COUNT(DISTINCT request_id) n FROM transaction_log WHERE request_id IS NOT NULL AND transaction_type='Stock Out' AND status='Pending'")["n"]
            stats["pending"] = stats["pending_requests"]
        items = all_rows("""SELECT i.*,s.shelf_num,sp.supplier_name FROM item i
            JOIN shelf s ON s.shelf_id=i.shelf_id JOIN supplier sp ON sp.supplier_id=i.supplier_id
            WHERE i.archived_at IS NULL ORDER BY (i.qty_on_hand<=i.reorder_threshold) DESC,i.item_name""")
        suppliers = all_rows("SELECT * FROM supplier WHERE archived_at IS NULL ORDER BY supplier_name")
        shelves = all_rows("SELECT * FROM shelf WHERE archived_at IS NULL ORDER BY shelf_num")
        stock_notifications = [
            {**item, "stock_label": "Out of Stock" if item["qty_on_hand"] == 0 else "Low Stock"}
            for item in items
            if item["qty_on_hand"] == 0 or item["qty_on_hand"] <= item["reorder_threshold"]
        ]
        stock_out_count = sum(item["qty_on_hand"] == 0 for item in stock_notifications)
        stock_low_count = sum(item["qty_on_hand"] > 0 for item in stock_notifications)
        notification_key = "stock-alerts-" + ",".join(
            f"{item['item_id']}:{item['qty_on_hand']}:{item['reorder_threshold']}" for item in stock_notifications
        )
        show_stock_alerts = bool(
            user["role"] == "admin" and page == "dashboard" and session.pop("show_stock_alerts", False)
            and stock_notifications
        )
        context = dict(page=page,user=user,stats=stats,items=items,suppliers=suppliers,shelves=shelves,
                       request_submission=request_submission,stock_notifications=stock_notifications,
                       notification_key=notification_key,show_stock_alerts=show_stock_alerts,
                       stock_out_count=stock_out_count,stock_low_count=stock_low_count)
        if page == "dashboard":
            if user["role"] == "personnel":
                context["recent"] = all_rows("""SELECT r.request_id,MIN(l.log_id) first_log_id,
                        r.requested_at,r.required_date,r.cancelled_at,
                        CASE WHEN r.cancelled_at IS NOT NULL THEN 'Cancelled'
                             WHEN SUM(l.status='Pending')>0 THEN 'Pending'
                             WHEN SUM(l.status='Approved')>0 THEN 'Approved'
                             WHEN SUM(l.status='Declined')>0 THEN 'Declined'
                             ELSE 'Fulfilled' END status
                    FROM supply_request r JOIN transaction_log l ON l.request_id=r.request_id
                    WHERE r.personnel_id=%s AND l.transaction_type='Stock Out'
                    GROUP BY r.request_id ORDER BY r.requested_at DESC LIMIT 6""", (user["personnel_id"],))
                for recent_request in context["recent"]:
                    recent_request["request_code"] = request_display_id(recent_request["requested_at"], recent_request["first_log_id"])
                recent_ids = [row["request_id"] for row in context["recent"]]
                if recent_ids:
                    placeholders = ",".join(["%s"] * len(recent_ids))
                    recent_items = all_rows(f"""SELECT l.request_id,i.item_name
                        FROM transaction_log l JOIN item i ON i.item_id=l.item_id
                        WHERE l.request_id IN ({placeholders}) AND l.transaction_type='Stock Out'
                        ORDER BY l.request_id DESC,i.item_name""",
                        tuple(recent_ids))
                else:
                    recent_items = []
                recent_items_by_request = {}
                for recent_item in recent_items:
                    recent_items_by_request.setdefault(recent_item["request_id"], []).append(recent_item["item_name"])
                for recent_request in context["recent"]:
                    recent_request["requested_items"] = ", ".join(recent_items_by_request.get(recent_request["request_id"], []))
            else:
                context["recent"] = all_rows("""SELECT
                        MIN(l.log_id) first_log_id,
                        GROUP_CONCAT(DISTINCT i.item_name ORDER BY i.item_name SEPARATOR ', ') item_names,
                        MAX(l.transaction_type) activity_type,MAX(l.transaction_date) activity_date,
                        'Fulfilled' status
                    FROM transaction_log l JOIN item i ON i.item_id=l.item_id
                    WHERE l.admin_id=%s AND l.status='Fulfilled'
                      AND l.transaction_type IN ('Stock In','Stock Out')
                    GROUP BY CASE WHEN l.request_id IS NOT NULL THEN CONCAT('request-',l.request_id)
                        ELSE CONCAT('movement-',COALESCE(l.admin_id,0),'-',REPLACE(LOWER(l.transaction_type),' ','-'),'-',
                            DATE_FORMAT(l.transaction_date,'%%Y%%m%%d')) END
                    ORDER BY activity_date DESC,MAX(l.log_id) DESC LIMIT 6""", (user["admin_id"],))
                for activity in context["recent"]:
                    activity["activity_id"] = transaction_display_id(activity["activity_type"], activity["activity_date"], activity["first_log_id"])
            context["greeting"] = "Good morning" if datetime.now().hour < 12 else "Good afternoon" if datetime.now().hour < 18 else "Good evening"
        elif page == "inventory":
            context["edit_item"] = one("SELECT * FROM item WHERE item_id=%s AND archived_at IS NULL", (request.args.get("edit", 0),)) if request.args.get("edit") else None
        elif page == "requests":
            if user["role"] == "personnel":
                requests = all_rows("""SELECT r.request_id,MIN(l.log_id) first_log_id,
                        r.requested_at,r.required_date,r.notes,r.cancelled_at,r.reviewed_at,r.review_notes,
                        MAX(a.admin_name) reviewed_by_name,
                        CASE WHEN r.cancelled_at IS NOT NULL THEN 'Cancelled'
                             WHEN SUM(l.status='Pending')>0 THEN 'Pending'
                             WHEN SUM(l.status='Approved')>0 THEN 'Approved'
                             WHEN SUM(l.status='Declined')>0 THEN 'Declined'
                             ELSE 'Fulfilled' END status
                    FROM supply_request r JOIN transaction_log l ON l.request_id=r.request_id
                    LEFT JOIN inventory_admin a ON a.admin_id=r.reviewed_by_admin_id
                    WHERE r.personnel_id=%s AND l.transaction_type='Stock Out'
                    GROUP BY r.request_id ORDER BY r.requested_at DESC""", (user["personnel_id"],))
                request_items = all_rows("""SELECT l.request_id,l.item_id,l.item_qty,l.status,i.item_name,i.item_description,i.unit_name,
                        i.qty_on_hand,i.reorder_threshold
                    FROM transaction_log l JOIN supply_request r ON r.request_id=l.request_id
                    JOIN item i ON i.item_id=l.item_id
                    WHERE r.personnel_id=%s AND l.transaction_type='Stock Out'
                    ORDER BY l.request_id DESC,i.item_name""", (user["personnel_id"],))
                items_by_request = {}
                for request_item in request_items:
                    items_by_request.setdefault(request_item["request_id"], []).append(request_item)
                for supply_request in requests:
                    supply_request["request_code"] = request_display_id(supply_request["requested_at"], supply_request["first_log_id"])
                    supply_request["items"] = items_by_request.get(supply_request["request_id"], [])
                context["requests"] = requests
            else:
                requests = all_rows("""SELECT r.request_id,MIN(l.log_id) first_log_id,
                        r.requested_at,r.required_date,r.notes,r.cancelled_at,r.reviewed_at,r.review_notes,
                        p.personnel_name requested_by,MAX(a.admin_name) reviewed_by_name,
                        CASE WHEN r.cancelled_at IS NOT NULL THEN 'Cancelled'
                             WHEN SUM(l.status='Pending')>0 THEN 'Pending'
                             WHEN SUM(l.status='Approved')>0 THEN 'Approved'
                             WHEN SUM(l.status='Declined')>0 THEN 'Declined'
                             ELSE 'Fulfilled' END status
                    FROM supply_request r JOIN transaction_log l ON l.request_id=r.request_id
                    JOIN office_personnel p ON p.personnel_id=r.personnel_id
                    LEFT JOIN inventory_admin a ON a.admin_id=r.reviewed_by_admin_id
                    WHERE l.transaction_type='Stock Out'
                    GROUP BY r.request_id ORDER BY FIELD(status,'Pending','Approved','Fulfilled','Declined','Cancelled'),r.requested_at DESC""")
                request_items = all_rows("""SELECT l.request_id,l.log_id,l.item_id,l.item_qty,l.status,
                        i.item_name,i.item_description,i.unit_name
                    FROM transaction_log l JOIN item i ON i.item_id=l.item_id
                    WHERE l.request_id IS NOT NULL AND l.transaction_type='Stock Out'
                    ORDER BY l.request_id DESC,i.item_name""")
                items_by_request = {}
                for request_item in request_items:
                    items_by_request.setdefault(request_item["request_id"], []).append(request_item)
                for supply_request in requests:
                    supply_request["request_code"] = request_display_id(supply_request["requested_at"], supply_request["first_log_id"])
                    supply_request["items"] = items_by_request.get(supply_request["request_id"], [])
                context["requests"] = requests
        elif page == "transactions":
            group_key_sql = "CASE WHEN l.request_id IS NOT NULL THEN CONCAT('request-',l.request_id) ELSE CONCAT('movement-',COALESCE(l.admin_id,0),'-',REPLACE(LOWER(l.transaction_type),' ','-'),'-',DATE_FORMAT(l.transaction_date,'%%Y%%m%%d')) END"
            context["log_count"] = one("SELECT COUNT(DISTINCT CASE WHEN request_id IS NOT NULL THEN CONCAT('request-',request_id) ELSE CONCAT('movement-',COALESCE(admin_id,0),'-',REPLACE(LOWER(transaction_type),' ','-'),'-',DATE_FORMAT(transaction_date,'%%Y%%m%%d')) END) n FROM transaction_log")["n"]
            context["logs"] = all_rows("""SELECT
                    """ + group_key_sql + """ transaction_key,
                    MIN(l.log_id) first_log_id,
                    MAX(l.request_id) request_id,
                    GROUP_CONCAT(DISTINCT i.item_name ORDER BY i.item_name SEPARATOR ', ') item_names,
                    MAX(l.transaction_type) transaction_type,MAX(l.transaction_date) transaction_date,
                    MAX(r.requested_at) requested_at,MAX(r.reviewed_at) reviewed_at,
                    GROUP_CONCAT(DISTINCT COALESCE(rp.personnel_name,p.personnel_name,'—')
                        ORDER BY COALESCE(rp.personnel_name,p.personnel_name,'—') SEPARATOR ', ') requested_by,
                    COALESCE(MAX(a.admin_name),'—') processed_by,
                    GROUP_CONCAT(DISTINCT COALESCE(sp.supplier_name,item_supplier.supplier_name,'—')
                        ORDER BY COALESCE(sp.supplier_name,item_supplier.supplier_name,'—') SEPARATOR ', ') supplied_by,
                    CASE WHEN MAX(r.cancelled_at) IS NOT NULL THEN 'Cancelled'
                         WHEN SUM(l.status='Pending')>0 THEN 'Pending'
                         WHEN SUM(l.status='Approved')>0 THEN 'Approved'
                         WHEN SUM(l.status='Declined')>0 THEN 'Declined'
                         ELSE 'Fulfilled' END status
                FROM transaction_log l JOIN item i ON i.item_id=l.item_id
                LEFT JOIN office_personnel p ON p.personnel_id=l.personnel_id
                LEFT JOIN supply_request r ON r.request_id=l.request_id
                LEFT JOIN office_personnel rp ON rp.personnel_id=r.personnel_id
                LEFT JOIN inventory_admin a ON a.admin_id=l.admin_id
                LEFT JOIN supplier sp ON sp.supplier_id=l.supplier_id
                LEFT JOIN supplier item_supplier ON item_supplier.supplier_id=i.supplier_id
                GROUP BY """ + group_key_sql + """
                ORDER BY MAX(l.transaction_date) DESC,MAX(l.log_id) DESC LIMIT 250""")
            transaction_keys = [row["transaction_key"] for row in context["logs"]]
            if transaction_keys:
                key_placeholders = ",".join(["%s"] * len(transaction_keys))
                transaction_items = all_rows("""SELECT l.log_id,l.request_id,l.admin_id,l.item_qty,l.transaction_type,l.status,
                        l.transaction_date,i.item_name,i.item_category,i.item_description,i.unit_name,
                        i.qty_on_hand,i.reorder_threshold,i.baseline_unit_cost,s.shelf_num,
                        COALESCE(sp.supplier_name,item_supplier.supplier_name,'—') supplier_name,
                        """ + group_key_sql + """ transaction_key
                    FROM transaction_log l JOIN item i ON i.item_id=l.item_id
                    JOIN shelf s ON s.shelf_id=i.shelf_id
                    LEFT JOIN supplier sp ON sp.supplier_id=l.supplier_id
                    LEFT JOIN supplier item_supplier ON item_supplier.supplier_id=i.supplier_id
                    WHERE """ + group_key_sql + " IN (" + key_placeholders + ") ORDER BY l.transaction_date DESC,l.log_id DESC",
                    tuple(transaction_keys))
            else:
                transaction_items = []
            items_by_transaction = {}
            for transaction_item in transaction_items:
                items_by_transaction.setdefault(transaction_item["transaction_key"], []).append(transaction_item)
            for transaction in context["logs"]:
                transaction["transaction_code"] = transaction_display_id(transaction["transaction_type"], transaction["transaction_date"], transaction["first_log_id"])
                transaction["items"] = items_by_transaction.get(transaction["transaction_key"], [])
        elif page == "team":
            context["people"] = all_rows("""SELECT u.email,u.role,u.active,COALESCE(p.personnel_name,a.admin_name) name,p.department
                FROM users u LEFT JOIN office_personnel p ON p.personnel_id=u.personnel_id LEFT JOIN inventory_admin a ON a.admin_id=u.admin_id
                ORDER BY u.role,u.email""")
        return render_template("app.html", **context)
    except DATABASE_ERROR_TYPES as exc:
        app.logger.exception("Database connection failed")
        return render_template("setup_error.html", error=str(exc)), 503


@app.post("/login")
def login():
    check_csrf()
    email = request.form.get("email", "").strip().lower()
    try:
        user_record = authentication.authenticate(email, request.form.get("password", ""))
    except DATABASE_ERROR_TYPES as exc:
        return render_template("setup_error.html", error=str(exc)), 503
    requested_role = request.form.get("role", "personnel")
    if not user_record or user_record.role != requested_role:
        return render_template("login.html", login_error="The email or password is incorrect."), 401
    session.clear()
    session["csrf"] = secrets.token_urlsafe(32)
    session.permanent = request.form.get("remember") == "on"
    session["user"] = {
        "id": user_record.account_id, "email": user_record.email, "role": user_record.role,
        "personnel_id": getattr(user_record, "personnel_id", None),
        "admin_id": getattr(user_record, "admin_id", None),
        "name": user_record.name,
        "department": getattr(user_record, "department", None),
    }
    if user_record.role == "admin":
        session["show_stock_alerts"] = True
    flash(f"Welcome back, {session['user']['name']}.")
    return redirect(url_for("home"))


@app.post("/logout")
@login_required
def logout():
    check_csrf()
    session.clear()
    return redirect(url_for("home"))


@app.post("/action/<action>")
@login_required
def action(action: str):
    check_csrf()
    user = session["user"]
    conn = None
    alert = None
    alerts = []
    submission_summary = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            if action == "request_supply":
                if user["role"] != "personnel": abort(403)
                try:
                    submitted_items = json.loads(request.form.get("request_items", "[]"))
                except json.JSONDecodeError as exc:
                    raise ValueError("The request cart is invalid. Please review it and try again.") from exc
                if not isinstance(submitted_items, list) or not submitted_items or len(submitted_items) > 50:
                    raise ValueError("Add at least one item to the request cart.")
                quantities = {}
                for line in submitted_items:
                    if not isinstance(line, dict):
                        raise ValueError("The request cart contains an invalid item.")
                    try:
                        item_id, qty = int(line.get("item_id")), int(line.get("quantity"))
                    except (TypeError, ValueError) as exc:
                        raise ValueError("Each cart item needs a valid quantity.") from exc
                    if item_id < 1 or qty < 1 or qty > 9999:
                        raise ValueError("Cart quantities must be between 1 and 9,999.")
                    quantities[item_id] = quantities.get(item_id, 0) + qty
                required = datetime.strptime(request.form.get("required_date", ""), "%Y-%m-%d")
                purpose = clean_text("notes", 255)
                personnel = OfficePersonnel(
                    personnel_id=user["personnel_id"],
                    personnel_name=user["name"],
                    department=user.get("department") or "",
                    account_id=user["id"],
                    email=user["email"],
                )
                request_created_at = datetime.now()
                cur.execute("""INSERT INTO supply_request(personnel_id,requested_at,required_date,notes)
                    VALUES(%s,%s,%s,%s)""", (personnel.personnel_id, request_created_at.strftime("%Y-%m-%d %H:%M:%S"), required.strftime("%Y-%m-%d 17:00:00"), purpose))
                request_id = cur.lastrowid
                request_log_ids = []
                for item_id, qty in quantities.items():
                    request_log_ids.append(personnel.request_supply(conn, request_id, item_id, qty, required, purpose))
                request_code = request_display_id(request_created_at, min(request_log_ids))
                message = f"Supply request {request_code} submitted with {len(quantities)} item(s) for administrator review."
                submission_summary = {
                    "request_code": request_code,
                    "submitted_date": datetime.now().strftime("%B %d, %Y"),
                    "item_count": len(quantities),
                    "status": "Pending",
                }
            elif action == "cancel_request":
                if user["role"] != "personnel": abort(403)
                request_id = positive_int("request_id", 1)
                cur.execute("""SELECT request_id,cancelled_at,requested_at FROM supply_request
                    WHERE request_id=%s AND personnel_id=%s FOR UPDATE""", (request_id, user["personnel_id"]))
                supply_request = cur.fetchone()
                if not supply_request: raise ValueError("Request not found.")
                cur.execute("""SELECT log_id,status FROM transaction_log WHERE request_id=%s
                    AND transaction_type='Stock Out' FOR UPDATE""", (request_id,))
                request_lines = cur.fetchall()
                request_statuses = [row["status"] for row in request_lines]
                if supply_request["cancelled_at"] is not None or not request_statuses or any(status != "Pending" for status in request_statuses):
                    raise ValueError("Only pending requests can be cancelled.")
                cancellation_reason = clean_text("cancellation_reason", 255)
                if not cancellation_reason:
                    raise ValueError("Enter a reason for cancellation.")
                cur.execute("""UPDATE transaction_log SET status='Declined'
                    WHERE request_id=%s AND transaction_type='Stock Out' AND status='Pending'""", (request_id,))
                cur.execute("""UPDATE supply_request SET cancelled_at=NOW(),reviewed_at=NOW(),
                    review_notes=%s WHERE request_id=%s""", (cancellation_reason, request_id))
                message = f"Request {request_display_id(supply_request['requested_at'], min(row['log_id'] for row in request_lines))} cancelled."
            elif action == "review_request":
                if user["role"] != "admin": abort(403)
                decision=request.form.get("decision")
                admin = InventoryAdmin(
                    admin_id=user["admin_id"], admin_name=user["name"],
                    account_id=user["id"], email=user["email"],
                )
                request_id = int(request.form.get("request_id", "0") or 0)
                if request_id:
                    cur.execute("""SELECT * FROM transaction_log WHERE request_id=%s
                        AND transaction_type='Stock Out' ORDER BY log_id FOR UPDATE""", (request_id,))
                    request_lines = cur.fetchall()
                    if not request_lines: raise ValueError("Request not found.")
                    statuses = {line["status"] for line in request_lines}
                    if decision == "approve":
                        if not statuses.issubset({"Pending", "Approved", "Fulfilled", "Declined"}) or "Pending" not in statuses:
                            raise ValueError("Only pending requests can be approved.")
                        for line in request_lines:
                            if line["status"] == "Pending": admin.approve_request(conn, line)
                        message = "Request approved."
                    elif decision == "decline":
                        if not statuses.issubset({"Pending", "Approved", "Declined"}) or not statuses.intersection({"Pending", "Approved"}):
                            raise ValueError("This request can no longer be declined.")
                        for line in request_lines:
                            if line["status"] in {"Pending", "Approved"}:
                                admin.decline_request(conn, line)
                        message = "Request declined."
                    elif decision == "fulfill":
                        if not statuses.issubset({"Approved", "Fulfilled", "Declined"}) or "Approved" not in statuses:
                            raise ValueError("Approve all items before fulfilling this request.")
                        for line in request_lines:
                            if line["status"] != "Approved":
                                continue
                            line_alert = admin.fulfill_request(conn, line, inventory)
                            if line_alert: alerts.append(line_alert)
                        message = "Request fulfilled and stock updated."
                    else: raise ValueError("Choose a valid request action.")
                    request_id_for_review = request_id
                else:
                    log_id = positive_int("log_id",1)
                    cur.execute("SELECT * FROM transaction_log WHERE log_id=%s AND transaction_type='Stock Out' FOR UPDATE",(log_id,)); req=cur.fetchone()
                    if not req: raise ValueError("Request not found.")
                    if decision in {"approve","decline"}:
                        if decision=="approve":
                            admin.approve_request(conn, req)
                            message="Request approved."
                        else:
                            admin.decline_request(conn, req)
                            message="Request declined."
                    elif decision=="fulfill":
                        alert=admin.fulfill_request(conn,req,inventory); message="Request fulfilled and stock updated."
                    else: raise ValueError("Choose a valid request action.")
                    request_id_for_review = req["request_id"]
                review_notes = clean_text("remarks", 500) if decision == "decline" else {
                    "approve": f"Approved by {admin.name}.",
                    "fulfill": f"Fulfilled by {admin.name}.",
                }.get(decision, "")
                if request_id_for_review:
                    cur.execute("""UPDATE supply_request SET reviewed_by_admin_id=%s,reviewed_at=NOW(),review_notes=%s
                        WHERE request_id=%s""", (admin.admin_id, review_notes, request_id_for_review))
            elif action == "stock_transaction":
                if user["role"]!="admin": abort(403)
                item_id,qty=positive_int("item_id",1),positive_int("item_qty",1); trans_type=request.form.get("transaction_type")
                if trans_type not in {"Stock In","Stock Out"}: raise ValueError("Choose stock in or stock out.")
                cur.execute("SELECT * FROM item WHERE item_id=%s AND archived_at IS NULL FOR UPDATE",(item_id,)); item=cur.fetchone()
                if not item: raise ValueError("Inventory item not found.")
                if clean_text("unit_name", 30) != item["unit_name"]:
                    raise ValueError("Choose the unit assigned to this inventory item.")
                supplier_id=positive_int("supplier_id",1) if trans_type=="Stock In" else item["supplier_id"]
                try: unit_cost=float(request.form.get("unit_cost", item["baseline_unit_cost"]) or item["baseline_unit_cost"])
                except ValueError as exc: raise ValueError("Enter a valid unit cost.") from exc
                if unit_cost < 0: raise ValueError("Unit cost cannot be negative.")
                if trans_type=="Stock Out" and item["qty_on_hand"]<qty: raise ValueError("Stock out quantity cannot exceed available stock.")
                operator="+" if trans_type=="Stock In" else "-"
                cur.execute(f"UPDATE item SET qty_on_hand=qty_on_hand{operator}%s WHERE item_id=%s",(qty,item_id))
                if trans_type == "Stock In":
                    cur.execute("UPDATE item SET baseline_unit_cost=%s WHERE item_id=%s", (unit_cost,item_id))
                cur.execute("""INSERT INTO transaction_log(item_id,admin_id,supplier_id,item_qty,transaction_type,status,unit_cost_at_time,required_date,notes)
                    VALUES(%s,%s,%s,%s,%s,'Fulfilled',%s,NOW(),%s)""",(item_id,user["admin_id"],supplier_id,qty,trans_type,unit_cost,clean_text("notes",255,False) or None))
                alert=inventory.record_low_stock_transition(conn,item_id); message="Stock transaction recorded. Inventory quantity updated."
            elif action == "save_item":
                if user["role"]!="admin": abort(403)
                item_id=int(request.form.get("item_id") or 0)
                values=(clean_text("item_name",100),clean_text("item_description",255),clean_text("item_category",50),clean_text("unit_name",30),positive_int("supplier_id",1),positive_int("shelf_id",1),positive_int("reorder_threshold"),request.form.get("baseline_unit_cost","0"))
                qty=positive_int("qty_on_hand")
                try: cost=float(values[-1])
                except ValueError as exc: raise ValueError("Enter a valid unit cost.") from exc
                if cost<0: raise ValueError("Unit cost cannot be negative.")
                if item_id:
                    cur.execute("UPDATE item SET item_name=%s,item_description=%s,item_category=%s,unit_name=%s,supplier_id=%s,shelf_id=%s,qty_on_hand=%s,reorder_threshold=%s,baseline_unit_cost=%s WHERE item_id=%s AND archived_at IS NULL",(*values[:6],qty,values[6],cost,item_id))
                else:
                    cur.execute("INSERT INTO item(item_name,item_description,item_category,unit_name,supplier_id,shelf_id,qty_on_hand,reorder_threshold,baseline_unit_cost) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(*values[:6],qty,values[6],cost))
                    item_id=cur.lastrowid
                alert=inventory.record_low_stock_transition(conn,item_id); message="Inventory item saved."
            elif action == "archive_item":
                if user["role"]!="admin": abort(403)
                cur.execute("UPDATE item SET archived_at=NOW() WHERE item_id=%s AND archived_at IS NULL",(positive_int("item_id",1),)); message="Item archived. Transaction history remains available."
            elif action == "add_supplier":
                if user["role"]!="admin": abort(403)
                name=clean_text("supplier_name",100); phone=clean_text("contact_num",15); email=clean_text("supplier_email",100).lower()
                if "@" not in email: raise ValueError("Enter a valid supplier email.")
                cur.execute("INSERT INTO supplier(supplier_name,contact_num,email) VALUES(%s,%s,%s)",(name,phone,email)); message="Supplier added."
            elif action == "save_supplier":
                if user["role"]!="admin": abort(403)
                supplier_id=positive_int("supplier_id",1)
                name=clean_text("supplier_name",100); phone=clean_text("contact_num",15); email=clean_text("supplier_email",100).lower()
                if "@" not in email: raise ValueError("Enter a valid supplier email.")
                cur.execute("UPDATE supplier SET supplier_name=%s,contact_num=%s,email=%s WHERE supplier_id=%s AND archived_at IS NULL",(name,phone,email,supplier_id)); message="Supplier updated."
            elif action == "archive_supplier":
                if user["role"]!="admin": abort(403)
                cur.execute("UPDATE supplier SET archived_at=NOW() WHERE supplier_id=%s AND archived_at IS NULL",(positive_int("supplier_id",1),)); message="Supplier archived. Existing inventory history is kept."
            elif action == "add_shelf":
                if user["role"]!="admin": abort(403)
                cur.execute("INSERT INTO shelf(shelf_num) VALUES(%s)",(positive_int("shelf_num",1),)); message="Shelf added."
            elif action == "save_shelf":
                if user["role"]!="admin": abort(403)
                shelf_id=positive_int("shelf_id",1)
                cur.execute("UPDATE shelf SET shelf_num=%s WHERE shelf_id=%s AND archived_at IS NULL",(positive_int("shelf_num",1),shelf_id)); message="Shelf updated."
            elif action == "archive_shelf":
                if user["role"]!="admin": abort(403)
                cur.execute("UPDATE shelf SET archived_at=NOW() WHERE shelf_id=%s AND archived_at IS NULL",(positive_int("shelf_id",1),)); message="Shelf archived. Existing inventory history is kept."
            elif action == "add_user":
                if user["role"]!="admin": abort(403)
                name=clean_text("name",100); department=clean_text("department",50,False) or "Office"; email=clean_text("new_email",190).lower(); password=request.form.get("new_password",""); role=request.form.get("role")
                if "@" not in email or len(password)<10: raise ValueError("Enter a valid email and a password with at least 10 characters.")
                if role not in {"admin","personnel"}: raise ValueError("Choose a valid account role.")
                if role=="admin":
                    cur.execute("INSERT INTO inventory_admin(admin_name) VALUES(%s)",(name,)); admin_id=cur.lastrowid
                    cur.execute("INSERT INTO users(email,password_hash,role,admin_id) VALUES(%s,%s,'admin',%s)",(email,generate_password_hash(password),admin_id))
                else:
                    cur.execute("INSERT INTO office_personnel(personnel_name,department) VALUES(%s,%s)",(name,department)); personnel_id=cur.lastrowid
                    cur.execute("INSERT INTO users(email,password_hash,role,personnel_id) VALUES(%s,%s,'personnel',%s)",(email,generate_password_hash(password),personnel_id))
                message="User account added."
            else:
                abort(404)
        conn.commit()
        if alert:
            inventory.deliver_low_stock_alert(alert)
        for pending_alert in alerts:
            inventory.deliver_low_stock_alert(pending_alert)
        if submission_summary:
            session["request_submission"] = submission_summary
        else:
            flash(message, "success")
    except Exception as exc:
        if conn:
            conn.rollback()
        if isinstance(exc, (ValueError,) + DATABASE_ERROR_TYPES):
            app.logger.info("Action failed: %s", exc)
            message = "A record with that email or shelf number already exists." if isinstance(exc, INTEGRITY_ERROR_TYPES) else str(exc)
            flash(message, "error")
        else:
            raise
    finally:
        if conn:
            conn.close()
    target=request.form.get("return_to", "dashboard")
    if target not in {"dashboard","inventory","requests","transactions","suppliers","team"}: target="dashboard"
    return redirect(url_for("home", page=target) if target!="dashboard" else url_for("home"))


@app.cli.command("seed-demo")
def seed_demo():
    """Create demo accounts and sample inventory in a freshly imported schema."""
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError("Demo data seeding is disabled in production.")
    admin_password = os.getenv("SEED_ADMIN_PASSWORD") or secrets.token_urlsafe(16)
    personnel_password = os.getenv("SEED_PERSONNEL_PASSWORD") or secrets.token_urlsafe(16)
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM users")
        if cur.fetchone()["n"]:
            print("Seed skipped: users already exist.")
            return
        cur.execute("INSERT INTO supplier(supplier_name,contact_num,email) VALUES('Staples Office Supply','555-0100','orders@staples-officesupplies.test'),('Quill Office Products','555-0101','sales@quilloffice.test')")
        cur.execute("INSERT INTO shelf(shelf_num) VALUES(1),(2),(3)")
        cur.execute("INSERT INTO office_personnel(personnel_name,department) VALUES('Pam Beesly','Reception'),('Jim Halpert','Sales')")
        cur.execute("INSERT INTO inventory_admin(admin_name) VALUES('Michael Scott')")
        admin_id=cur.lastrowid
        cur.execute("INSERT INTO users(email,password_hash,role,admin_id) VALUES(%s,%s,'admin',%s)",('admin@dundermifflin.local',generate_password_hash(admin_password),admin_id))
        for email,pid in [('pam@dundermifflin.local',1),('jim@dundermifflin.local',2)]:
            cur.execute("INSERT INTO users(email,password_hash,role,personnel_id) VALUES(%s,%s,'personnel',%s)",(email,generate_password_hash(personnel_password),pid))
        cur.execute("""INSERT INTO item(supplier_id,shelf_id,item_name,item_description,item_category,unit_name,qty_on_hand,reorder_threshold,baseline_unit_cost) VALUES
            (1,1,'HP LaserJet Toner','Black toner cartridge for the office printer.','Printing','Cartridge',12,5,89.99),
            (2,1,'Copy Paper','A4 80 gsm paper, 500 sheets per ream.','Paper','Ream',8,10,6.50),
            (1,2,'Black Ballpoint Pens','Retractable black ink pens.','Writing','Box',46,15,1.25),
            (2,3,'Manila Folders','Letter-size kraft folders.','Filing','Pack',31,10,0.80),
            (2,1,'Long Bond Paper','Long-size bond paper for office printing and correspondence.','Paper','Ream',20,5,6.50),
            (2,3,'Long Document Envelope','Long kraft envelopes for office documents.','Paper','Pack',18,5,0.35),
            (1,1,'Black Ink Cartridge','Black replacement ink cartridge for office printers.','Printing','Cartridge',0,3,29.99)""")
        cur.execute("SELECT item_id,item_name,supplier_id,baseline_unit_cost FROM item WHERE archived_at IS NULL")
        demo_items = {row["item_name"]: row for row in cur.fetchall()}
        demo_item_ids = {name: row["item_id"] for name, row in demo_items.items()}
        demo_requests = [
            ("Pending", ["Copy Paper", "Black Ballpoint Pens", "Manila Folders"], 5, "Restock the reception area before next week's client meetings.", None),
            ("Approved", ["Black Ballpoint Pens", "Copy Paper"], 4, "Replace worn pens and replenish the shared copier paper.", "Approved; supplies are available for the requested date."),
            ("Declined", ["Manila Folders", "Long Bond Paper", "Long Document Envelope", "Black Ink Cartridge"], 3, "Prepare folders and envelopes for the monthly records filing.", "Declined because the black ink cartridge is currently out of stock."),
            ("Cancelled", ["Long Bond Paper", "HP LaserJet Toner"], 2, "These supplies are no longer needed for the monthly report.", "Cancelled by the requester before review."),
            ("Fulfilled", ["HP LaserJet Toner", "Copy Paper", "Black Ballpoint Pens", "Manila Folders", "Long Document Envelope"], 1, "Prepare printed copies and filing supplies for the quarterly report.", "Items were issued from the supply room and the request was fulfilled."),
        ]
        for status, item_names, days_needed, notes, review_notes in demo_requests:
            required = (datetime.now() + timedelta(days=days_needed)).replace(hour=17, minute=0, second=0, microsecond=0)
            cancelled_at = datetime.now() if status == "Cancelled" else None
            reviewed_by = admin_id if status in {"Approved", "Declined", "Fulfilled"} else None
            reviewed_at = datetime.now() if status != "Pending" else None
            cur.execute("""INSERT INTO supply_request(personnel_id,requested_at,required_date,notes,cancelled_at,
                    reviewed_by_admin_id,reviewed_at,review_notes)
                VALUES(1,NOW(),%s,%s,%s,%s,%s,%s)""",
                (required, notes, cancelled_at, reviewed_by, reviewed_at, review_notes))
            request_id = cur.lastrowid
            line_status = "Declined" if status == "Cancelled" else status
            for item_name in item_names:
                item_id = demo_item_ids[item_name]
                cur.execute("""INSERT INTO transaction_log(request_id,item_id,personnel_id,item_qty,transaction_type,status,unit_cost_at_time,required_date,notes)
                    SELECT %s,item_id,1,1,'Stock Out',%s,baseline_unit_cost,%s,%s
                    FROM item WHERE item_id=%s""", (request_id, line_status, required, notes, item_id))
        admin_activity_items = ["HP LaserJet Toner", "Black Ballpoint Pens", "Manila Folders"]
        for index, item_name in enumerate(admin_activity_items, start=1):
            demo_item = demo_items[item_name]
            for transaction_type in ("Stock In", "Stock Out"):
                # Pair the sample movements so they leave the seeded inventory quantity unchanged.
                delta = 1 if transaction_type == "Stock In" else -1
                cur.execute("UPDATE item SET qty_on_hand=qty_on_hand+%s WHERE item_id=%s", (delta, demo_item["item_id"]))
                cur.execute("""INSERT INTO transaction_log(item_id,admin_id,supplier_id,item_qty,transaction_type,status,
                        unit_cost_at_time,required_date,notes)
                    VALUES(%s,%s,%s,1,%s,'Fulfilled',%s,NOW(),%s)""",
                    (demo_item["item_id"], admin_id, demo_item["supplier_id"] if transaction_type == "Stock In" else None,
                     transaction_type, demo_item["baseline_unit_cost"], f"Admin dashboard sample activity: {transaction_type} {index}/3"))
        cur.execute("SELECT item_id FROM item WHERE qty_on_hand<=reorder_threshold AND archived_at IS NULL")
        initial_alerts = [inventory.record_low_stock_transition(conn, row["item_id"]) for row in cur.fetchall()]
        conn.commit()
    for alert in initial_alerts:
        if alert:
            inventory.deliver_low_stock_alert(alert)
    print("Demo data created. Admin login: admin@dundermifflin.local")
    print(f"Admin password (save now): {admin_password}")
    print("Personnel login: pam@dundermifflin.local or jim@dundermifflin.local")
    print(f"Personnel password (save now): {personnel_password}")


@app.cli.command("seed-admin-activity")
def seed_admin_activity():
    """Add six balanced example stock movements for the admin dashboard."""
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT admin_id FROM inventory_admin ORDER BY admin_id LIMIT 1")
        admin = cur.fetchone()
        if not admin:
            print("No administrator exists; create the demo account first.")
            return
        cur.execute("SELECT COUNT(*) n FROM transaction_log WHERE notes LIKE 'Admin dashboard sample activity:%'")
        if cur.fetchone()["n"] >= 6:
            print("Admin dashboard sample activity already exists.")
            return
        cur.execute("""SELECT item_id,item_name,supplier_id,baseline_unit_cost FROM item
            WHERE archived_at IS NULL AND qty_on_hand>0 ORDER BY item_id LIMIT 3""")
        sample_items = cur.fetchall()
        if len(sample_items) < 3:
            print("At least three active, in-stock items are needed to add sample activity.")
            return
        for index, item in enumerate(sample_items, start=1):
            for transaction_type in ("Stock In", "Stock Out"):
                delta = 1 if transaction_type == "Stock In" else -1
                cur.execute("UPDATE item SET qty_on_hand=qty_on_hand+%s WHERE item_id=%s", (delta, item["item_id"]))
                cur.execute("""INSERT INTO transaction_log(item_id,admin_id,supplier_id,item_qty,transaction_type,status,
                        unit_cost_at_time,required_date,notes)
                    VALUES(%s,%s,%s,1,%s,'Fulfilled',%s,NOW(),%s)""",
                    (item["item_id"], admin["admin_id"], item["supplier_id"] if transaction_type == "Stock In" else None,
                     transaction_type, item["baseline_unit_cost"], f"Admin dashboard sample activity: {transaction_type} {index}/3"))
        conn.commit()
    print("Added three Stock In and three Stock Out admin activity records.")


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
