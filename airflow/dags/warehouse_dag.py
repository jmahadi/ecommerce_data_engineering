from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from sqlalchemy import create_engine, text
import logging

default_args = {
    'owner': 'analytics_team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'warehouse_transformation',
    default_args=default_args,
    description='Transform staging data to dimensional warehouse model',
    schedule_interval='@daily',
    catchup=False,
    tags=['warehouse', 'etl', 'dimensional']
)

def get_db_connection():
    """Get database connection"""
    connection_string = "postgresql://analytics_user:analytics_pass@postgres:5432/ecommerce_analytics"
    return create_engine(connection_string)

def transform_customers_dimension():
    """Transform customers with SCD Type 2 using MERGE"""
    logging.info("Transforming customers dimension...")
    
    engine = get_db_connection()
    
    # Step 1: Close existing records that have changed
    close_changed_sql = text("""
    UPDATE warehouse.dim_customers 
    SET expiry_date = CURRENT_DATE - INTERVAL '1 day',
        is_current = false
    WHERE customer_id IN (
        SELECT s.customer_id 
        FROM staging.customers s
        JOIN warehouse.dim_customers w ON s.customer_id = w.customer_id 
        WHERE w.is_current = true
        AND (s.customer_segment != w.customer_segment 
             OR s.city != w.city 
             OR s.country != w.country)
    ) AND is_current = true;
    """)
    
    # Step 2: Insert new and changed customers
    insert_customers_sql = text("""
    INSERT INTO warehouse.dim_customers 
    (customer_id, first_name, last_name, full_name, email, customer_segment, 
     preferred_category, city, country, registration_date, effective_date, expiry_date, is_current)
    SELECT 
        s.customer_id,
        s.first_name,
        s.last_name,
        s.first_name || ' ' || s.last_name as full_name,
        s.email,
        s.customer_segment,
        s.preferred_category,
        s.city,
        s.country,
        s.registration_date::date,
        CURRENT_DATE as effective_date,
        '9999-12-31'::date as expiry_date,
        true as is_current
    FROM staging.customers s
    LEFT JOIN warehouse.dim_customers w ON s.customer_id = w.customer_id AND w.is_current = true
    WHERE w.customer_id IS NULL 
       OR (s.customer_segment != w.customer_segment 
           OR s.city != w.city 
           OR s.country != w.country);
    """)
    
    try:
        with engine.begin() as conn:  # Use begin() for auto-commit
            # Execute both steps
            conn.execute(close_changed_sql)
            conn.execute(insert_customers_sql)
        
        logging.info("Customers dimension transformation completed")
        
    except Exception as e:
        logging.error(f"Failed to transform customers dimension: {e}")
        raise
    finally:
        engine.dispose()

def transform_products_dimension():
    """Transform products with SCD Type 2"""
    logging.info("Transforming products dimension...")
    
    engine = get_db_connection()
    
    scd_sql = text("""
    -- Close existing records that have changed
    UPDATE warehouse.dim_products 
    SET expiry_date = CURRENT_DATE - INTERVAL '1 day',
        is_current = false
    WHERE product_id IN (
        SELECT s.product_id 
        FROM staging.products s
        JOIN warehouse.dim_products w ON s.product_id = w.product_id 
        WHERE w.is_current = true
        AND (s.cost_price != w.cost_price 
             OR s.selling_price != w.selling_price 
             OR s.is_active != w.is_active)
    ) AND is_current = true;
    
    -- Insert new and changed products
    INSERT INTO warehouse.dim_products 
    (product_id, product_name, category, subcategory, brand, cost_price, 
     selling_price, profit_margin, rating, launch_date, is_active, 
     effective_date, expiry_date, is_current)
    SELECT 
        s.product_id,
        s.product_name,
        s.category,
        s.subcategory,
        s.brand,
        s.cost_price::numeric,
        s.selling_price::numeric,
        ROUND(((s.selling_price::numeric - s.cost_price::numeric) / s.selling_price::numeric * 100), 2) as profit_margin,
        s.rating::numeric,
        s.launch_date::date,
        s.is_active::boolean,
        CURRENT_DATE as effective_date,
        '9999-12-31'::date as expiry_date,
        true as is_current
    FROM staging.products s
    LEFT JOIN warehouse.dim_products w ON s.product_id = w.product_id AND w.is_current = true
    WHERE w.product_id IS NULL 
       OR (s.cost_price != w.cost_price 
           OR s.selling_price != w.selling_price 
           OR s.is_active != w.is_active);
    """)
    
    try:
        with engine.begin() as conn:
            result = conn.execute(scd_sql)
        
        logging.info("Products dimension transformation completed")
        
    except Exception as e:
        logging.error(f"Failed to transform products dimension: {e}")
        raise
    finally:
        engine.dispose()

