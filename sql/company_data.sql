CREATE DATABASE IF NOT EXISTS company_data CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE company_data;

CREATE TABLE IF NOT EXISTS companies (
    id INT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    sector VARCHAR(80) NOT NULL,
    employees INT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INT PRIMARY KEY,
    company_id INT NOT NULL,
    name VARCHAR(120) NOT NULL,
    category VARCHAR(80) NOT NULL,
    annual_revenue DECIMAL(14, 2) NOT NULL,
    CONSTRAINT fk_products_company FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS sales (
    id INT PRIMARY KEY,
    product_id INT NOT NULL,
    region VARCHAR(40) NOT NULL,
    quarter VARCHAR(10) NOT NULL,
    revenue DECIMAL(14, 2) NOT NULL,
    CONSTRAINT fk_sales_product FOREIGN KEY (product_id) REFERENCES products(id)
);

INSERT INTO companies (id, name, sector, employees) VALUES
    (1, 'Northstar Labs', 'Healthcare', 420),
    (2, 'Cedar Analytics', 'Software', 180),
    (3, 'Harbor Devices', 'Manufacturing', 760)
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO products (id, company_id, name, category, annual_revenue) VALUES
    (1, 1, 'Aster', 'Diagnostics', 12500000.00),
    (2, 1, 'Beacon', 'Research tools', 8200000.00),
    (3, 2, 'Compass', 'Analytics', 9600000.00),
    (4, 3, 'Delta', 'Sensors', 15100000.00)
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO sales (id, product_id, region, quarter, revenue) VALUES
    (1, 1, 'East', '2026-Q1', 3100000.00),
    (2, 1, 'West', '2026-Q1', 2950000.00),
    (3, 3, 'East', '2026-Q1', 2400000.00),
    (4, 4, 'North', '2026-Q1', 3820000.00)
ON DUPLICATE KEY UPDATE revenue = VALUES(revenue);

