"""Shelf entity from the mini-SRS Shelf class."""

from dataclasses import dataclass


@dataclass(slots=True)
class Shelf:
    shelf_id: int
    shelf_num: int
