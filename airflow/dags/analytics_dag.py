from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
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
    'analytics_processing',
    default_args=default_args,
    description='Create business analytics and summary tables',
    schedule_interval='@daily',
    catchup=False,
    tags=['analytics', 'metrics', 'business']
)

def get_db_connection():
    """Get database connection"""
    connection_string = "postgresql://analytics_user:analytics_pass@postgres:5432/ecommerce_analytics"
    return create_engine(connection_string)

def create_customer_metrics():
    """Calculate customer metrics with separate transactions"""
    logging.info("Creating customer metrics...")
    
    engine = get_db_connection()
    
    try:
        # Step 1: Clear table
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE analytics.customer_metrics CASCADE;"))
        
        logging.info("Customer metrics table cleared")
        
        # Step 2: Insert data
        insert_sql = text("""
        INSERT INTO analytics.customer_metrics 
        (customer_id, total_orders, total_spent, avg_order_value, lifetime_value,
         first_order_date, last_order_date, days_since_last_order, customer_segment, churn_risk_score)
        SELECT 
            c.customer_id,
            COALESCE(COUNT(fo.order_id), 0) as total_orders,
            COALESCE(SUM(fo.total_amount), 0) as total_spent,
            COALESCE(AVG(fo.total_amount), 0) as avg_order_value,
            COALESCE(SUM(fo.total_amount), 0) as lifetime_value,
            MIN(dt.full_date) as first_order_date,
            MAX(dt.full_date) as last_order_date,
            COALESCE(CURRENT_DATE - MAX(dt.full_date), 0) as days_since_last_order,
            c.customer_segment,
            CASE 
                WHEN CURRENT_DATE - MAX(dt.full_date) > 365 THEN 0.9
                WHEN CURRENT_DATE - MAX(dt.full_date) > 180 THEN 0.7
                WHEN CURRENT_DATE - MAX(dt.full_date) > 90 THEN 0.4
                ELSE 0.1
            END as churn_risk_score
        FROM warehouse.dim_customers c
        LEFT JOIN warehouse.fact_orders fo ON c.customer_key = fo.customer_key
        LEFT JOIN warehouse.dim_time dt ON fo.order_date_key = dt.time_key
        WHERE c.is_current = true
        GROUP BY c.customer_id, c.customer_key, c.customer_segment;
        """)
        
        with engine.begin() as conn:
            conn.execute(insert_sql)
        
        logging.info("Customer metrics created successfully")
        
    except Exception as e:
        logging.error(f"Failed to create customer metrics: {e}")
        raise
    finally:
        engine.dispose()

def create_product_metrics():
    """Calculate product performance metrics with separate transactions"""
    logging.info("Creating product metrics...")
    
    engine = get_db_connection()
    
    try:
        # Step 1: Clear table in separate transaction
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE analytics.product_metrics CASCADE;"))
        
        logging.info("Product metrics table cleared")
        
        # Step 2: Insert data in separate transaction
        insert_sql = text("""
        INSERT INTO analytics.product_metrics 
        (product_id, total_revenue, total_orders, total_quantity_sold, avg_rating, profit_margin, inventory_turnover)
        WITH total_inventory AS (
        SELECT 
                product_id, 
                SUM(current_stock) as total_stock
            FROM staging.inventory 
            GROUP BY product_id
        )
        SELECT 
            p.product_id,
            COALESCE(SUM(foi.total_price), 0) as total_revenue,
            COALESCE(COUNT(DISTINCT foi.order_key), 0) as total_orders,
            COALESCE(SUM(foi.quantity), 0) as total_quantity_sold,
            p.rating as avg_rating,
            p.profit_margin,
            CASE 
                WHEN i.total_stock > 0 THEN COALESCE(SUM(foi.quantity), 0) / i.total_stock 
                ELSE 0 
            END as inventory_turnover
        FROM warehouse.dim_products p
        LEFT JOIN warehouse.fact_order_items foi ON p.product_key = foi.product_key
        LEFT JOIN total_inventory i ON p.product_id = i.product_id
        WHERE p.is_current = true
        GROUP BY p.product_id, p.rating, p.profit_margin, i.total_stock;
        """)
        
        with engine.begin() as conn:
            conn.execute(insert_sql)
        
        logging.info("Product metrics created successfully")
        
    except Exception as e:
        logging.error(f"Failed to create product metrics: {e}")
        raise
    finally:
        engine.dispose()