def load_time_dimension():
    """Load time dimension with new dates only"""
    logging.info("Loading time dimension...")
    
    engine = get_db_connection()
    
    time_sql = text("""
    INSERT INTO warehouse.dim_time 
    (time_key, full_date, day_of_week, day_name, day_of_month, day_of_year,
     week_of_year, month_number, month_name, quarter, year, is_weekend)
    SELECT DISTINCT
        TO_CHAR(order_date::date, 'YYYYMMDD')::INTEGER as time_key,
        order_date::date as full_date,
        EXTRACT(DOW FROM order_date::date) as day_of_week,
        TO_CHAR(order_date::date, 'Day') as day_name,
        EXTRACT(DAY FROM order_date::date) as day_of_month,
        EXTRACT(DOY FROM order_date::date) as day_of_year,
        EXTRACT(WEEK FROM order_date::date) as week_of_year,
        EXTRACT(MONTH FROM order_date::date) as month_number,
        TO_CHAR(order_date::date, 'Month') as month_name,
        EXTRACT(QUARTER FROM order_date::date) as quarter,
        EXTRACT(YEAR FROM order_date::date) as year,
        CASE WHEN EXTRACT(DOW FROM order_date::date) IN (0, 6) THEN true ELSE false END as is_weekend
    FROM staging.orders
    WHERE order_date::date NOT IN (SELECT full_date FROM warehouse.dim_time)
    ON CONFLICT (time_key) DO NOTHING;
    """)
    
    try:
        with engine.begin() as conn:
            result = conn.execute(time_sql)
        
        logging.info("Time dimension loaded successfully")
        
    except Exception as e:
        logging.error(f"Failed to load time dimension: {e}")
        raise
    finally:
        engine.dispose()

def load_orders_fact():
    """Load orders fact table incrementally"""
    logging.info("Loading orders fact table...")
    
    engine = get_db_connection()
    
    # Delete existing records for this batch then insert
    fact_sql = text("""
    -- Delete existing records for orders in this batch
    DELETE FROM warehouse.fact_orders 
    WHERE order_id IN (SELECT order_id FROM staging.orders);
    
    -- Insert orders fact records
    INSERT INTO warehouse.fact_orders
    (order_id, customer_key, order_date_key, order_status, payment_method,
     subtotal, discount_amount, shipping_cost, tax_amount, total_amount, profit_amount, total_items)
    SELECT 
        o.order_id,
        c.customer_key,
        TO_CHAR(o.order_date::date, 'YYYYMMDD')::INTEGER as order_date_key,
        o.order_status,
        o.payment_method,
        o.subtotal::numeric,
        COALESCE(o.discount_amount::numeric, 0),
        COALESCE(o.shipping_cost::numeric, 0),
        COALESCE(o.tax_amount::numeric, 0),
        o.total_amount::numeric,
        -- Simple profit calculation
        o.total_amount::numeric - COALESCE(o.tax_amount::numeric, 0) - COALESCE(o.shipping_cost::numeric, 0) as profit_amount,
        1 as total_items  -- Simplified for now
    FROM staging.orders o
    JOIN warehouse.dim_customers c ON o.customer_id = c.customer_id AND c.is_current = true;
    """)
    
    try:
        with engine.begin() as conn:
            result = conn.execute(fact_sql)
        
        logging.info("Orders fact table loaded successfully")
        
    except Exception as e:
        logging.error(f"Failed to load orders fact table: {e}")
        raise
    finally:
        engine.dispose()

