import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
import os

# Setup
fake = Faker()
np.random.seed(42)

def generate_daily_incremental_data():
    """Generate daily incremental data to simulate ongoing business"""
    
    # Get today's date for incremental data
    today = datetime.now().date()
    
    print(f"Generating incremental data for {today}")
    
    # Generate new orders (simulate 50-200 new orders per day)
    new_orders_count = random.randint(50, 200)
    
    # Load existing customers to pick from
    try:
        existing_customers = pd.read_csv('/opt/airflow/data/customers.csv')
        customer_ids = existing_customers['customer_id'].tolist()
    except:
        print("Warning: Could not load existing customers, generating new ones")
        customer_ids = [f"CUST_{i:06d}" for i in range(1, 2501)]
    
    # Load existing products
    try:
        existing_products = pd.read_csv('/opt/airflow/data/products.csv')
        product_data = existing_products[['product_id', 'selling_price']].to_dict('records')
    except:
        print("Warning: Could not load existing products")
        product_data = [{'product_id': f"PROD_{i:06d}", 'selling_price': random.uniform(10, 500)} for i in range(1, 651)]
    
    # Generate new orders
    new_orders = []
    new_order_items = []
    
    for i in range(new_orders_count):
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d')}_{i+1:04d}"
        customer_id = random.choice(customer_ids)
        
        # Random time today
        order_time = datetime.combine(today, datetime.min.time()) + timedelta(
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        
        # Order details
        num_items = random.randint(1, 4)
        subtotal = 0
        order_items_for_order = []
        
        for j in range(num_items):
            product = random.choice(product_data)
            quantity = random.randint(1, 3)
            unit_price = product['selling_price']
            total_price = quantity * unit_price
            subtotal += total_price
            
            order_item = {
                'order_item_id': f"OI_{datetime.now().strftime('%Y%m%d')}_{len(new_order_items)+1:04d}",
                'order_id': order_id,
                'product_id': product['product_id'],
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price,
                'created_at': order_time
            }
            new_order_items.append(order_item)
            order_items_for_order.append(order_item)
        
        # Calculate order totals
        discount_amount = subtotal * random.uniform(0, 0.15) if random.random() < 0.3 else 0
        shipping_cost = 0 if subtotal > 500 else random.uniform(10, 50)
        tax_amount = (subtotal - discount_amount) * 0.15
        total_amount = subtotal - discount_amount + shipping_cost + tax_amount
        
        order = {
            'order_id': order_id,
            'customer_id': customer_id,
            'order_date': order_time.date(),
            'order_status': random.choice(['Completed', 'Shipped', 'Processing']),
            'payment_method': random.choice(['Credit Card', 'bKash', 'Nagad', 'Bank Transfer']),
            'subtotal': round(subtotal, 2),
            'discount_amount': round(discount_amount, 2),
            'shipping_cost': round(shipping_cost, 2),
            'tax_amount': round(tax_amount, 2),
            'total_amount': round(total_amount, 2),
            'shipping_address': f"{fake.street_address()}, Dhaka",
            'delivery_date': today + timedelta(days=random.randint(1, 5)),
            'created_at': order_time,
            'updated_at': order_time
        }
        new_orders.append(order)
    
    # Generate new clickstream events (simulate 500-1000 events per day)
    new_events_count = random.randint(500, 1000)
    new_clickstream = []
    
    event_types = ['page_view', 'product_view', 'add_to_cart', 'remove_from_cart', 'search']
    device_types = ['desktop', 'mobile', 'tablet']
    browsers = ['Chrome', 'Firefox', 'Safari', 'Edge']
    
    for i in range(new_events_count):
        # Random time today
        event_time = datetime.combine(today, datetime.min.time()) + timedelta(
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        
        event = {
            'event_id': f"EVT_{datetime.now().strftime('%Y%m%d')}_{i+1:06d}",
            'session_id': fake.uuid4(),
            'customer_id': random.choice(customer_ids) if random.random() < 0.7 else None,
            'product_id': random.choice([p['product_id'] for p in product_data]) if random.random() < 0.5 else None,
            'event_type': random.choice(event_types),
            'page_url': f"/{random.choice(['home', 'category', 'product', 'cart', 'checkout'])}",
            'referrer_url': fake.url() if random.random() < 0.3 else None,
            'user_agent': fake.user_agent(),
            'device_type': random.choice(device_types),
            'browser': random.choice(browsers),
            'ip_address': fake.ipv4(),
            'country': 'Bangladesh',
            'city': random.choice(['Dhaka', 'Chittagong', 'Sylhet']),
            'timestamp': event_time,
            'duration_seconds': random.randint(5, 300),
            'created_at': event_time
        }
        new_clickstream.append(event)
    
    # Save incremental files with date suffix
    date_suffix = today.strftime('%Y%m%d')
    
    # Create incremental directory
    os.makedirs('/opt/airflow/data/incremental', exist_ok=True)
    
    # Save incremental data
    pd.DataFrame(new_orders).to_csv(f'/opt/airflow/data/incremental/orders_inc_{date_suffix}.csv', index=False)
    pd.DataFrame(new_order_items).to_csv(f'/opt/airflow/data/incremental/order_items_inc_{date_suffix}.csv', index=False)
    pd.DataFrame(new_clickstream).to_csv(f'/opt/airflow/data/incremental/clickstream_inc_{date_suffix}.csv', index=False)
    
    print(f"Generated incremental data:")
    print(f"  - {len(new_orders)} new orders")
    print(f"  - {len(new_order_items)} new order items") 
    print(f"  - {len(new_clickstream)} new clickstream events")
    print(f"  - Files saved to /opt/airflow/data/incremental/")

if __name__ == "__main__":
    generate_daily_incremental_data()