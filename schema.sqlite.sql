-- SQLite schema for a new Inventory System database.
-- Do not execute this against an existing database; it creates the tables.
PRAGMA foreign_keys = ON;

CREATE TABLE supplier (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL,
    contact_num TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at DATETIME NULL
);

CREATE TABLE shelf (
    shelf_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shelf_num INTEGER NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at DATETIME NULL
);

CREATE TABLE office_personnel (
    personnel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    personnel_name TEXT NOT NULL,
    department TEXT NOT NULL
);

CREATE TABLE inventory_admin (
    admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_name TEXT NOT NULL
);

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'personnel')),
    personnel_id INTEGER NULL UNIQUE,
    admin_id INTEGER NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (personnel_id) REFERENCES office_personnel(personnel_id),
    FOREIGN KEY (admin_id) REFERENCES inventory_admin(admin_id),
    CHECK ((role='admin' AND admin_id IS NOT NULL AND personnel_id IS NULL)
        OR (role='personnel' AND personnel_id IS NOT NULL AND admin_id IS NULL))
);

CREATE TABLE item (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    shelf_id INTEGER NOT NULL,
    item_name TEXT NOT NULL,
    item_description TEXT NOT NULL,
    item_category TEXT NOT NULL,
    unit_name TEXT NOT NULL DEFAULT 'Piece',
    qty_on_hand INTEGER NOT NULL DEFAULT 0 CHECK (qty_on_hand >= 0),
    reorder_threshold INTEGER NOT NULL DEFAULT 0 CHECK (reorder_threshold >= 0),
    baseline_unit_cost NUMERIC NOT NULL DEFAULT 0.00 CHECK (baseline_unit_cost >= 0),
    low_stock_active INTEGER NOT NULL DEFAULT 0 CHECK (low_stock_active IN (0, 1)),
    low_stock_episode INTEGER NOT NULL DEFAULT 0,
    archived_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES supplier(supplier_id),
    FOREIGN KEY (shelf_id) REFERENCES shelf(shelf_id)
);

CREATE INDEX idx_item_stock ON item (archived_at, qty_on_hand, reorder_threshold);

CREATE TRIGGER item_updated_at
AFTER UPDATE ON item
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE item SET updated_at = CURRENT_TIMESTAMP WHERE item_id = NEW.item_id;
END;

CREATE TABLE supply_request (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    personnel_id INTEGER NOT NULL,
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    required_date DATETIME NOT NULL,
    notes TEXT NULL,
    cancelled_at DATETIME NULL,
    reviewed_by_admin_id INTEGER NULL,
    reviewed_at DATETIME NULL,
    review_notes TEXT NULL,
    FOREIGN KEY (personnel_id) REFERENCES office_personnel(personnel_id),
    FOREIGN KEY (reviewed_by_admin_id) REFERENCES inventory_admin(admin_id)
);

CREATE INDEX idx_request_personnel_date ON supply_request (personnel_id, requested_at);

CREATE TABLE transaction_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NULL,
    item_id INTEGER NOT NULL,
    personnel_id INTEGER NULL,
    admin_id INTEGER NULL,
    supplier_id INTEGER NULL,
    item_qty INTEGER NOT NULL CHECK (item_qty > 0),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('Stock Out', 'Stock In')),
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Declined', 'Fulfilled')),
    unit_cost_at_time NUMERIC NOT NULL DEFAULT 0.00 CHECK (unit_cost_at_time >= 0),
    transaction_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    required_date DATETIME NOT NULL,
    notes TEXT NULL,
    FOREIGN KEY (request_id) REFERENCES supply_request(request_id),
    FOREIGN KEY (item_id) REFERENCES item(item_id),
    FOREIGN KEY (personnel_id) REFERENCES office_personnel(personnel_id),
    FOREIGN KEY (admin_id) REFERENCES inventory_admin(admin_id),
    FOREIGN KEY (supplier_id) REFERENCES supplier(supplier_id)
);

CREATE INDEX idx_log_date ON transaction_log (transaction_date);
CREATE INDEX idx_log_status ON transaction_log (status, transaction_type);
CREATE INDEX idx_log_request ON transaction_log (request_id);

CREATE TABLE low_stock_alert (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    episode_no INTEGER NOT NULL,
    quantity_at_trigger INTEGER NOT NULL,
    threshold_at_trigger INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK (delivery_status IN ('pending', 'sent', 'failed')),
    delivered_at DATETIME NULL,
    last_error TEXT NULL,
    FOREIGN KEY (item_id) REFERENCES item(item_id),
    UNIQUE (item_id, episode_no)
);