def load_order_items_fact():
    """Load order items fact table with partitioning support"""
    logging.info("Loading order items fact table...")
    
    engine = get_db_connection()
    
    fact_items_sql = text("""
    -- Delete existing order items for this batch
    DELETE FROM warehouse.fact_order_items 
    WHERE order_key IN (
        SELECT fo.order_key 
        FROM warehouse.fact_orders fo 
        JOIN staging.orders so ON fo.order_id = so.order_id
    );
    
    -- Insert order items (include order_date_key for partitioning)
    INSERT INTO warehouse.fact_order_items
    (order_key, product_key, customer_key, order_date_key, quantity, unit_price, total_price, unit_cost, profit_amount)
    SELECT 
        fo.order_key,
        p.product_key,
        c.customer_key,
        fo.order_date_key,  -- Include for partitioning
        oi.quantity::integer,
        oi.unit_price::numeric,
        oi.total_price::numeric,
        p.cost_price as unit_cost,
        (oi.unit_price::numeric - p.cost_price) * oi.quantity::integer as profit_amount
    FROM staging.order_items oi
    JOIN warehouse.fact_orders fo ON oi.order_id = fo.order_id
    JOIN warehouse.dim_products p ON oi.product_id = p.product_id AND p.is_current = true
    JOIN warehouse.dim_customers c ON fo.customer_key = c.customer_key;
    """)
    
    try:
        with engine.begin() as conn:  # FIXED - USE begin() FOR AUTO-COMMIT
            result = conn.execute(fact_items_sql)
        
        logging.info("Order items fact table loaded successfully")
        
    except Exception as e:
        logging.error(f"Failed to load order items fact table: {e}")
        raise
    finally:
        engine.dispose()

def create_warehouse_indexes():
    """Create indexes on warehouse tables for query performance"""
    logging.info("Creating warehouse indexes...")
    
    engine = get_db_connection()
    
    # Basic indexes for common query patterns
    index_queries = [
        # Dimension table indexes
        "CREATE INDEX IF NOT EXISTS idx_dim_customers_segment ON warehouse.dim_customers(customer_segment) WHERE is_current = true;",
        "CREATE INDEX IF NOT EXISTS idx_dim_customers_current ON warehouse.dim_customers(customer_id) WHERE is_current = true;",
        "CREATE INDEX IF NOT EXISTS idx_dim_products_category ON warehouse.dim_products(category) WHERE is_current = true;",
        "CREATE INDEX IF NOT EXISTS idx_dim_products_current ON warehouse.dim_products(product_id) WHERE is_current = true;",
        
        # Fact table indexes for common joins
        "CREATE INDEX IF NOT EXISTS idx_fact_orders_customer ON warehouse.fact_orders(customer_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_orders_date ON warehouse.fact_orders(order_date_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_order_items_product ON warehouse.fact_order_items(product_key);",
        "CREATE INDEX IF NOT EXISTS idx_fact_order_items_order ON warehouse.fact_order_items(order_key);"
    ]
    
    try:
        with engine.begin() as conn:
            for query in index_queries:
                conn.execute(text(query))
        
        logging.info("Warehouse indexes created successfully")
        
    except Exception as e:
        logging.error(f"Failed to create warehouse indexes: {e}")
        raise
    finally:
        engine.dispose()

