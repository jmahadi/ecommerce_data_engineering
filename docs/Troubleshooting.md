# Troubleshooting Guide

Ran into a bunch of issues while building this project using a Windows operating system. Here's how I solved them in case anyone else runs into the same problems.

## Docker & Container Issues

### PostgreSQL Won't Start
**Problem**: Container keeps restarting or won't start
```bash
# Check what's wrong
docker-compose logs postgres

# Common fixes:
# 1. Port 5434 already in use
netstat -ano | findstr :5434
# 2.Kill whatever's using it or change port in docker-compose.yml
Stop-Process -Id 1234 -Force

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

# restart everything periodically
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

```

## Data Pipeline Issues

### Warehouse Transform Fails
**Problem**: Type casting errors, foreign key violations
```sql
-- Check data types match between staging and warehouse
\d staging.customers
\d warehouse.dim_customers

-- Add explicit casting in SQL:
SELECT column_name::date, other_column::numeric

```


Most issues I ran into were related to:
- Docker port conflicts  
- Missing permissions/schemas
- ngrok connection stability
- Data type mismatches
