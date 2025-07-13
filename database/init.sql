-- database/init.sql
-- This script runs automatically when PostgreSQL container starts

-- Create schemas for different data layers
CREATE SCHEMA IF NOT EXISTS staging;     -- Raw CSV data
CREATE SCHEMA IF NOT EXISTS warehouse;   -- Star schema (dimensional model)
CREATE SCHEMA IF NOT EXISTS analytics;   -- Business KPIs and aggregated data

-- Grant permissions to our user
GRANT ALL PRIVILEGES ON SCHEMA staging TO analytics_user;
GRANT ALL PRIVILEGES ON SCHEMA warehouse TO analytics_user;
GRANT ALL PRIVILEGES ON SCHEMA analytics TO analytics_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA staging GRANT ALL ON TABLES TO analytics_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA warehouse GRANT ALL ON TABLES TO analytics_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT ALL ON TABLES TO analytics_user;

-- ===================================
-- STAGING SCHEMA - Raw CSV Data
-- ===================================

-- Staging tables that match your CSV structure exactly
CREATE TABLE staging.customers (
    customer_id VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),
    date_of_birth DATE,
    gender VARCHAR(10),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    registration_date DATE,
    customer_segment VARCHAR(50),
    preferred_category VARCHAR(100),
    marketing_consent BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staging.products (
    product_id VARCHAR(20) PRIMARY KEY,
    product_name VARCHAR(255),
    description TEXT,
    category VARCHAR(100),
    subcategory VARCHAR(100),
    brand VARCHAR(100),
    sku VARCHAR(50),
    cost_price DECIMAL(10,2),
    selling_price DECIMAL(10,2),
    weight_kg DECIMAL(8,2),
    dimensions VARCHAR(50),
    color VARCHAR(50),
    size VARCHAR(20),
    rating DECIMAL(3,1),
    launch_date DATE,
    is_active BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staging.orders (
    order_id VARCHAR(20) PRIMARY KEY,
    customer_id VARCHAR(20),
    order_date DATE,
    order_status VARCHAR(50),
    payment_method VARCHAR(50),
    subtotal DECIMAL(12,2),
    discount_amount DECIMAL(12,2),
    shipping_cost DECIMAL(8,2),
    tax_amount DECIMAL(10,2),
    total_amount DECIMAL(12,2),
    shipping_address TEXT,
    delivery_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staging.order_items (
    order_item_id VARCHAR(20) PRIMARY KEY,
    order_id VARCHAR(20),
    product_id VARCHAR(20),
    quantity INTEGER,
    unit_price DECIMAL(10,2),
    total_price DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staging.clickstream (
    event_id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(100),
    customer_id VARCHAR(20),
    product_id VARCHAR(20),
    event_type VARCHAR(50),
    page_url VARCHAR(500),
    referrer_url VARCHAR(500),
    user_agent TEXT,
    device_type VARCHAR(50),
    browser VARCHAR(50),
    ip_address INET,
    country VARCHAR(100),
    city VARCHAR(100),
    timestamp TIMESTAMP,
    duration_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staging.marketing_campaigns (
    campaign_id VARCHAR(20) PRIMARY KEY,
    campaign_name VARCHAR(255),
    channel VARCHAR(100),
    start_date DATE,
    end_date DATE,
    budget DECIMAL(12,2),
    target_audience VARCHAR(100),
    objective VARCHAR(100),
    impressions INTEGER,
    clicks INTEGER,
    conversions INTEGER,
    cost_per_click DECIMAL(8,2),
    conversion_rate DECIMAL(5,2),
    roi DECIMAL(8,2),
    is_active BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staging.inventory (
    inventory_id VARCHAR(20) PRIMARY KEY,
    product_id VARCHAR(20),
    warehouse_location VARCHAR(100),
    current_stock INTEGER,
    reserved_stock INTEGER,
    reorder_point INTEGER,
    max_stock INTEGER,
    last_restocked DATE,
    supplier_id VARCHAR(20),
    lead_time_days INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===================================
-- WAREHOUSE SCHEMA - Star Schema
-- ===================================

-- Dimension Tables
CREATE TABLE warehouse.dim_customers (
    customer_key SERIAL PRIMARY KEY,
    customer_id VARCHAR(20) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(255),
    email VARCHAR(255),
    customer_segment VARCHAR(50),
    preferred_category VARCHAR(100),
    city VARCHAR(100),
    country VARCHAR(100),
    registration_date DATE,
    -- SCD Type 2 fields
    effective_date DATE DEFAULT CURRENT_DATE,
    expiry_date DATE DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE warehouse.dim_products (
    product_key SERIAL PRIMARY KEY,
    product_id VARCHAR(20) UNIQUE NOT NULL,
    product_name VARCHAR(255),
    category VARCHAR(100),
    subcategory VARCHAR(100),
    brand VARCHAR(100),
    cost_price DECIMAL(10,2),
    selling_price DECIMAL(10,2),
    profit_margin DECIMAL(5,2),
    rating DECIMAL(3,1),
    launch_date DATE,
    is_active BOOLEAN,
    -- SCD Type 2 fields
    effective_date DATE DEFAULT CURRENT_DATE,
    expiry_date DATE DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE warehouse.dim_time (
    time_key INTEGER PRIMARY KEY,
    full_date DATE UNIQUE NOT NULL,
    day_of_week INTEGER,
    day_name VARCHAR(10),
    day_of_month INTEGER,
    day_of_year INTEGER,
    week_of_year INTEGER,
    month_number INTEGER,
    month_name VARCHAR(10),
    quarter INTEGER,
    year INTEGER,
    is_weekend BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fact Tables
CREATE TABLE warehouse.fact_orders (
    order_key SERIAL,
    order_id VARCHAR(20) NOT NULL,
    customer_key INTEGER REFERENCES warehouse.dim_customers(customer_key),
    order_date_key INTEGER REFERENCES warehouse.dim_time(time_key),
    order_status VARCHAR(50),
    payment_method VARCHAR(50),
    subtotal DECIMAL(12,2),
    discount_amount DECIMAL(12,2),
    shipping_cost DECIMAL(8,2),
    tax_amount DECIMAL(10,2),
    total_amount DECIMAL(12,2),
    profit_amount DECIMAL(12,2),
    total_items INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (order_date_key);


-- Create partitions for all ranges
CREATE TABLE warehouse.fact_orders_202407 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20240701) TO (20240801);
CREATE TABLE warehouse.fact_orders_202408 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20240801) TO (20240901);
CREATE TABLE warehouse.fact_orders_202409 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20240901) TO (20241001);
CREATE TABLE warehouse.fact_orders_202410 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20241001) TO (20241101);
CREATE TABLE warehouse.fact_orders_202411 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20241101) TO (20241201);
CREATE TABLE warehouse.fact_orders_202412 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20241201) TO (20250101);
CREATE TABLE warehouse.fact_orders_202501 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20250101) TO (20250201);
CREATE TABLE warehouse.fact_orders_202502 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20250201) TO (20250301);
CREATE TABLE warehouse.fact_orders_202503 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20250301) TO (20250401);
CREATE TABLE warehouse.fact_orders_202504 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20250401) TO (20250501);
CREATE TABLE warehouse.fact_orders_202505 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20250501) TO (20250601);
CREATE TABLE warehouse.fact_orders_202506 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20250601) TO (20250701);
CREATE TABLE warehouse.fact_orders_202507 PARTITION OF warehouse.fact_orders FOR VALUES FROM (20250701) TO (20250801);

