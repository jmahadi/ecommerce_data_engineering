# E-commerce Analytics Pipeline

This data engineering assignment demonstrates building an analytics platform for an e-commerce company. The project creates the whole pipeline from scratch - generating data, processing it, and making dashboards that actually answer business questions.

## What Was Built

The main idea was to simulate a real e-commerce analytics setup. Technology stack includes:
- **PostgreSQL** as the database (running in Docker)
- **Apache Airflow** for orchestrating all data pipelines 
- **Python** for all data processing logic
- **Looker Studio** for dashboards (using ngrok to expose local DB)

Initially attempted using Metabase for dashboards since it's more common in data engineering setups, but the computer kept shutting down when running too many Docker services simultaneously (Postgres + Airflow + Metabase was too much for the machine). Switched to Looker Studio with ngrok which worked much better and didn't overload the system.

## Architecture Overview

Built with a standard data warehouse approach using three schemas. Here's the overall flow:

```
CSV Files → Staging Tables → Warehouse (Star Schema) → Analytics Tables → Dashboards
     ↓              ↓                    ↓                    ↓             ↓
Python Script → PostgreSQL → Airflow DAG → PostgreSQL → Looker Studio
```

### 1. Staging Schema (`staging`)

Raw CSV data landing zone. Mirrors the CSV structure exactly:

- `customers` - customer info and segments
- `products` - product catalog with pricing
- `orders` & `order_items` - transaction data
- `clickstream` - website events 
- `marketing_campaigns` - campaign data
- `inventory` - stock levels

### 2. Warehouse Schema (`warehouse`) 

Implements a proper star schema for analytics:

- **Fact Tables**: `fact_orders`, `fact_order_items`, `fact_clickstream`, `fact_inventory`
- **Dimension Tables**: `dim_customers`, `dim_products`, `dim_time`, `dim_marketing_campaigns`

Implementation includes SCD Type 2 for dimension tables to track changes over time. Fact tables are partitioned by date which should help with performance as data grows.

**Why SCD Type 2?** For dimensions that can change (like customer segments or product prices), track history with:

- `effective_date` / `expiry_date` for time boundaries
- `is_current` flag for easy filtering  
- Surrogate keys to handle changes properly

### 3. Analytics Schema (`analytics`)

Contains all pre-aggregated business metrics:

- `customer_metrics` - CLV, churn risk, order patterns
- `product_metrics` - revenue, profit margins, inventory turnover  
- `daily_sales` - daily aggregated sales data
- `campaign_attribution` - marketing campaign effectiveness

## Sample Data Generated

Created realistic e-commerce dataset using Python Faker library:

- **2,500 customers** across Premium (28%), Regular (56.9%), Budget (15.1%) segments
- **650 products** in 6 categories with realistic pricing and profit margins
- **12,000 orders** with seasonal patterns and customer behavior
- **75,000 clickstream events** simulating website interactions
- **25 marketing campaigns** with performance metrics and ROI data

Relationships between tables are maintained properly, and the data has realistic business patterns.

## How to Run This Thing

### Prerequisites
- Docker & Docker Compose
- Python 3.8+
- ngrok account (free tier is fine)

### Setup Steps

1. **Clone and start the containers:**
```bash
git clone <your-repo>
cd ecommerce_analytics_engineering
docker-compose up -d
```

2. **Generate sample data:**
```bash
# First generate the CSV files
python scripts/generate_data.py

# Then load into staging via Airflow
# Go to http://localhost:8083 (Airflow UI)
# Run the staging_data_ingestion DAG
```

3. **Run the data pipeline:**
```bash
# In Airflow UI, run DAGs in this order:
# 1. staging_data_ingestion
# 2. warehouse_transformation  
# 3. analytics_processing
```

4. **Access dashboards:**
```bash
# Start ngrok to expose PostgreSQL
ngrok tcp 5434

# Use the ngrok URL in Looker Studio
# Connect to: <ngrok-host>:<ngrok-port>
# Database: ecommerce_analytics
# User: analytics_user / Pass: analytics_pass

> **NOTE:** ngrok URL changes every restart, so you'll need to update the connection strings in all Looker Studio data sources each time. Dashboards are exported as PDFs (saved in dashboards/ folder) as backup since the live connection isn't permanent.

# Live Dashboard Link
https://lookerstudio.google.com/reporting/f7aa5016-7919-4c08-ab7a-05be25df8919
```

## Data Pipeline Details

### ETL Process

The pipeline runs daily and uses a full refresh approach (probably not ideal for production but works for this assignment):

1. **Staging Load** - Raw CSV data gets loaded into staging tables with basic validation
2. **Warehouse Transform** - Data gets cleaned and transformed into star schema with proper joins
3. **Analytics Aggregation** - Business metrics get calculated and stored for fast dashboard queries

### Data Quality

Implementation includes basic data quality checks:

- Null value validation on required fields
- Referential integrity checks between related tables
- Row count validation between pipeline stages
- Basic business logic validation (like prices > 0, valid date ranges)

Each Airflow DAG includes validation steps that will fail the pipeline if data quality issues are detected.

