"""Item entity from the mini-SRS Item class."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping


@dataclass(slots=True)
class Item:
    item_id: int
    item_name: str
    item_description: str
    item_category: str
    unit_name: str
    supplier_id: int
    shelf_id: int
    qty_on_hand: int
    reorder_threshold: int
    baseline_unit_cost: Decimal
    low_stock_active: bool = False
    low_stock_episode: int = 0

    @property
    def is_low_stock(self) -> bool:
        return self.qty_on_hand <= self.reorder_threshold

    @classmethod
    def from_record(cls, row: Mapping[str, Any]) -> "Item":
        return cls(
            item_id=int(row["item_id"]), item_name=str(row["item_name"]),
            item_description=str(row.get("item_description", "")),
            item_category=str(row.get("item_category", "")),
            unit_name=str(row.get("unit_name", "Piece")),
            supplier_id=int(row.get("supplier_id", 0)), shelf_id=int(row.get("shelf_id", 0)),
            qty_on_hand=int(row["qty_on_hand"]), reorder_threshold=int(row["reorder_threshold"]),
            baseline_unit_cost=Decimal(str(row.get("baseline_unit_cost", 0))),
            low_stock_active=bool(row.get("low_stock_active", False)),
            low_stock_episode=int(row.get("low_stock_episode", 0)),
        )