-- Default partition for any other dates
CREATE TABLE warehouse.fact_orders_default PARTITION OF warehouse.fact_orders DEFAULT;


CREATE TABLE warehouse.fact_order_items (
    order_item_key SERIAL,
    order_key INTEGER,
    product_key INTEGER REFERENCES warehouse.dim_products(product_key),
    customer_key INTEGER REFERENCES warehouse.dim_customers(customer_key),
    order_date_key INTEGER,
    quantity INTEGER,
    unit_price DECIMAL(10,2),
    total_price DECIMAL(12,2),
    unit_cost DECIMAL(10,2),
    profit_amount DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (order_date_key);

-- Create partitions for all ranges
CREATE TABLE warehouse.fact_order_items_202407 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20240701) TO (20240801);
CREATE TABLE warehouse.fact_order_items_202408 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20240801) TO (20240901);
CREATE TABLE warehouse.fact_order_items_202409 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20240901) TO (20241001);
CREATE TABLE warehouse.fact_order_items_202410 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20241001) TO (20241101);
CREATE TABLE warehouse.fact_order_items_202411 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20241101) TO (20241201);
CREATE TABLE warehouse.fact_order_items_202412 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20241201) TO (20250101);
CREATE TABLE warehouse.fact_order_items_202501 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20250101) TO (20250201);
CREATE TABLE warehouse.fact_order_items_202502 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20250201) TO (20250301);
CREATE TABLE warehouse.fact_order_items_202503 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20250301) TO (20250401);
CREATE TABLE warehouse.fact_order_items_202504 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20250401) TO (20250501);
CREATE TABLE warehouse.fact_order_items_202505 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20250501) TO (20250601);
CREATE TABLE warehouse.fact_order_items_202506 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20250601) TO (20250701);
CREATE TABLE warehouse.fact_order_items_202507 PARTITION OF warehouse.fact_order_items FOR VALUES FROM (20250701) TO (20250801);