def validate_warehouse_data():
    """Basic data quality checks on warehouse tables"""
    logging.info("Running warehouse data quality checks...")
    
    engine = get_db_connection()
    
    quality_checks = [
        "SELECT COUNT(*) as current_customers FROM warehouse.dim_customers WHERE is_current = true;",
        "SELECT COUNT(*) as current_products FROM warehouse.dim_products WHERE is_current = true;",
        "SELECT COUNT(*) as fact_orders FROM warehouse.fact_orders;",
        "SELECT COUNT(*) as fact_order_items FROM warehouse.fact_order_items;",
        "SELECT COUNT(*) as orphaned_orders FROM warehouse.fact_orders fo LEFT JOIN warehouse.dim_customers dc ON fo.customer_key = dc.customer_key WHERE dc.customer_key IS NULL;"
    ]
    
    try:
        with engine.connect() as conn:  # No begin() needed for read-only operations
            for check in quality_checks:
                result = conn.execute(text(check)).fetchone()
                logging.info(f"Warehouse quality check: {check} -> {result[0]}")
        
        logging.info("Warehouse data quality checks completed")
        
    except Exception as e:
        logging.error(f"Warehouse data quality check failed: {e}")
        raise
    finally:
        engine.dispose()


def load_inventory_fact():
    """Load inventory fact table using DELETE + INSERT pattern"""
    logging.info("Loading inventory fact table...")
    
    engine = get_db_connection()
    
    try:
        # Step 1: Clear existing data
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM warehouse.fact_inventory;"))
        
        logging.info("Inventory table cleared")
        
        # Step 2: Insert fresh data
        inventory_sql = text("""
        INSERT INTO warehouse.fact_inventory
        (product_key, warehouse_location, current_stock, reserved_stock, reorder_point, 
         max_stock, last_restocked_key, supplier_id, lead_time_days)
        SELECT 
            p.product_key,
            i.warehouse_location,
            i.current_stock,
            i.reserved_stock,
            i.reorder_point,
            i.max_stock,
            COALESCE(t.time_key, 20240701) as last_restocked_key,
            i.supplier_id,
            i.lead_time_days
        FROM staging.inventory i
        JOIN warehouse.dim_products p ON i.product_id = p.product_id AND p.is_current = true
        LEFT JOIN warehouse.dim_time t ON i.last_restocked = t.full_date;
        """)
        
        with engine.begin() as conn:
            conn.execute(inventory_sql)
        
        logging.info("Inventory fact table loaded successfully")
        
    except Exception as e:
        logging.error(f"Failed to load inventory fact table: {e}")
        raise
    finally:
        engine.dispose()

def load_marketing_campaigns_dimension():
    """Load marketing campaigns dimension (includes all metrics) using DELETE + INSERT"""
    logging.info("Loading marketing campaigns dimension...")
    
    engine = get_db_connection()
    
    try:
        # Step 1: Clear existing data
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM warehouse.dim_marketing_campaigns;"))
        
        logging.info("Marketing campaigns table cleared")
        
        # Step 2: Insert fresh data (all campaign info + metrics)
        campaigns_sql = text("""
        INSERT INTO warehouse.dim_marketing_campaigns
        (campaign_id, campaign_name, channel, start_date_key, end_date_key, 
         budget, target_audience, objective, impressions, clicks, conversions,
         cost_per_click, conversion_rate, roi, is_active)
        SELECT 
            mc.campaign_id,
            mc.campaign_name,
            mc.channel,
            COALESCE(t1.time_key, 20240701) as start_date_key,
            COALESCE(t2.time_key, 20240701) as end_date_key,
            mc.budget,
            mc.target_audience,
            mc.objective,
            mc.impressions,
            mc.clicks,
            mc.conversions,
            mc.cost_per_click,
            mc.conversion_rate,
            mc.roi,
            mc.is_active
        FROM staging.marketing_campaigns mc
        LEFT JOIN warehouse.dim_time t1 ON mc.start_date = t1.full_date
        LEFT JOIN warehouse.dim_time t2 ON mc.end_date = t2.full_date;
        """)
        
        with engine.begin() as conn:
            conn.execute(campaigns_sql)
        
        logging.info("Marketing campaigns dimension loaded successfully")
        
    except Exception as e:
        logging.error(f"Failed to load marketing campaigns dimension: {e}")
        raise
    finally:
        engine.dispose()