## Dashboard & Analytics

Created 3 main dashboards in Looker Studio:

### Executive Summary Dashboard
- Total revenue, customers, orders KPIs
- Monthly revenue trends over time
- Customer segmentation breakdown (Premium/Regular/Budget)
- Churn risk analysis (Low/Medium/High risk categories)

### Product Performance Dashboard  
- Top products by profit margin (answers assignment question!)
- Revenue by category and brand breakdown
- Profit margin vs sales volume scatter plot analysis
- Inventory turnover metrics

### Customer Analytics Dashboard
- Customer acquisition patterns and timing analysis  
- Average time to first purchase (another assignment question!)
- Customer lifetime value analysis by segment
- Marketing campaign effectiveness measurement

## Business Questions Answered

The assignment required answering these specific questions:

1. **Which products have the highest profit margins?** 
    - **Sony Smartphones** (Electronics): 105.58% margin - highest individual product
   - Books and Health & Beauty mostly consistently show 58-60% margins
   - Electronics has lower average margins (~45%) but highest volume

2. **What are the top customer segments by lifetime value?**
   - Regular customers: $7.7M total (56.9% of base)
   - Premium customers: $3.8M total (28% of base) 
   - Budget customers: $2.1M total (15.1% of base)
   - **Average CLV** across all segments: $5,449.36

3. **How do seasonal trends affect sales performance?**
   - Pretty stable throughout the year around $1M/month
   - Slight dip in July 2025 (because of generation of data )

4. **Which marketing campaigns generate the best ROI?**
   - **"Re-contextualized cohesive focus"**  campaign generated the highest revenue during that duration at ~$2M
   - Original ROI data in staging.marketing_campaigns shows 15-85% ROI range

5. **What's the average time between customer acquisition and first purchase?**
   - 67.8 days average
   - Most customers (1.4K) purchase "After Month" 

## Technical Challenges & Solutions

### Metabase Resource Issues
Initially wanted to use Metabase for dashboards since it's a common choice in data engineering. But running PostgreSQL + Airflow + Metabase simultaneously kept causing the computer to shut down due to resource constraints. The Java-based Metabase was particularly memory-heavy.

Switched to Looker Studio which runs in the cloud, so no local resource impact. Much better for development on limited hardware.

### ngrok Connection Issues
Encountered some trouble with ngrok requiring credit card for TCP tunnels on free tier. Worked around it by getting verified account. The connection sometimes drops which breaks the dashboards temporarily.

**Main limitation**: ngrok URL changes every time you restart, so have to update all data source connections in Looker Studio each time. That's why dashboards are exported as PDFs - they're saved in the `dashboards/` folder as backup since the live connection isn't permanent.

### Airflow DAG Dependencies  
Initially tried to use ExternalTaskSensor between DAGs but it was overkill for this assignment. Simplified to just run them manually in sequence.

### Data Type Casting
PostgreSQL was pretty strict about data types when loading from staging to warehouse. Had to add explicit casting (::date, ::numeric) in several places.

### Looker Studio Schema Access
Looker Studio couldn't see custom schemas initially. Fixed by creating views in the public schema that point to analytics tables.

## Performance & Scalability Considerations

### Current Optimizations

- **Date-partitioned fact tables** for better query performance on time ranges
- **Indexes on join columns** and frequently filtered fields  
- **Pre-aggregated analytics tables** so dashboards don't aggregate on the fly
- **Looker Studio caching** (12-hour cache) reduces database load

## What Would Be Done Differently

If this was a real production system:
- Use incremental loading instead of full refresh
- Implement proper data flow tracking  
- Add more comprehensive data quality testing
- Use a proper cloud data warehouse (Snowflake/BigQuery)
- Set up automated testing for the DAGs
- Add alerting for pipeline failures

But for an assignment this demonstrates the core concepts.

## Files Structure

```
ecommerce_analytics_engineering/
├── airflow/
│   └── dags/
│       ├── staging_data_ingestion.py
│       ├── warehouse_dag.py
│       └── analytics_dag.py
├── scripts/
│   └── generate_data.py
├── database/
│   └── init.sql
├── docs/ 
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── Ecommerce_Customer_Analysis_Looker_Dashboards.pdf
├── dashboards/
│   ├── Ecommerce_Customer_Analysis_Looker_Dashboards.pdf
├── docker-compose.yml
└── .gitignore
```

## Access Details

- **Airflow**: http://localhost:8083 (admin/admin123)
- **pgAdmin**: http://localhost:8082 (admin@analytics.com/admin123)  
- **PostgreSQL**: localhost:5434 (analytics_user/analytics_pass)
- **Database**: ecommerce_analytics

The dashboards are in Looker Studio and need the ngrok connection to work. PDFs are exported as backup since the connection isn't permanent - every time you restart ngrok, you get a new URL and have to update all the data source connections.

---

This was a pretty fun project - got to work with the full data engineering stack and actually see some interesting insights in the data. The fake data generator with the defined logics created a good set of data that make the analysis meaningful. The resource constraints taught valuable lessons about balancing local development environments too.