def create_daily_sales_summary():
    """Create daily sales summary with separate transactions"""
    logging.info("Creating daily sales summary...")
    
    engine = get_db_connection()
    
    try:
        # Step 1: Clear table
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE analytics.daily_sales CASCADE;"))
        
        logging.info("Daily sales table cleared")
        
        # Step 2: Insert data
        insert_sql = text("""
        INSERT INTO analytics.daily_sales 
        (sales_date, total_orders, total_revenue, total_profit, avg_order_value, unique_customers, new_customers)
        SELECT 
            dt.full_date as sales_date,
            COUNT(fo.order_id) as total_orders,
            SUM(fo.total_amount) as total_revenue,
            SUM(fo.profit_amount) as total_profit,
            AVG(fo.total_amount) as avg_order_value,
            COUNT(DISTINCT fo.customer_key) as unique_customers,
            0 as new_customers  -- Simplified for now
        FROM warehouse.dim_time dt
        JOIN warehouse.fact_orders fo ON dt.time_key = fo.order_date_key
        GROUP BY dt.full_date;
        """)
        
        with engine.begin() as conn:
            conn.execute(insert_sql)
        
        logging.info("Daily sales summary created successfully")
        
    except Exception as e:
        logging.error(f"Failed to create daily sales summary: {e}")
        raise
    finally:
        engine.dispose()