-- Default partition for order items
CREATE TABLE warehouse.fact_order_items_default PARTITION OF warehouse.fact_order_items DEFAULT;


CREATE TABLE warehouse.fact_clickstream (
    clickstream_key SERIAL PRIMARY KEY,
    event_id VARCHAR(50) UNIQUE NOT NULL,
    customer_key INTEGER REFERENCES warehouse.dim_customers(customer_key),
    product_key INTEGER REFERENCES warehouse.dim_products(product_key),
    event_date_key INTEGER REFERENCES warehouse.dim_time(time_key),
    event_type VARCHAR(50),
    session_id VARCHAR(100),
    device_type VARCHAR(50),
    browser VARCHAR(50),
    duration_seconds INTEGER,
    timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE warehouse.fact_inventory (
    inventory_key SERIAL PRIMARY KEY,
    product_key INTEGER REFERENCES warehouse.dim_products(product_key),
    warehouse_location VARCHAR(100), 
    current_stock INTEGER,
    reserved_stock INTEGER,
    reorder_point INTEGER,
    max_stock INTEGER,
    last_restocked_key INTEGER REFERENCES warehouse.dim_time(time_key),
    supplier_id VARCHAR(20),
    lead_time_days INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fact_inventory_product ON warehouse.fact_inventory(product_key);
CREATE INDEX idx_fact_inventory_warehouse ON warehouse.fact_inventory(warehouse_location);


CREATE TABLE warehouse.dim_marketing_campaigns (
    campaign_key SERIAL PRIMARY KEY,
    campaign_id VARCHAR(20) UNIQUE NOT NULL,
    campaign_name VARCHAR(255),
    channel VARCHAR(100),
    start_date_key INTEGER REFERENCES warehouse.dim_time(time_key),
    end_date_key INTEGER REFERENCES warehouse.dim_time(time_key),
    budget DECIMAL(12,2),
    target_audience VARCHAR(100),
    objective VARCHAR(100),
    impressions INTEGER,
    clicks INTEGER,
    conversions INTEGER,
    cost_per_click DECIMAL(8,2),
    conversion_rate DECIMAL(5,2),
    roi DECIMAL(8,2),
    is_active BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_campaigns_channel ON warehouse.dim_marketing_campaigns(channel);
CREATE INDEX idx_dim_campaigns_active ON warehouse.dim_marketing_campaigns(is_active);


-- ===================================
-- ANALYTICS SCHEMA - Business KPIs
-- ===================================

-- Customer Analytics
CREATE TABLE analytics.customer_metrics (
    customer_id VARCHAR(20) PRIMARY KEY,
    total_orders INTEGER,
    total_spent DECIMAL(12,2),
    avg_order_value DECIMAL(10,2),
    lifetime_value DECIMAL(12,2),
    first_order_date DATE,
    last_order_date DATE,
    days_since_last_order INTEGER,
    customer_segment VARCHAR(50),
    churn_risk_score DECIMAL(3,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product Analytics  
CREATE TABLE analytics.product_metrics (
    product_id VARCHAR(20) PRIMARY KEY,
    total_revenue DECIMAL(12,2),
    total_orders INTEGER,
    total_quantity_sold INTEGER,
    avg_rating DECIMAL(3,1),
    profit_margin DECIMAL(5,2),
    inventory_turnover DECIMAL(8,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily Sales Summary
CREATE TABLE analytics.daily_sales (
    sales_date DATE PRIMARY KEY,
    total_orders INTEGER,
    total_revenue DECIMAL(12,2),
    total_profit DECIMAL(12,2),
    avg_order_value DECIMAL(10,2),
    unique_customers INTEGER,
    new_customers INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===================================
-- Indexes for Performance
-- ===================================

-- Staging indexes
CREATE INDEX idx_staging_orders_customer_id ON staging.orders(customer_id);
CREATE INDEX idx_staging_orders_date ON staging.orders(order_date);
CREATE INDEX idx_staging_order_items_order_id ON staging.order_items(order_id);
CREATE INDEX idx_staging_clickstream_customer ON staging.clickstream(customer_id);
CREATE INDEX idx_staging_clickstream_timestamp ON staging.clickstream(timestamp);

-- Warehouse indexes
CREATE INDEX idx_dim_customers_segment ON warehouse.dim_customers(customer_segment);
CREATE INDEX idx_dim_products_category ON warehouse.dim_products(category);
CREATE INDEX idx_fact_orders_date_key ON warehouse.fact_orders(order_date_key);
CREATE INDEX idx_fact_orders_customer_key ON warehouse.fact_orders(customer_key);