"""Authentication and inventory business rules."""

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Any

from werkzeug.security import check_password_hash

from .database import Database
from .inventory_admin import InventoryAdmin
from .item import Item
from .office_personnel import OfficePersonnel


class AuthenticationService:
    def __init__(self, database: Database):
        self.database = database

    def authenticate(self, email: str, password: str) -> InventoryAdmin | OfficePersonnel | None:
        row = self.database.fetch_one(
            """SELECT u.*,p.personnel_name,p.department,a.admin_name FROM users u
            LEFT JOIN office_personnel p ON p.personnel_id=u.personnel_id
            LEFT JOIN inventory_admin a ON a.admin_id=u.admin_id
            WHERE u.email=%s AND u.active=1 LIMIT 1""",
            (email.strip().lower(),),
        )
        if not row or not check_password_hash(row["password_hash"], password):
            return None
        if row["role"] == "admin":
            return InventoryAdmin.from_auth_record(row)
        return OfficePersonnel.from_auth_record(row)


class InventoryService:
    def __init__(self, database: Database):
        self.database = database

    def record_low_stock_transition(self, connection, item_id: int):
        """Persist one unique alert for an item's transition below its threshold."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM item WHERE item_id=%s FOR UPDATE", (item_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = Item.from_record(row)
            if item.is_low_stock and not item.low_stock_active:
                episode = item.low_stock_episode + 1
                cursor.execute(
                    "UPDATE item SET low_stock_active=1,low_stock_episode=%s WHERE item_id=%s",
                    (episode, item.item_id),
                )
                cursor.execute(
                    """INSERT INTO low_stock_alert(item_id,episode_no,quantity_at_trigger,threshold_at_trigger)
                    VALUES(%s,%s,%s,%s)""",
                    (item.item_id, episode, item.qty_on_hand, item.reorder_threshold),
                )
                return {
                    "alert_id": cursor.lastrowid, "name": item.item_name,
                    "qty": item.qty_on_hand, "threshold": item.reorder_threshold,
                }
            if not item.is_low_stock and item.low_stock_active:
                cursor.execute("UPDATE item SET low_stock_active=0 WHERE item_id=%s", (item.item_id,))
        return None

    def fulfill_request(self, connection, request_row: dict[str, Any], admin_id: int):
        with connection.cursor() as cursor:
            if request_row["status"] != "Approved":
                raise ValueError("Approve this request before fulfilling it.")
            cursor.execute(
                "SELECT qty_on_hand FROM item WHERE item_id=%s AND archived_at IS NULL FOR UPDATE",
                (request_row["item_id"],),
            )
            item = cursor.fetchone()
            if not item or item["qty_on_hand"] < request_row["item_qty"]:
                raise ValueError("There is not enough stock to fulfill this request.")
            cursor.execute(
                "UPDATE item SET qty_on_hand=qty_on_hand-%s WHERE item_id=%s",
                (request_row["item_qty"], request_row["item_id"]),
            )
            cursor.execute(
                "UPDATE transaction_log SET status='Fulfilled',admin_id=%s WHERE log_id=%s",
                (admin_id, request_row["log_id"]),
            )
        return self.record_low_stock_transition(connection, request_row["item_id"])

    def deliver_low_stock_alert(self, alert: dict[str, Any]) -> None:
        """Attempt immediate mail delivery and retain the result on the alert."""
        status, error, delivered = "failed", "SMTP settings are missing.", None
        try:
            recipients = [row["email"] for row in self.database.fetch_all(
                "SELECT email FROM users WHERE role='admin' AND active=1"
            )]
            host, sender = os.getenv("SMTP_HOST"), os.getenv("MAIL_FROM")
            if not host or not sender or not recipients:
                raise RuntimeError("Configure SMTP_HOST and MAIL_FROM, and add an active admin account.")
            message = EmailMessage()
            message["Subject"] = f"Low stock alert: {alert['name']}"
            message["From"] = sender
            message["To"] = ", ".join(recipients)
            message.set_content(
                f"{alert['name']} is at {alert['qty']} unit(s), at or below its reorder threshold of "
                f"{alert['threshold']}. Please review the inventory."
            )
            with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587")), timeout=5) as smtp:
                if os.getenv("SMTP_STARTTLS", "1") == "1":
                    smtp.starttls()
                smtp.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", ""))
                smtp.send_message(message)
            status, error, delivered = "sent", None, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as exc:
            error = str(exc)[:255]
        with self.database.connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE low_stock_alert SET delivery_status=%s,delivered_at=%s,last_error=%s
                WHERE alert_id=%s AND delivery_status='pending'""",
                (status, delivered, error, alert["alert_id"]),
            )
            connection.commit()
