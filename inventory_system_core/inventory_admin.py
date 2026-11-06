"""InventoryAdmin role and request decisions from the mini-SRS."""

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from typing import Mapping

if TYPE_CHECKING:
    from .services import InventoryService


@dataclass(slots=True)
class InventoryAdmin:
    admin_id: int
    admin_name: str
    account_id: int = 0
    email: str = ""

    @property
    def role(self) -> str:
        return "admin"

    @property
    def name(self) -> str:
        return self.admin_name

    @classmethod
    def from_auth_record(cls, row: Mapping[str, Any]) -> "InventoryAdmin":
        return cls(
            admin_id=int(row["admin_id"]),
            admin_name=str(row.get("admin_name") or ""),
            account_id=int(row["user_id"]),
            email=str(row["email"]),
        )

    def approve_request(self, connection, request_row: dict[str, Any]) -> None:
        if request_row["status"] != "Pending":
            raise ValueError("Only pending requests can be approved.")
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE transaction_log SET status='Approved',admin_id=%s WHERE log_id=%s",
                (self.admin_id, request_row["log_id"]),
            )

    def decline_request(self, connection, request_row: dict[str, Any]) -> None:
        if request_row["status"] not in {"Pending", "Approved"}:
            raise ValueError("This request can no longer be declined.")
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE transaction_log SET status='Declined',admin_id=%s WHERE log_id=%s",
                (self.admin_id, request_row["log_id"]),
            )

    def fulfill_request(self, connection, request_row: dict[str, Any], inventory_service: "InventoryService"):
        return inventory_service.fulfill_request(connection, request_row, self.admin_id)
