"""TransactionLog entity from the mini-SRS TransactionLog class."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class TransactionLog:
    log_id: int
    item_id: int
    item_qty: int
    transaction_type: str
    status: str
    unit_cost_at_time: Decimal
    transaction_date: Any
    required_date: Any
    personnel_id: int | None = None
    admin_id: int | None = None
    supplier_id: int | None = None
    request_id: int | None = None
