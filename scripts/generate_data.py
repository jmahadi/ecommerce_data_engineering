import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
import os

# setup
fake = Faker()
np.random.seed(42)  # so we get same results each time

def create_customers(num_customers=2500):
    """Generate customer data - the foundation of everything"""
    print(f"Creating {num_customers} customers...")
    
    customers = []
    # customer segments - business wants to track these
    segments = ['Premium', 'Regular', 'Budget']
    segment_weights = [0.2, 0.6, 0.2]  # 20% premium, 60% regular, 20% budget
    
    categories = ['Electronics', 'Clothing', 'Home & Garden', 'Sports', 'Books', 'Health & Beauty']
    
    for i in range(num_customers):
        # basic info
        first_name = fake.first_name()
        last_name = fake.last_name()
        
        # make realistic email
        email_patterns = [
            f"{first_name.lower()}.{last_name.lower()}@gmail.com",
            f"{first_name.lower()}{last_name.lower()}@yahoo.com",
            f"{first_name.lower()}{random.randint(1,99)}@hotmail.com"
        ]
        email = random.choice(email_patterns)
        
        # pick segment
        segment = np.random.choice(segments, p=segment_weights)
        
        customer = {
            'customer_id': f"CUST_{i+1:06d}",
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': f"+880{random.randint(1700000000, 1999999999)}",  # BD phone format
            'date_of_birth': fake.date_of_birth(minimum_age=18, maximum_age=75),
            'gender': np.random.choice(['M', 'F'], p=[0.5, 0.5]),
            'address': fake.street_address(),
            'city': np.random.choice(['Dhaka', 'Chittagong', 'Sylhet', 'Rajshahi', 'Khulna']),
            'state': 'Bangladesh',  # keeping it simple
            'country': 'Bangladesh',
            'postal_code': f"{random.randint(1000, 9999)}",
            'registration_date': fake.date_between(start_date='-2y', end_date='today'),
            'customer_segment': segment,
            'preferred_category': random.choice(categories),
            'marketing_consent': random.choice([True, False]),
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        customers.append(customer)
        
        # progress check
        if (i+1) % 500 == 0:
            print(f"  Generated {i+1} customers...")
    
    df = pd.DataFrame(customers)
    print(f"✓ Created {len(df)} customers")
    print(f"  Segments: {df['customer_segment'].value_counts().to_dict()}")
    return df

def create_products(num_products=650):
    """Generate product catalog"""
    print(f"Creating {num_products} products...")
    
    # define our product structure
    categories = {
        'Electronics': {
            'subcategories': ['Smartphones', 'Laptops', 'Headphones', 'Cameras'],
            'brands': ['Samsung', 'Apple', 'Sony', 'HP', 'Xiaomi'],
            'price_range': (50, 1500)
        },
        'Clothing': {
            'subcategories': ['Mens Wear', 'Womens Wear', 'Kids Wear', 'Shoes'],
            'brands': ['H&M', 'Zara', 'Nike', 'Adidas', 'Local Brand'],
            'price_range': (15, 200)
        },
        'Home & Garden': {
            'subcategories': ['Furniture', 'Kitchen', 'Bedding', 'Garden'],
            'brands': ['IKEA', 'HomeStyle', 'Kitchen Pro'],
            'price_range': (25, 500)
        },
        'Sports': {
            'subcategories': ['Fitness', 'Outdoor', 'Team Sports'],
            'brands': ['Nike', 'Adidas', 'Puma', 'Under Armour'],
            'price_range': (20, 300)
        },
        'Books': {
            'subcategories': ['Fiction', 'Non-Fiction', 'Educational'],
            'brands': ['Penguin', 'Oxford', 'Local Publisher'],
            'price_range': (8, 50)
        },
        'Health & Beauty': {
            'subcategories': ['Skincare', 'Makeup', 'Hair Care'],
            'brands': ['Loreal', 'Nivea', 'Garnier'],
            'price_range': (12, 100)
        }
    }
    
    products = []
    for i in range(num_products):
        # pick category and details
        category = random.choice(list(categories.keys()))
        cat_info = categories[category]
        subcategory = random.choice(cat_info['subcategories'])
        brand = random.choice(cat_info['brands'])
        
        # pricing - cost should be less than selling price
        min_price, max_price = cat_info['price_range']
        selling_price = round(random.uniform(min_price, max_price), 2)
        cost_price = round(selling_price * random.uniform(0.4, 0.7), 2)  # 40-70% of selling price
        
        # generate name
        product_name = f"{brand} {subcategory} {fake.word().title()}"
        
        product = {
            'product_id': f"PROD_{i+1:06d}",
            'product_name': product_name,
            'description': f"{fake.sentence(nb_words=8)}",
            'category': category,
            'subcategory': subcategory,
            'brand': brand,
            'sku': f"{category[:3].upper()}{i+1:06d}",
            'cost_price': cost_price,
            'selling_price': selling_price,
            'weight_kg': round(random.uniform(0.1, 10), 2),
            'dimensions': f"{random.randint(5,50)}x{random.randint(5,50)}x{random.randint(5,50)}",
            'color': fake.color_name(),
            'size': random.choice(['XS', 'S', 'M', 'L', 'XL', 'One Size']),
            'rating': round(random.uniform(2.5, 5.0), 1),
            'launch_date': fake.date_between(start_date='-1y', end_date='today'),
            'is_active': random.choice([True, True, True, False]),  # mostly active
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        products.append(product)
        
        if (i+1) % 100 == 0:
            print(f"  Generated {i+1} products...")
    
    df = pd.DataFrame(products)
    print(f"✓ Created {len(df)} products")
    print(f"  Categories: {df['category'].value_counts().to_dict()}")
    return df

def create_orders(customers_df, products_df, num_orders=12000):
    """Generate orders and order items - this is where the money happens"""
    print(f"Creating {num_orders} orders...")
    
    orders = []
    order_items = []
    
    for i in range(num_orders):
        # pick a random customer
        customer = customers_df.sample(1).iloc[0]
        
        # order behavior based on customer segment
        if customer['customer_segment'] == 'Premium':
            max_items = 5
            discount_chance = 0.8
        elif customer['customer_segment'] == 'Regular':
            max_items = 3
            discount_chance = 0.5
        else:  # Budget
            max_items = 2
            discount_chance = 0.2
        
        # how many items in this order?
        num_items = random.randint(1, max_items)
        
        order_id = f"ORD_{i+1:08d}"
        order_date = fake.date_between(start_date='-1y', end_date='today')
        
        # pick products for this order
        selected_products = products_df.sample(num_items)
        
        subtotal = 0
        for j, (_, product) in enumerate(selected_products.iterrows()):
            quantity = random.randint(1, 3)
            unit_price = product['selling_price']
            total_price = quantity * unit_price
            subtotal += total_price
            
            # create order item
            order_item = {
                'order_item_id': f"OI_{len(order_items)+1:08d}",
                'order_id': order_id,
                'product_id': product['product_id'],
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price,
                'created_at': datetime.now()
            }
            order_items.append(order_item)
        
        # calculate order totals
        discount_amount = 0
        if random.random() < discount_chance:
            discount_amount = subtotal * random.uniform(0.05, 0.2)  # 5-20% discount
        
        shipping_cost = 0 if subtotal > 500 else random.uniform(10, 50)  # free shipping over 500
        tax_amount = (subtotal - discount_amount) * 0.15  # 15% tax
        total_amount = subtotal - discount_amount + shipping_cost + tax_amount
        
        order = {
            'order_id': order_id,
            'customer_id': customer['customer_id'],
            'order_date': order_date,
            'order_status': random.choice(['Completed', 'Shipped', 'Processing', 'Cancelled']),
            'payment_method': random.choice(['Credit Card', 'bKash', 'Nagad', 'Bank Transfer']),
            'subtotal': round(subtotal, 2),
            'discount_amount': round(discount_amount, 2),
            'shipping_cost': round(shipping_cost, 2),
            'tax_amount': round(tax_amount, 2),
            'total_amount': round(total_amount, 2),
            'shipping_address': f"{fake.street_address()}, {customer['city']}",
            'delivery_date': order_date + timedelta(days=random.randint(1, 7)),
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        orders.append(order)
        
        if (i+1) % 2000 == 0:
            print(f"  Generated {i+1} orders...")
    
    orders_df = pd.DataFrame(orders)
    order_items_df = pd.DataFrame(order_items)
    
    print(f"✓ Created {len(orders_df)} orders and {len(order_items_df)} order items")
    print(f"  Total revenue: ${orders_df['total_amount'].sum():,.2f}")
    return orders_df, order_items_df

def create_clickstream(customers_df, products_df, num_events=75000):
    """Generate website clickstream data"""
    print(f"Creating {num_events} clickstream events...")
    
    events = []
    event_types = ['page_view', 'product_view', 'add_to_cart', 'remove_from_cart', 
                   'checkout_start', 'purchase', 'search']
    
    for i in range(num_events):
        # sometimes no customer (anonymous browsing)
        customer = customers_df.sample(1).iloc[0] if random.random() < 0.7 else None
        product = products_df.sample(1).iloc[0] if random.random() < 0.5 else None
        
        event = {
            'event_id': f"EVT_{i+1:08d}",
            'session_id': fake.uuid4(),
            'customer_id': customer['customer_id'] if customer is not None else None,
            'product_id': product['product_id'] if product is not None else None,
            'event_type': random.choice(event_types),
            'page_url': f"/{random.choice(['home', 'category', 'product', 'cart', 'checkout'])}",
            'referrer_url': fake.url() if random.random() < 0.3 else None,
            'user_agent': fake.user_agent(),
            'device_type': random.choice(['desktop', 'mobile', 'tablet']),
            'browser': random.choice(['Chrome', 'Firefox', 'Safari', 'Edge']),
            'ip_address': fake.ipv4(),
            'country': 'Bangladesh',
            'city': random.choice(['Dhaka', 'Chittagong', 'Sylhet']),
            'timestamp': fake.date_time_between(start_date='-1y', end_date='now'),
            'duration_seconds': random.randint(5, 300),
            'created_at': datetime.now()
        }
        events.append(event)
        
        if (i+1) % 10000 == 0:
            print(f"  Generated {i+1} events...")
    
    df = pd.DataFrame(events)
    print(f"✓ Created {len(df)} clickstream events")
    return df

def create_campaigns(num_campaigns=25):
    """Generate marketing campaign data"""
    print(f"Creating {num_campaigns} marketing campaigns...")
    
    campaigns = []
    channels = ['Email', 'Facebook Ads', 'Google Ads', 'SMS', 'Instagram']
    
    for i in range(num_campaigns):
        start_date = fake.date_between(start_date='-1y', end_date='-30d')
        duration = random.randint(7, 60)  # 1 week to 2 months
        end_date = start_date + timedelta(days=duration)
        
        budget = random.uniform(5000, 100000)
        impressions = random.randint(50000, 2000000)
        clicks = int(impressions * random.uniform(0.01, 0.08))  # 1-8% click rate
        conversions = int(clicks * random.uniform(0.02, 0.15))  # 2-15% conversion
        
        campaign = {
            'campaign_id': f"CAMP_{i+1:06d}",
            'campaign_name': f"{fake.catch_phrase()} Campaign",
            'channel': random.choice(channels),
            'start_date': start_date,
            'end_date': end_date,
            'budget': round(budget, 2),
            'target_audience': random.choice(['All', 'Premium', 'Regular', 'Budget']),
            'objective': random.choice(['Awareness', 'Conversion', 'Retention']),
            'impressions': impressions,
            'clicks': clicks,
            'conversions': conversions,
            'cost_per_click': round(budget/clicks if clicks > 0 else 0, 2),
            'conversion_rate': round(conversions/clicks*100 if clicks > 0 else 0, 2),
            'roi': round((conversions * 75 - budget)/budget * 100, 2),  # assuming avg value 75
            'is_active': end_date >= datetime.now().date(),
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        campaigns.append(campaign)
    
    df = pd.DataFrame(campaigns)
    print(f"✓ Created {len(df)} campaigns")
    return df

def create_inventory(products_df):
    """Generate inventory data for all products"""
    print("Creating inventory data...")
    
    inventory = []
    warehouses = ['Dhaka_Main', 'Chittagong_Hub', 'Sylhet_Center']
    
    for _, product in products_df.iterrows():
        # each product in each warehouse
        for warehouse in warehouses:
            stock_level = random.randint(0, 1000)
            
            inventory_record = {
                'inventory_id': f"INV_{len(inventory)+1:06d}",
                'product_id': product['product_id'],
                'warehouse_location': warehouse,
                'current_stock': stock_level,
                'reserved_stock': random.randint(0, min(stock_level//4, 50)),
                'reorder_point': random.randint(10, 100),
                'max_stock': random.randint(500, 2000),
                'last_restocked': fake.date_between(start_date='-3m', end_date='today'),
                'supplier_id': f"SUP_{random.randint(1, 20):03d}",
                'lead_time_days': random.randint(3, 30),
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            inventory.append(inventory_record)
    
    df = pd.DataFrame(inventory)
    print(f"✓ Created {len(df)} inventory records")
    return df

def save_all_data(datasets, output_dir='data'):
    """Save all the generated data to CSV files"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"\nSaving all datasets to {output_dir}/...")
    
    for filename, df in datasets.items():
        filepath = os.path.join(output_dir, filename)
        df.to_csv(filepath, index=False)
        print(f"  Saved {len(df)} records to {filename}")
    
    print("✓ All data saved!")

def quick_validation(datasets):
    """Quick check that our data makes sense"""
    print("\nQuick validation check...")
    
    customers_df = datasets['customers.csv']
    products_df = datasets['products.csv']
    orders_df = datasets['orders.csv']
    order_items_df = datasets['order_items.csv']
    
    # check relationships
    customers_in_orders = set(orders_df['customer_id'])
    customers_available = set(customers_df['customer_id'])
    if not customers_in_orders.issubset(customers_available):
        print("❌ ERROR: Some orders reference missing customers!")
        return False
    
    products_in_items = set(order_items_df['product_id'])
    products_available = set(products_df['product_id'])
    if not products_in_items.issubset(products_available):
        print("❌ ERROR: Some order items reference missing products!")
        return False
    
    print("✓ Data relationships look good")
    return True



def main():
    """Main function - generates everything"""
    print("🚀 Starting E-commerce Data Generation")
    print("=" * 50)
    
    # generate core data first
    customers_df = create_customers(2500)
    products_df = create_products(650)
    
    # then dependent data
    orders_df, order_items_df = create_orders(customers_df, products_df, 12000)
    clickstream_df = create_clickstream(customers_df, products_df, 75000)
    campaigns_df = create_campaigns(25)
    inventory_df = create_inventory(products_df)
    
    # package everything
    datasets = {
        'customers.csv': customers_df,
        'products.csv': products_df,
        'orders.csv': orders_df,
        'order_items.csv': order_items_df,
        'clickstream.csv': clickstream_df,
        'marketing_campaigns.csv': campaigns_df,
        'inventory.csv': inventory_df
    }

    # Display samples from each dataset
    for name, df in datasets.items():
        print(f"\n{name} Sample:")
        print(df.head())

    
    # quick check
    if quick_validation(datasets):
        save_all_data(datasets)
        
        print("\n" + "=" * 50)
        print("📊 GENERATION COMPLETE!")
        print(f"Customers: {len(customers_df):,}")
        print(f"Products: {len(products_df):,}")
        print(f"Orders: {len(orders_df):,}")
        print(f"Order Items: {len(order_items_df):,}")
        print(f"Clickstream Events: {len(clickstream_df):,}")
        print(f"Marketing Campaigns: {len(campaigns_df):,}")
        print(f"Inventory Records: {len(inventory_df):,}")
        print(f"Total Revenue: ${orders_df['total_amount'].sum():,.2f}")
        print("=" * 50)
    else:
        print("❌ Validation failed - check the data!")

if __name__ == "__main__":
    main()