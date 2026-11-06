"""OfficePersonnel role and supply-request behavior from the mini-SRS."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class OfficePersonnel:
    personnel_id: int
    personnel_name: str
    department: str
    account_id: int = 0
    email: str = ""

    @property
    def role(self) -> str:
        return "personnel"

    @property
    def name(self) -> str:
        return self.personnel_name

    @classmethod
    def from_auth_record(cls, row: Mapping[str, Any]) -> "OfficePersonnel":
        return cls(
            personnel_id=int(row["personnel_id"]),
            personnel_name=str(row.get("personnel_name") or ""),
            department=str(row.get("department") or ""),
            account_id=int(row["user_id"]),
            email=str(row["email"]),
        )

    def request_supply(self, connection, request_id: int, item_id: int, item_qty: int, required_date: datetime, notes: str | None = None) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO transaction_log(request_id,item_id,personnel_id,item_qty,transaction_type,status,unit_cost_at_time,required_date,notes)
                SELECT %s,item_id,%s,%s,'Stock Out','Pending',baseline_unit_cost,%s,%s
                FROM item WHERE item_id=%s AND archived_at IS NULL""",
                (request_id, self.personnel_id, item_qty, required_date.replace(hour=17).strftime("%Y-%m-%d %H:%M:%S"), notes, item_id),
            )
            if not cursor.rowcount:
                raise ValueError("That inventory item is unavailable.")
            return int(cursor.lastrowid)
