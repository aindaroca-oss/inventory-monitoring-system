-- Move the existing tables and data into the new inventory_system schema.
-- Back up dunder_inventory before running this once in phpMyAdmin.
-- This does not drop the old schema.

CREATE DATABASE IF NOT EXISTS inventory_system
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

RENAME TABLE
    dunder_inventory.supplier TO inventory_system.supplier,
    dunder_inventory.shelf TO inventory_system.shelf,
    dunder_inventory.office_personnel TO inventory_system.office_personnel,
    dunder_inventory.inventory_admin TO inventory_system.inventory_admin,
    dunder_inventory.users TO inventory_system.users,
    dunder_inventory.item TO inventory_system.item,
    dunder_inventory.supply_request TO inventory_system.supply_request,
    dunder_inventory.transaction_log TO inventory_system.transaction_log,
    dunder_inventory.low_stock_alert TO inventory_system.low_stock_alert;
