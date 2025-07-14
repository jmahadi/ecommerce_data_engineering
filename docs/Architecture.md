# Technical Architecture

This doc explains how I designed the whole data pipeline and why I made certain technical choices.

## Overall Data Flow

```
CSV Files → Staging Tables → Warehouse (Star Schema) → Analytics Tables → Dashboards
     ↓              ↓                    ↓                    ↓             ↓
Python Script → PostgreSQL → Airflow DAG → PostgreSQL → Looker Studio
```

## Technology Stack & Reasoning

### PostgreSQL 
Went with Postgres because:
- Good support for analytical queries with window functions
- Easy to set up locally with Docker
- Has decent partitioning capabilities 
- I'm comfortable with it

Could have used something like Snowflake but felt like overkill for an assignment. Plus wanted to show I can work with traditional RDBMS.

### Apache Airflow
Chose Airflow for orchestration because:
- Industry standard for data pipelines
- Good for showing ETL workflow management
- Easy to visualize dependencies 
- Built-in retry logic and monitoring

The DAG structure is pretty straightforward:
1. `staging_data_ingestion` - loads CSVs
2. `warehouse_transformation` - builds star schema  
3. `analytics_processing` - creates business metrics

### Docker Setup
Everything runs in containers which makes it easy to reproduce:
- PostgreSQL container for the database
- Airflow webserver + scheduler containers
- pgAdmin for DB management
- Separate Airflow metadata DB

## Database Design

### Schema Strategy
I used a three-layer approach:

**Staging** → Raw data, matches CSV structure exactly
**Warehouse** → Clean, normalized star schema for analysis  
**Analytics** → Pre-aggregated business metrics

This separation makes it easy to:
- Debug data issues (can check each layer)
- Reprocess without affecting raw data
- Optimize queries at each level

### Star Schema Design

**Fact Tables:**
- `fact_orders` - order header info, partitioned by date
- `fact_order_items` - line item details, also partitioned
- `fact_clickstream` - website events
- `fact_inventory` - stock levels

**Dimension Tables:**
- `dim_customers` - customer master with SCD Type 2
- `dim_products` - product catalog with SCD Type 2  
- `dim_time` - date dimension (generated from actual order dates)
- `dim_marketing_campaigns` - campaign master

### SCD Type 2 Implementation
For dimensions that can change (customers, products), I implemented slowly changing dimensions:
- `effective_date` / `expiry_date` for time boundaries
- `is_current` flag for easy filtering
- Surrogate keys to handle changes

This was probably overkill for the assignment but wanted to show I understand the concept.

### Partitioning Strategy
Partitioned the fact tables by date (year-month) which should help with:
- Query performance on date ranges
- Maintenance operations
- Data retention policies

## ETL Logic

### Data Generation
The Python script creates realistic e-commerce data:
- 2,500 customers across 3 segments
- 650 products in 6 categories  
- 12,000 orders with realistic patterns
- 75,000 clickstream events
- 25 marketing campaigns

Used Faker library to make it look realistic. The relationships between tables are maintained properly.

### Staging Load
Pretty straightforward - pandas reads CSVs and loads to staging tables via SQLAlchemy. Added some basic validation:
- Check for required columns
- Data type validation 
- Remove obvious bad records

### Warehouse Transformation
This is where the real ETL logic happens:

**Dimension Processing:**
- Check for changes vs existing records
- Close out old versions (set expiry_date)
- Insert new/changed records with current effective_date

**Fact Processing:**  
- Join to dimensions to get surrogate keys
- Calculate derived metrics (profit amounts, etc)
- Load with date partitioning

**Time Dimension:**
- Extract unique dates from all source tables
- Generate calendar attributes (day of week, quarter, etc)

### Analytics Aggregation
The analytics layer pre-calculates common business metrics:
- Customer lifetime value and churn risk
- Product performance and inventory turnover
- Daily/monthly sales summaries
- Campaign attribution (simplified)

This makes dashboard queries much faster since we're not aggregating on the fly.

## Dashboard Architecture

### Looker Studio Connection
Had to use ngrok to expose the local PostgreSQL since Looker Studio can't connect to localhost directly.

The connection flow:
```
Looker Studio → ngrok tunnel → localhost:5434 → PostgreSQL
```

### Public Schema Views
Looker Studio has trouble with custom schemas, so created views in the public schema:
```sql
CREATE VIEW public.customer_metrics AS SELECT * FROM analytics.customer_metrics;
```

This also provides a nice abstraction layer for the dashboards.

### Dashboard Design
Created 3 focused dashboards:
1. **Executive Summary** - high-level KPIs and trends
2. **Product Performance** - product analysis and profit margins  
3. **Customer Analytics** - customer behavior and acquisition

Each dashboard answers specific business questions from the assignment.

## Performance Considerations

### Indexing Strategy
Added indexes on commonly joined columns:
- Primary keys and foreign keys
- Date columns for time-based filtering  
- Customer/product IDs for lookups

### Query Optimization
- Used appropriate data types (numeric vs text)
- Avoided SELECT * in production queries
- Used LIMIT where appropriate
- Partitioned large fact tables

### Caching
Looker Studio caches data for 12 hours which reduces load on the database.

## Data Quality & Monitoring

### Validation Checks
Each DAG includes validation steps:
- Row count checks between stages
- Null value validation on required fields
- Referential integrity checks
- Business logic validation (e.g., prices > 0)

### Error Handling  
- Airflow retry logic for transient failures
- Separate transactions to isolate issues
- Logging at each major step

### Monitoring
- Airflow web UI shows pipeline status
- Built-in data quality checks in each DAG
- Manual validation queries for spot checking

## Security & Access

### Database Security
- Separate user account (analytics_user) with limited permissions
- No direct prod access - everything goes through Airflow
- Connection strings stored in Airflow configuration

### Dashboard Access
- Looker Studio dashboards can be shared with specific Google accounts
- ngrok tunnel is temporary and can be secured with auth tokens

## Scalability Thoughts

Current limitations:
- Single PostgreSQL instance
- Full refresh approach  
- Local development setup

For production scale:
- Would use distributed data warehouse (Snowflake/BigQuery)
- Implement incremental loading
- Add proper CI/CD pipeline
- Use managed Airflow (Cloud Composer/MWAA)

## Alternative Approaches Considered

**Cloud-native:** Could have used BigQuery + Looker, but wanted to show on-premise skills

**Real-time:** Could have added Kafka + streaming, but assignment focused on batch processing

**dbt:** Could have used dbt for transformations, but wanted to show raw SQL skills

**Different viz tools:** Considered Tableau/PowerBI but Looker Studio was free and accessible

## Lessons Learned

1. **ngrok limitations** - Free tier has restrictions, paid version needed for stable TCP tunnels
2. **Airflow complexity** - Probably overkill for this size, but good to demonstrate
3. **Schema design matters** - Spent time upfront on good schema design, paid off in dashboard creation
4. **Data quality is hard** - Even with fake data, had to handle edge cases and type issues

Overall pretty happy with how it turned out. The architecture is realistic for a mid-size company and demonstrates most of the key data engineering concepts.