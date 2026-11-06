"""Durable low-stock event entity used for alert de-duplication."""

from dataclasses import dataclass


@dataclass(slots=True)
class LowStockAlert:
    alert_id: int
    item_id: int
    episode_no: int
    quantity_at_trigger: int
    threshold_at_trigger: int
    delivery_status: str = "pending"
