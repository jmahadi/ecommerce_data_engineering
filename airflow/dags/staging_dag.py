from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
import logging
import os

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
    'staging_data_ingestion',
    default_args=default_args,
    description='Load raw CSV data into staging tables',
    schedule_interval='@daily',
    catchup=False,
    tags=['staging', 'etl', 'raw-data']
)

def get_db_connection():
    """Get database connection"""
    connection_string = "postgresql://analytics_user:analytics_pass@postgres:5432/ecommerce_analytics"
    return create_engine(connection_string)

def validate_csv_file(file_path, expected_columns):
    """Basic validation for CSV files"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    df = pd.read_csv(file_path, nrows=1)
    missing_columns = set(expected_columns) - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing columns in {file_path}: {missing_columns}")
    
    return True

def load_customers_to_staging():
    """Load customers CSV to staging table"""
    logging.info("Loading customers data to staging...")
    
    file_path = '/opt/airflow/data/customers.csv'
    expected_columns = ['customer_id', 'first_name', 'last_name', 'email', 'customer_segment']
    
    try:
        validate_csv_file(file_path, expected_columns)
        df = pd.read_csv(file_path)
        
        # Basic data cleaning
        df['email'] = df['email'].str.lower().str.strip()
        df['customer_segment'] = df['customer_segment'].fillna('Unknown')
        
        engine = get_db_connection()
        
        # Load data in chunks for better memory management
        chunk_size = 1000
        total_rows = 0
        
        for chunk in pd.read_csv(file_path, chunksize=chunk_size):
            chunk.to_sql(
                'customers',
                engine,
                schema='staging',
                if_exists='append' if total_rows > 0 else 'replace',
                index=False,
                method='multi'
            )
            total_rows += len(chunk)
        
        logging.info(f"Successfully loaded {total_rows} customer records")
        engine.dispose()
        
    except Exception as e:
        logging.error(f"Failed to load customers: {e}")
        raise

def load_products_to_staging():
    """Load products CSV to staging table"""
    logging.info("Loading products data to staging...")
    
    file_path = '/opt/airflow/data/products.csv'
    expected_columns = ['product_id', 'product_name', 'category', 'cost_price', 'selling_price']
    
    try:
        validate_csv_file(file_path, expected_columns)
        
        engine = get_db_connection()
        chunk_size = 1000
        total_rows = 0
        
        for chunk in pd.read_csv(file_path, chunksize=chunk_size):
            # Basic data validation
            chunk['cost_price'] = pd.to_numeric(chunk['cost_price'], errors='coerce')
            chunk['selling_price'] = pd.to_numeric(chunk['selling_price'], errors='coerce')
            
            # Remove rows with invalid prices
            chunk = chunk.dropna(subset=['cost_price', 'selling_price'])
            
            chunk.to_sql(
                'products',
                engine,
                schema='staging',
                if_exists='append' if total_rows > 0 else 'replace',
                index=False,
                method='multi'
            )
            total_rows += len(chunk)
        
        logging.info(f"Successfully loaded {total_rows} product records")
        engine.dispose()
        
    except Exception as e:
        logging.error(f"Failed to load products: {e}")
        raise

def load_orders_to_staging():
    """Load orders CSV to staging table"""
    logging.info("Loading orders data to staging...")
    
    file_path = '/opt/airflow/data/orders.csv'
    expected_columns = ['order_id', 'customer_id', 'order_date', 'total_amount']
    
    try:
        validate_csv_file(file_path, expected_columns)
        
        engine = get_db_connection()
        chunk_size = 1000
        total_rows = 0
        
        for chunk in pd.read_csv(file_path, chunksize=chunk_size):
            # Convert date column
            chunk['order_date'] = pd.to_datetime(chunk['order_date'])
            chunk['total_amount'] = pd.to_numeric(chunk['total_amount'], errors='coerce')
            
            # Remove invalid records
            chunk = chunk.dropna(subset=['order_date', 'total_amount'])
            
            chunk.to_sql(
                'orders',
                engine,
                schema='staging',
                if_exists='append' if total_rows > 0 else 'replace',
                index=False,
                method='multi'
            )
            total_rows += len(chunk)
        
        logging.info(f"Successfully loaded {total_rows} order records")
        engine.dispose()
        
    except Exception as e:
        logging.error(f"Failed to load orders: {e}")
        raise

def load_remaining_tables():
    """Load other CSV files to staging"""
    logging.info("Loading remaining CSV files...")
    
    remaining_files = {
        'order_items.csv': 'order_items',
        'clickstream.csv': 'clickstream',
        'marketing_campaigns.csv': 'marketing_campaigns',
        'inventory.csv': 'inventory'
    }
    
    engine = get_db_connection()
    
    for csv_file, table_name in remaining_files.items():
        try:
            file_path = f'/opt/airflow/data/{csv_file}'
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                
                df.to_sql(
                    table_name,
                    engine,
                    schema='staging',
                    if_exists='replace',
                    index=False,
                    method='multi'
                )
                
                logging.info(f"Loaded {len(df)} records to staging.{table_name}")
            else:
                logging.warning(f"File not found: {file_path}")
                
        except Exception as e:
            logging.error(f"Failed to load {csv_file}: {e}")
            raise
    
    engine.dispose()

def create_staging_indexes():
    """Create basic indexes on staging tables for performance"""
    logging.info("Creating indexes on staging tables...")
    
    engine = get_db_connection()
    
    # Basic indexes for common lookup columns
    index_queries = [
        "CREATE INDEX IF NOT EXISTS idx_staging_customers_id ON staging.customers(customer_id);",
        "CREATE INDEX IF NOT EXISTS idx_staging_products_id ON staging.products(product_id);",
        "CREATE INDEX IF NOT EXISTS idx_staging_orders_id ON staging.orders(order_id);",
        "CREATE INDEX IF NOT EXISTS idx_staging_orders_customer ON staging.orders(customer_id);",
        "CREATE INDEX IF NOT EXISTS idx_staging_orders_date ON staging.orders(order_date);",
        "CREATE INDEX IF NOT EXISTS idx_staging_order_items_order ON staging.order_items(order_id);",
        "CREATE INDEX IF NOT EXISTS idx_staging_order_items_product ON staging.order_items(product_id);"
    ]
    
    try:
        with engine.begin() as conn:  # Use begin() for auto-commit
            for query in index_queries:
                conn.execute(text(query))
        
        logging.info("Successfully created staging indexes")
        
    except Exception as e:
        logging.error(f"Failed to create indexes: {e}")
        raise
    finally:
        engine.dispose()

def validate_staging_data():
    """Basic data quality checks on staging data"""
    logging.info("Running data quality checks...")
    
    engine = get_db_connection()
    
    quality_checks = [
        "SELECT COUNT(*) as customer_count FROM staging.customers;",
        "SELECT COUNT(*) as product_count FROM staging.products;",
        "SELECT COUNT(*) as order_count FROM staging.orders;",
        "SELECT COUNT(*) as null_emails FROM staging.customers WHERE email IS NULL;",
        "SELECT COUNT(*) as invalid_prices FROM staging.products WHERE cost_price <= 0 OR selling_price <= 0;"
    ]
    
    try:
        with engine.connect() as conn:  # No need for begin() here, just reading data
            for check in quality_checks:
                result = conn.execute(text(check)).fetchone()
                logging.info(f"Data quality check: {check} -> {result[0]}")
        
        logging.info("Data quality checks completed")
        
    except Exception as e:
        logging.error(f"Data quality check failed: {e}")
        raise
    finally:
        engine.dispose()

# Define tasks
load_customers_task = PythonOperator(
    task_id='load_customers_to_staging',
    python_callable=load_customers_to_staging,
    dag=dag
)

load_products_task = PythonOperator(
    task_id='load_products_to_staging',
    python_callable=load_products_to_staging,
    dag=dag
)

load_orders_task = PythonOperator(
    task_id='load_orders_to_staging',
    python_callable=load_orders_to_staging,
    dag=dag
)

load_remaining_task = PythonOperator(
    task_id='load_remaining_tables',
    python_callable=load_remaining_tables,
    dag=dag
)

create_indexes_task = PythonOperator(
    task_id='create_staging_indexes',
    python_callable=create_staging_indexes,
    dag=dag
)

validate_data_task = PythonOperator(
    task_id='validate_staging_data',
    python_callable=validate_staging_data,
    dag=dag
)

# Set task dependencies
[load_customers_task, load_products_task, load_orders_task, load_remaining_task] >> create_indexes_task >> validate_data_task