# Troubleshooting Guide

Ran into a bunch of issues while building this project. Here's how I solved them in case anyone else runs into the same problems.

## Docker & Container Issues

### PostgreSQL Won't Start
**Problem**: Container keeps restarting or won't start
```bash
# Check what's wrong
docker-compose logs postgres

# Common fixes:
# 1. Port 5434 already in use
sudo lsof -i :5434
# Kill whatever's using it or change port in docker-compose.yml

# 2. Permission issues with data volume
sudo chown -R 999:999 postgres_data/

# 3. Nuclear option - rebuild everything
docker-compose down -v
docker-compose up -d
```

### Airflow Web UI Won't Load
**Problem**: Can't access http://localhost:8083
```bash
# Check container status
docker-compose ps

# If airflow-webserver is failing:
docker-compose logs airflow-webserver

# Common issue - database init
docker-compose exec airflow-webserver airflow db init
docker-compose restart airflow-webserver
```

### Memory Issues
**Problem**: Docker containers using too much RAM, computer slowing down/shutting down
```bash
# Check resource usage
docker stats

# If PostgreSQL using too much memory, add to docker-compose.yml:
# postgres:
#   environment:
#     - POSTGRES_SHARED_BUFFERS=128MB
#     - POSTGRES_EFFECTIVE_CACHE_SIZE=512MB

# Or just restart everything periodically
docker-compose restart
```

### Metabase Overloading System
**Problem**: Computer shuts down when running Metabase + other services
```bash
# Metabase is pretty resource-heavy (Java-based)
# On limited hardware, running PostgreSQL + Airflow + Metabase simultaneously 
# can cause system overload

# Solutions:
# 1. Use cloud-based dashboarding (Looker Studio, etc.)
# 2. Run Metabase separately, not with other services
# 3. Increase Docker memory limits if possible
# 4. Use lighter alternatives like Streamlit

# I switched to Looker Studio to avoid this issue entirely
```

## Database Connection Problems

### Can't Connect to PostgreSQL
**Problem**: Connection refused on localhost:5434
```bash
# 1. Check if container is running
docker-compose ps postgres

# 2. Test connection from inside container
docker-compose exec postgres psql -U analytics_user -d ecommerce_analytics

# 3. Check port mapping
docker port ecommerce_postgres

# 4. Firewall blocking? Try from container network:
docker-compose exec airflow-webserver psql -h postgres -U analytics_user -d ecommerce_analytics
```

### Wrong Schema/Table Not Found
**Problem**: Tables don't exist or wrong schema
```sql
-- Check what schemas exist
\dn

-- Check what tables exist in each schema  
\dt staging.*
\dt warehouse.*
\dt analytics.*

-- If empty, run the DAGs in correct order:
-- 1. staging_data_ingestion
-- 2. warehouse_transformation  
-- 3. analytics_processing
```

## Airflow DAG Issues

### DAG Won't Show Up
**Problem**: DAG not appearing in Airflow UI
```bash
# 1. Check DAG file syntax
python airflow/dags/your_dag.py

# 2. Check Airflow can see the file
docker-compose exec airflow-webserver airflow dags list

# 3. Refresh DAGs page in UI or restart scheduler
docker-compose restart airflow-scheduler
```

### DAG Tasks Failing
**Problem**: Tasks showing red/failed in UI
```bash
# Check task logs in Airflow UI or:
docker-compose logs airflow-scheduler

# Common issues:
# 1. Import errors - check Python imports
# 2. Database connection - check connection string
# 3. Permission errors - check user permissions

# Debug by running task manually:
docker-compose exec airflow-webserver airflow tasks run dag_id task_id 2024-01-01
```

### ExternalTaskSensor Timeout
**Problem**: DAGs waiting forever for other DAGs
```python
# I removed these from my final DAGs but if you have them:
# Either increase timeout or remove dependency

# Before:
wait_for_warehouse = ExternalTaskSensor(
    task_id='wait_for_warehouse',
    external_dag_id='warehouse_transformation',
    timeout=300  # Increase this
)

# After (what I did):
# Just removed it and run DAGs manually in sequence
```

## ngrok & Dashboard Issues

### ngrok TCP Tunnel Requires Payment  
**Problem**: "You must add a credit card before you can use TCP endpoints"
```bash
# Solutions:
# 1. Add credit card to ngrok account (free to use, just need verification)
# 2. Use http tunnel instead (more complex setup)
# 3. Use alternative like localtunnel (didn't test this)

# After adding card:
ngrok tcp 5434
# Note the URL like: tcp://0.tcp.ngrok.io:12345
```