def load_clickstream_fact():
    """Load clickstream fact table using DELETE + INSERT pattern"""
    logging.info("Loading clickstream fact table...")
    
    engine = get_db_connection()
    
    try:
        # Step 1: Clear existing data
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM warehouse.fact_clickstream;"))
        
        logging.info("Clickstream table cleared")
        
        # Step 2: Insert fresh data
        clickstream_sql = text("""
        INSERT INTO warehouse.fact_clickstream
        (event_id, customer_key, product_key, event_date_key, event_type, 
         session_id, device_type, browser, duration_seconds, timestamp)
        SELECT 
            cs.event_id,
            c.customer_key,
            p.product_key,
            COALESCE(t.time_key, 20240701) as event_date_key,
            cs.event_type,
            cs.session_id,
            cs.device_type,
            cs.browser,
            cs.duration_seconds,
            cs.timestamp
        FROM staging.clickstream cs
        LEFT JOIN warehouse.dim_customers c ON cs.customer_id = c.customer_id AND c.is_current = true
        LEFT JOIN warehouse.dim_products p ON cs.product_id = p.product_id AND p.is_current = true
        LEFT JOIN warehouse.dim_time t ON cs.timestamp::date = t.full_date;
        """)
        
        with engine.begin() as conn:
            conn.execute(clickstream_sql)
        
        logging.info("Clickstream fact table loaded successfully")
        
    except Exception as e:
        logging.error(f"Failed to load clickstream fact table: {e}")
        raise
    finally:
        engine.dispose()


# Define transformation tasks
transform_customers_task = PythonOperator(
    task_id='transform_customers_dimension',
    python_callable=transform_customers_dimension,
    dag=dag
)

transform_products_task = PythonOperator(
    task_id='transform_products_dimension',
    python_callable=transform_products_dimension,
    dag=dag
)

load_time_task = PythonOperator(
    task_id='load_time_dimension',
    python_callable=load_time_dimension,
    dag=dag
)

load_orders_fact_task = PythonOperator(
    task_id='load_orders_fact',
    python_callable=load_orders_fact,
    dag=dag
)

load_order_items_fact_task = PythonOperator(
    task_id='load_order_items_fact',
    python_callable=load_order_items_fact,
    dag=dag
)

create_indexes_task = PythonOperator(
    task_id='create_warehouse_indexes',
    python_callable=create_warehouse_indexes,
    dag=dag
)

validate_warehouse_task = PythonOperator(
    task_id='validate_warehouse_data',
    python_callable=validate_warehouse_data,
    dag=dag
)

load_inventory_fact_task = PythonOperator(
    task_id='load_inventory_fact',
    python_callable=load_inventory_fact,
    dag=dag
)

load_marketing_campaigns_task = PythonOperator(
    task_id='load_marketing_campaigns_dimension',
    python_callable=load_marketing_campaigns_dimension,
    dag=dag
)

load_clickstream_fact_task = PythonOperator(
    task_id='load_clickstream_fact',
    python_callable=load_clickstream_fact,
    dag=dag
)


# Core transformations run in parallel
[transform_customers_task, transform_products_task, load_time_task] >> load_orders_fact_task
load_orders_fact_task >> load_order_items_fact_task

# New transformations run in parallel with core ones
[transform_customers_task, transform_products_task, load_time_task] >> load_inventory_fact_task
[transform_customers_task, transform_products_task, load_time_task] >> load_marketing_campaigns_task  
[transform_customers_task, transform_products_task, load_time_task] >> load_clickstream_fact_task

# All transformations complete before indexes and validation
[load_order_items_fact_task, load_inventory_fact_task, load_marketing_campaigns_task, load_clickstream_fact_task] >> create_indexes_task >> validate_warehouse_task