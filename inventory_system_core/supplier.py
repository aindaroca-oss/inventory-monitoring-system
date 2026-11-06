"""Supplier entity from the mini-SRS Supplier class."""

from dataclasses import dataclass


@dataclass(slots=True)
class Supplier:
    supplier_id: int
    name: str
    contact_num: str
    email: str
