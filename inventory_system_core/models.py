"""Shared import point for entity classes named in the mini-SRS.

Each SRS entity has its own module; this facade keeps imports reusable and
preserves the older ``inventory_system_core.models`` import path.
"""

from .inventory_admin import InventoryAdmin
from .item import Item
from .low_stock_alert import LowStockAlert
from .office_personnel import OfficePersonnel
from .shelf import Shelf
from .supplier import Supplier
from .transaction_log import TransactionLog

__all__ = [
    "InventoryAdmin", "Item", "LowStockAlert", "OfficePersonnel",
    "Shelf", "Supplier", "TransactionLog",
]
