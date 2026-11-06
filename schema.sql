-- Dunder Mifflin Inventory Monitoring System
-- Import into MySQL 8.0+ (or MariaDB 10.4+) before opening the site.
CREATE DATABASE IF NOT EXISTS inventory_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE inventory_system;

CREATE TABLE IF NOT EXISTS supplier (
    supplier_id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_name VARCHAR(100) NOT NULL,
    contact_num VARCHAR(15) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at DATETIME NULL
);

CREATE TABLE IF NOT EXISTS shelf (
    shelf_id INT AUTO_INCREMENT PRIMARY KEY,
    shelf_num INT NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at DATETIME NULL
);

CREATE TABLE IF NOT EXISTS office_personnel (
    personnel_id INT AUTO_INCREMENT PRIMARY KEY,
    personnel_name VARCHAR(100) NOT NULL,
    department VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_admin (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    admin_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(190) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin','personnel') NOT NULL,
    personnel_id INT NULL UNIQUE,
    admin_id INT NULL UNIQUE,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_personnel FOREIGN KEY (personnel_id) REFERENCES office_personnel(personnel_id),
    CONSTRAINT fk_user_admin FOREIGN KEY (admin_id) REFERENCES inventory_admin(admin_id),
    CONSTRAINT chk_user_role_link CHECK ((role='admin' AND admin_id IS NOT NULL AND personnel_id IS NULL) OR (role='personnel' AND personnel_id IS NOT NULL AND admin_id IS NULL))
);

CREATE TABLE IF NOT EXISTS item (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id INT NOT NULL,
    shelf_id INT NOT NULL,
    item_name VARCHAR(100) NOT NULL,
    item_description VARCHAR(255) NOT NULL,
    item_category VARCHAR(50) NOT NULL,
    unit_name VARCHAR(30) NOT NULL DEFAULT 'Piece',
    qty_on_hand INT NOT NULL DEFAULT 0,
    reorder_threshold INT NOT NULL DEFAULT 0,
    baseline_unit_cost DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    low_stock_active TINYINT(1) NOT NULL DEFAULT 0,
    low_stock_episode INT NOT NULL DEFAULT 0,
    archived_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_item_supplier FOREIGN KEY (supplier_id) REFERENCES supplier(supplier_id),
    CONSTRAINT fk_item_shelf FOREIGN KEY (shelf_id) REFERENCES shelf(shelf_id),
    CONSTRAINT chk_item_qty CHECK (qty_on_hand >= 0),
    CONSTRAINT chk_item_threshold CHECK (reorder_threshold >= 0),
    CONSTRAINT chk_item_cost CHECK (baseline_unit_cost >= 0),
    INDEX idx_item_stock (archived_at, qty_on_hand, reorder_threshold)
);

CREATE TABLE IF NOT EXISTS supply_request (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    personnel_id INT NOT NULL,
    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    required_date DATETIME NOT NULL,
    notes VARCHAR(255) NULL,
    cancelled_at DATETIME NULL,
    reviewed_by_admin_id INT NULL,
    reviewed_at DATETIME NULL,
    review_notes VARCHAR(500) NULL,
    CONSTRAINT fk_request_personnel FOREIGN KEY (personnel_id) REFERENCES office_personnel(personnel_id),
    CONSTRAINT fk_request_admin FOREIGN KEY (reviewed_by_admin_id) REFERENCES inventory_admin(admin_id),
    INDEX idx_request_personnel_date (personnel_id, requested_at)
);

CREATE TABLE IF NOT EXISTS transaction_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NULL,
    item_id INT NOT NULL,
    personnel_id INT NULL,
    admin_id INT NULL,
    supplier_id INT NULL,
    item_qty INT NOT NULL,
    transaction_type ENUM('Stock Out','Stock In') NOT NULL,
    status ENUM('Pending','Approved','Declined','Fulfilled') NOT NULL DEFAULT 'Pending',
    unit_cost_at_time DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    transaction_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    required_date DATETIME NOT NULL,
    notes VARCHAR(255) NULL,
    CONSTRAINT fk_log_request FOREIGN KEY (request_id) REFERENCES supply_request(request_id),
    CONSTRAINT fk_log_item FOREIGN KEY (item_id) REFERENCES item(item_id),
    CONSTRAINT fk_log_personnel FOREIGN KEY (personnel_id) REFERENCES office_personnel(personnel_id),
    CONSTRAINT fk_log_admin FOREIGN KEY (admin_id) REFERENCES inventory_admin(admin_id),
    CONSTRAINT fk_log_supplier FOREIGN KEY (supplier_id) REFERENCES supplier(supplier_id),
    CONSTRAINT chk_log_qty CHECK (item_qty > 0),
    CONSTRAINT chk_log_cost CHECK (unit_cost_at_time >= 0),
    INDEX idx_log_date (transaction_date),
    INDEX idx_log_status (status, transaction_type),
    INDEX idx_log_request (request_id)
);

-- One durable alert record per low-stock episode. The item row is locked while
-- the episode counter changes, so concurrent stock updates cannot enqueue twice.
CREATE TABLE IF NOT EXISTS low_stock_alert (
    alert_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    episode_no INT NOT NULL,
    quantity_at_trigger INT NOT NULL,
    threshold_at_trigger INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    delivery_status ENUM('pending','sent','failed') NOT NULL DEFAULT 'pending',
    delivered_at DATETIME NULL,
    last_error VARCHAR(255) NULL,
    CONSTRAINT fk_alert_item FOREIGN KEY (item_id) REFERENCES item(item_id),
    CONSTRAINT uq_alert_episode UNIQUE (item_id, episode_no)
);