def create_marketing_campaign_roi():
    """Calculate marketing campaign ROI if data exists"""
    logging.info("Creating marketing campaign ROI...")
    
    engine = get_db_connection()
    
    # Simple ROI calculation based on campaign period
    roi_sql = text("""
    -- This is a simplified version since we don't have direct attribution
    INSERT INTO analytics.campaign_roi 
    (campaign_id, campaign_name, total_revenue, total_orders, roi_estimate, campaign_period)
    SELECT 
        mc.campaign_id,
        mc.campaign_name,
        COALESCE(SUM(ds.total_revenue), 0) as total_revenue,
        COALESCE(SUM(ds.total_orders), 0) as total_orders,
        CASE 
            WHEN mc.budget > 0 THEN COALESCE(SUM(ds.total_revenue), 0) / mc.budget 
            ELSE 0 
        END as roi_estimate,
        mc.start_date || ' to ' || mc.end_date as campaign_period
    FROM staging.marketing_campaigns mc
    LEFT JOIN analytics.daily_sales ds ON ds.sales_date BETWEEN mc.start_date AND mc.end_date
    GROUP BY mc.campaign_id, mc.campaign_name, mc.budget, mc.start_date, mc.end_date
    ON CONFLICT (campaign_id) DO UPDATE SET
        total_revenue = EXCLUDED.total_revenue,
        total_orders = EXCLUDED.total_orders,
        roi_estimate = EXCLUDED.roi_estimate,
        updated_at = CURRENT_TIMESTAMP;
    """)
    
    try:
        with engine.begin() as conn:
            # Check if marketing campaigns table exists and has data
            check_result = conn.execute(text("SELECT COUNT(*) FROM staging.marketing_campaigns")).fetchone()
            
            if check_result[0] > 0:
                # Create campaign_roi table if it doesn't exist
                create_table_sql = text("""
                CREATE TABLE IF NOT EXISTS analytics.campaign_roi (
                    campaign_id VARCHAR(20) PRIMARY KEY,
                    campaign_name VARCHAR(255),
                    total_revenue DECIMAL(12,2),
                    total_orders INTEGER,
                    roi_estimate DECIMAL(8,2),
                    campaign_period TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                conn.execute(create_table_sql)
                
                result = conn.execute(roi_sql)
                logging.info("Marketing campaign ROI created successfully")
            else:
                logging.info("No marketing campaign data found, skipping ROI calculation")
        
    except Exception as e:
        logging.error(f"Failed to create marketing ROI: {e}")
        # Don't raise error for optional table
        pass
    finally:
        engine.dispose()

def create_business_summary_views():
    """Create summary views for dashboard consumption"""
    logging.info("Creating business summary views...")
    
    engine = get_db_connection()
    
    # Create a view for executive dashboard
    exec_summary_sql = text("""
    CREATE OR REPLACE VIEW analytics.executive_summary AS
    SELECT 
        COUNT(DISTINCT cm.customer_id) as total_customers,
        COUNT(DISTINCT CASE WHEN cm.churn_risk_score < 0.5 THEN cm.customer_id END) as active_customers,
        SUM(cm.total_spent) as total_revenue,
        AVG(cm.avg_order_value) as avg_order_value,
        COUNT(DISTINCT pm.product_id) as total_products,
        AVG(pm.profit_margin) as avg_profit_margin,
        COUNT(DISTINCT ds.sales_date) as days_with_sales,
        MAX(ds.sales_date) as last_sales_date
    FROM analytics.customer_metrics cm
    CROSS JOIN analytics.product_metrics pm
    CROSS JOIN analytics.daily_sales ds;
    """)
    
    # Create a view for top performing products
    top_products_sql = text("""
    CREATE OR REPLACE VIEW analytics.top_products AS
    SELECT 
        p.product_id,
        p.product_name,
        p.category,
        pm.total_revenue,
        pm.total_quantity_sold,
        pm.profit_margin,
        RANK() OVER (ORDER BY pm.total_revenue DESC) as revenue_rank
    FROM warehouse.dim_products p
    JOIN analytics.product_metrics pm ON p.product_id = pm.product_id
    WHERE p.is_current = true
    ORDER BY pm.total_revenue DESC
    LIMIT 20;
    """)
    
    # Create customer segmentation view
    customer_segments_sql = text("""
    CREATE OR REPLACE VIEW analytics.customer_segmentation AS
    SELECT 
        customer_segment,
        COUNT(*) as customer_count,
        SUM(total_spent) as segment_revenue,
        AVG(total_spent) as avg_customer_value,
        AVG(churn_risk_score) as avg_churn_risk
    FROM analytics.customer_metrics
    GROUP BY customer_segment
    ORDER BY segment_revenue DESC;
    """)
    
    # Create seasonal trends view
    seasonal_trends_sql = text("""
    CREATE OR REPLACE VIEW analytics.seasonal_performance AS
    SELECT 
        quarter,
        SUM(total_revenue) as quarter_revenue,
        AVG(total_revenue) as avg_monthly_revenue,
        SUM(total_orders) as quarter_orders,
        AVG(avg_order_value) as avg_order_value
    FROM analytics.monthly_trends
    GROUP BY quarter
    ORDER BY quarter;
    """)
    
    # Create acquisition summary view  
    acquisition_summary_sql = text("""
    CREATE OR REPLACE VIEW analytics.acquisition_summary AS
    SELECT 
        acquisition_category,
        COUNT(*) as customer_count,
        AVG(days_to_first_purchase) as avg_days_to_purchase,
        AVG(first_order_value) as avg_first_order_value,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
    FROM analytics.customer_acquisition
    GROUP BY acquisition_category
    ORDER BY 
        CASE acquisition_category
            WHEN 'Same Day' THEN 1
            WHEN 'Within Week' THEN 2  
            WHEN 'Within Month' THEN 3
            WHEN 'After Month' THEN 4
            WHEN 'No Purchase' THEN 5
        END;
    """)
    
    views = [
        ("Executive Summary", exec_summary_sql),
        ("Top Products", top_products_sql),
        ("Customer Segmentation", customer_segments_sql),
        ("Seasonal Performance", seasonal_trends_sql),
        ("Acquisition Summary", acquisition_summary_sql)
    ]
    
    try:
        with engine.begin() as conn:
            for view_name, view_sql in views:
                conn.execute(view_sql)
                logging.info(f"Created view: {view_name}")
        
        logging.info("Business summary views created successfully")
        
    except Exception as e:
        logging.error(f"Failed to create summary views: {e}")
        raise
    finally:
        engine.dispose()

def create_monthly_trends():
    """Create monthly sales trends for seasonal analysis"""
    logging.info("Creating monthly sales trends...")
    
    engine = get_db_connection()
    
    try:
        # Step 1: Clear table
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE analytics.monthly_trends CASCADE;"))
        
        logging.info("Monthly trends table cleared")
        
        # Step 2: Insert data
        monthly_sql = text("""
        INSERT INTO analytics.monthly_trends 
        (year, month_number, month_name, quarter, total_orders, total_revenue, 
         total_profit, avg_order_value, unique_customers)
        SELECT 
            dt.year,
            dt.month_number,
            dt.month_name,
            dt.quarter,
            COUNT(fo.order_id) as total_orders,
            SUM(fo.total_amount) as total_revenue,
            SUM(fo.profit_amount) as total_profit,
            AVG(fo.total_amount) as avg_order_value,
            COUNT(DISTINCT fo.customer_key) as unique_customers
        FROM warehouse.dim_time dt
        JOIN warehouse.fact_orders fo ON dt.time_key = fo.order_date_key
        GROUP BY dt.year, dt.month_number, dt.month_name, dt.quarter
        ORDER BY dt.year, dt.month_number;
        """)
        
        with engine.begin() as conn:
            conn.execute(monthly_sql)
        
        logging.info("Monthly trends created successfully")
        
    except Exception as e:
        logging.error(f"Failed to create monthly trends: {e}")
        raise
    finally:
        engine.dispose()

def create_customer_acquisition_analysis():
    """Create customer acquisition analysis"""
    logging.info("Creating customer acquisition analysis...")
    
    engine = get_db_connection()
    
    try:
        # Step 1: Clear table
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE analytics.customer_acquisition CASCADE;"))
        
        logging.info("Customer acquisition table cleared")
        
        # Step 2: Insert data
        acquisition_sql = text("""
        INSERT INTO analytics.customer_acquisition
        (customer_id, registration_date, first_order_date, days_to_first_purchase, 
         first_order_value, acquisition_category)
        WITH customer_first_order AS (
            SELECT 
                c.customer_id,
                c.registration_date,
                MIN(dt.full_date) as first_order_date,
                MIN(fo.total_amount) as first_order_value
            FROM warehouse.dim_customers c
            LEFT JOIN warehouse.fact_orders fo ON c.customer_key = fo.customer_key
            LEFT JOIN warehouse.dim_time dt ON fo.order_date_key = dt.time_key
            WHERE c.is_current = true
            GROUP BY c.customer_id, c.registration_date
        )
        SELECT 
            customer_id,
            registration_date,
            first_order_date,
            CASE 
                WHEN first_order_date IS NOT NULL 
                THEN first_order_date - registration_date 
                ELSE NULL 
            END as days_to_first_purchase,
            first_order_value,
            CASE 
                WHEN first_order_date IS NULL THEN 'No Purchase'
                WHEN first_order_date - registration_date <= 1 THEN 'Same Day'
                WHEN first_order_date - registration_date <= 7 THEN 'Within Week'
                WHEN first_order_date - registration_date <= 30 THEN 'Within Month'
                ELSE 'After Month'
            END as acquisition_category
        FROM customer_first_order;
        """)
        
        with engine.begin() as conn:
            conn.execute(acquisition_sql)
        
        logging.info("Customer acquisition analysis created successfully")
        
    except Exception as e:
        logging.error(f"Failed to create customer acquisition analysis: {e}")
        raise
    finally:
        engine.dispose()

def create_campaign_attribution():
    """Create campaign attribution analysis - no redundant ROI calculation"""
    logging.info("Creating campaign attribution analysis...")
    
    engine = get_db_connection()
    
    try:
        with engine.begin() as conn:
            # Check if marketing campaigns table exists and has data
            check_result = conn.execute(text("SELECT COUNT(*) FROM staging.marketing_campaigns")).fetchone()
            
            if check_result[0] > 0:
                # Clear existing data
                conn.execute(text("TRUNCATE TABLE analytics.campaign_attribution CASCADE;"))
                
                # Insert campaign attribution data
                attribution_sql = text("""
                INSERT INTO analytics.campaign_attribution
                (campaign_id, campaign_name, campaign_start_date, campaign_end_date,
                 total_revenue_during_period, total_orders_during_period, revenue_per_day)
                SELECT 
                    mc.campaign_id,
                    mc.campaign_name,
                    mc.start_date::date as campaign_start_date,
                    mc.end_date::date as campaign_end_date,
                    COALESCE(SUM(ds.total_revenue), 0) as total_revenue_during_period,
                    COALESCE(SUM(ds.total_orders), 0) as total_orders_during_period,
                    CASE 
                        WHEN mc.end_date::date - mc.start_date::date > 0 
                        THEN COALESCE(SUM(ds.total_revenue), 0) / (mc.end_date::date - mc.start_date::date + 1)
                        ELSE COALESCE(SUM(ds.total_revenue), 0)
                    END as revenue_per_day
                FROM staging.marketing_campaigns mc
                LEFT JOIN analytics.daily_sales ds ON ds.sales_date BETWEEN mc.start_date::date AND mc.end_date::date
                GROUP BY mc.campaign_id, mc.campaign_name, mc.start_date::date, mc.end_date::date;
                """)
                
                conn.execute(attribution_sql)
                logging.info("Campaign attribution created successfully")
            else:
                logging.info("No marketing campaign data found, skipping attribution")
        
    except Exception as e:
        logging.error(f"Failed to create campaign attribution: {e}")
        # Don't raise error for optional table
        pass
    finally:
        engine.dispose()
    """Basic validation of analytics outputs"""
    logging.info("Running analytics data validation...")
    
    engine = get_db_connection()
    
    validation_checks = [
        "SELECT COUNT(*) as customer_metrics_count FROM analytics.customer_metrics;",
        "SELECT COUNT(*) as product_metrics_count FROM analytics.product_metrics;",
        "SELECT COUNT(*) as daily_sales_count FROM analytics.daily_sales;",
        "SELECT SUM(total_revenue) as total_platform_revenue FROM analytics.daily_sales;",
        "SELECT AVG(churn_risk_score) as avg_churn_risk FROM analytics.customer_metrics;"
    ]
    
    try:
        with engine.connect() as conn:  # No begin() needed for read-only
            for check in validation_checks:
                result = conn.execute(text(check)).fetchone()
                logging.info(f"Analytics validation: {check} -> {result[0]}")
        
        logging.info("Analytics data validation completed successfully")
        
    except Exception as e:
        logging.error(f"Analytics validation failed: {e}")
        raise
    finally:
        engine.dispose()

def validate_analytics_data():
    """Basic validation of analytics outputs"""
    logging.info("Running analytics data validation...")
    
    engine = get_db_connection()
    
    validation_checks = [
        "SELECT COUNT(*) as customer_metrics_count FROM analytics.customer_metrics;",
        "SELECT COUNT(*) as product_metrics_count FROM analytics.product_metrics;",
        "SELECT COUNT(*) as daily_sales_count FROM analytics.daily_sales;",
        "SELECT COUNT(*) as monthly_trends_count FROM analytics.monthly_trends;",
        "SELECT COUNT(*) as customer_acquisition_count FROM analytics.customer_acquisition;",
        "SELECT SUM(total_revenue) as total_platform_revenue FROM analytics.daily_sales;",
        "SELECT AVG(churn_risk_score) as avg_churn_risk FROM analytics.customer_metrics;",
        "SELECT AVG(days_to_first_purchase) as avg_days_to_first_purchase FROM analytics.customer_acquisition WHERE days_to_first_purchase IS NOT NULL;"
    ]
    
    try:
        with engine.connect() as conn:  # No begin() needed for read-only
            for check in validation_checks:
                result = conn.execute(text(check)).fetchone()
                logging.info(f"Analytics validation: {check} -> {result[0]}")
        
        logging.info("Analytics data validation completed successfully")
        
    except Exception as e:
        logging.error(f"Analytics validation failed: {e}")
        raise
    finally:
        engine.dispose()

# Define analytics tasks - No external sensors for simplified initial load
create_customer_metrics_task = PythonOperator(
    task_id='create_customer_metrics',
    python_callable=create_customer_metrics,
    dag=dag
)

create_product_metrics_task = PythonOperator(
    task_id='create_product_metrics',
    python_callable=create_product_metrics,
    dag=dag
)

create_daily_sales_task = PythonOperator(
    task_id='create_daily_sales_summary',
    python_callable=create_daily_sales_summary,
    dag=dag
)

create_monthly_trends_task = PythonOperator(
    task_id='create_monthly_trends',
    python_callable=create_monthly_trends,
    dag=dag
)

create_customer_acquisition_task = PythonOperator(
    task_id='create_customer_acquisition_analysis',
    python_callable=create_customer_acquisition_analysis,
    dag=dag
)

create_campaign_roi_task = PythonOperator(
    task_id='create_marketing_campaign_roi',
    python_callable=create_marketing_campaign_roi,
    dag=dag
)

create_views_task = PythonOperator(
    task_id='create_business_summary_views',
    python_callable=create_business_summary_views,
    dag=dag
)

validate_analytics_task = PythonOperator(
    task_id='validate_analytics_data',
    python_callable=validate_analytics_data,
    dag=dag
)

# Set task dependencies - Simplified for initial load
[create_customer_metrics_task, create_product_metrics_task] >> create_daily_sales_task
create_daily_sales_task >> [create_monthly_trends_task, create_customer_acquisition_task]
[create_monthly_trends_task, create_customer_acquisition_task] >> create_campaign_roi_task
create_campaign_roi_task >> create_views_task >> validate_analytics_task