### Looker Studio Connection Fails
**Problem**: Can't connect Looker Studio to database
```bash
# 1. Check ngrok is running and accessible
curl -I http://127.0.0.1:4040  # ngrok web interface

# 2. Test connection manually first
psql -h 0.tcp.ngrok.io -p 12345 -U analytics_user -d ecommerce_analytics

# 3. Common Looker Studio mistakes:
# - Including "tcp://" in hostname (remove it)
# - Wrong database name (use "ecommerce_analytics" not "ecomm")
# - Wrong username (use "analytics_user" not "analytics")

# Correct Looker Studio settings:
# Host: 0.tcp.ngrok.io (NO tcp:// prefix)
# Port: 12345 (your actual port from ngrok)
# Database: ecommerce_analytics
# Username: analytics_user  
# Password: analytics_pass
```

### Dashboards Show "No Data"
**Problem**: Connected but charts are empty
```sql
-- Check if views exist in public schema (Looker Studio needs this)
\dv public.*

-- If missing, create them:
CREATE VIEW public.customer_metrics AS SELECT * FROM analytics.customer_metrics;
CREATE VIEW public.product_metrics AS SELECT * FROM analytics.product_metrics;
-- etc.

-- Grant permissions:
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_user;
```

### ngrok Connection Keeps Dropping  
**Problem**: Dashboards work then suddenly break
```bash
# ngrok free tier has session limits
# Solutions:
# 1. Restart ngrok (get new URL, update Looker Studio)
# 2. Export dashboard to PDF as backup
# 3. Use paid ngrok for stable URLs

# Quick recovery:
# 1. Stop ngrok (Ctrl+C)
# 2. Restart: ngrok tcp 5434
# 3. Update data source URL in Looker Studio
```

## Data Pipeline Issues

### CSV Loading Fails
**Problem**: staging_data_ingestion DAG fails
```python
# Common issues:
# 1. File not found - check paths match
# 2. Permission errors - check file permissions  
# 3. Data type errors - check CSV format

# Debug in Python:
import pandas as pd
df = pd.read_csv('/opt/airflow/data/customers.csv')
print(df.dtypes)
print(df.head())
```

### Warehouse Transform Fails
**Problem**: Type casting errors, foreign key violations
```sql
-- Check data types match between staging and warehouse
\d staging.customers
\d warehouse.dim_customers

-- Common fixes:
-- Add explicit casting in SQL:
SELECT column_name::date, other_column::numeric

-- Check for null values causing issues:
SELECT * FROM staging.customers WHERE customer_id IS NULL;
```

### Analytics Aggregation Takes Forever
**Problem**: Analytics DAG runs for hours
```sql
-- Check table sizes:
SELECT 
    schemaname,
    tablename, 
    n_tup_ins as rows
FROM pg_stat_user_tables 
ORDER BY n_tup_ins DESC;

-- Add indexes if missing:
CREATE INDEX IF NOT EXISTS idx_orders_customer ON warehouse.fact_orders(customer_key);
CREATE INDEX IF NOT EXISTS idx_orders_date ON warehouse.fact_orders(order_date_key);
```

## Performance Issues

### Queries Running Slow
```sql
-- Check for missing indexes:
EXPLAIN ANALYZE SELECT * FROM warehouse.fact_orders 
WHERE customer_key = 123;

-- Add indexes on frequently joined columns:
CREATE INDEX IF NOT EXISTS idx_fact_orders_customer ON warehouse.fact_orders(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_orders_date ON warehouse.fact_orders(order_date_key);
```

### Docker Using Too Much Disk
```bash
# Clean up Docker
docker system prune -a

# Check space usage
docker system df

# Remove old volumes if needed (WARNING: loses data)
docker volume prune
```

## General Debugging Tips

1. **Check logs first**: Almost every issue shows up in logs
   ```bash
   docker-compose logs [service-name]
   ```

2. **Test connections step by step**: 
   - Local DB → ngrok → external access
   - Each DAG individually

3. **Use Airflow UI**: 
   - Task logs show detailed error messages
   - Graph view shows dependencies

4. **Keep it simple**: 
   - If something complex isn't working, try simpler version first
   - Remove dependencies when debugging

5. **Export/backup early**: 
   - Take screenshots of working dashboards
   - Export data to CSV if needed

Most issues I ran into were related to:
- Docker port conflicts  
- Missing permissions/schemas
- ngrok connection stability
- Data type mismatches

The key is methodical debugging - check each component individually before looking at the whole system.