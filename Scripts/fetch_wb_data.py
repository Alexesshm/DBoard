"""
Fetch Wildberries sales and stock data via API.
Includes warehouse breakdown with product details (supplierArticle).
"""

import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json

# Dynamic path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CREDENTIALS_PATH = os.path.join(PROJECT_DIR, 'Credentials.env')
EXECUTIONS_DIR = os.path.join(PROJECT_DIR, 'Executions')

# Ensure Executions directory exists
os.makedirs(EXECUTIONS_DIR, exist_ok=True)

load_dotenv(CREDENTIALS_PATH)
WB_TOKEN = os.getenv('WB_API_TOKEN')


def fetch_wb_stocks():
    """Fetch current stock levels from Wildberries with warehouse breakdown."""
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/stocks"
    params = {"dateFrom": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}
    headers = {"Authorization": WB_TOKEN}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Error: WB API timeout (stocks)")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching WB stocks: HTTP {e.response.status_code}")
        return []
    except Exception as e:
        print(f"Error fetching WB stocks: {e}")
        return []


def fetch_wb_orders():
    """Fetch orders data for the last 30 days from Wildberries."""
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    params = {"dateFrom": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}
    headers = {"Authorization": WB_TOKEN}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Error: WB API timeout (orders)")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching WB orders: HTTP {e.response.status_code}")
        return []
    except Exception as e:
        print(f"Error fetching WB orders: {e}")
        return []


def fetch_wb_sales():
    """Fetch sales (redemptions) data for the last 30 days from Wildberries."""
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/sales"
    params = {"dateFrom": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}
    headers = {"Authorization": WB_TOKEN}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Error: WB API timeout (sales)")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching WB sales: HTTP {e.response.status_code}")
        return []
    except Exception as e:
        print(f"Error fetching WB sales: {e}")
        return []


def aggregate_stocks_by_warehouse(stocks):
    """Aggregate stocks by warehouse (FBW warehouses)."""
    warehouses = {}
    for item in stocks:
        wh_name = item.get('warehouseName', 'Unknown')
        qty = item.get('quantityFull', 0)
        
        if wh_name not in warehouses:
            warehouses[wh_name] = {
                'name': wh_name,
                'quantity': 0,
                'items_count': 0
            }
        warehouses[wh_name]['quantity'] += qty
        warehouses[wh_name]['items_count'] += 1
    
    sorted_warehouses = sorted(warehouses.values(), key=lambda x: x['quantity'], reverse=True)
    return sorted_warehouses


def aggregate_stocks_by_warehouse_and_product(stocks):
    """
    Aggregate stocks by warehouse with product breakdown.
    Returns structure: { warehouse_name: { article: quantity } }
    """
    warehouses = {}
    all_articles = set()
    
    for item in stocks:
        wh_name = item.get('warehouseName', 'Unknown')
        article = item.get('supplierArticle', 'Unknown')
        qty = item.get('quantityFull', 0)
        
        if qty == 0:
            continue  # Skip zero stocks
        
        all_articles.add(article)
        
        if wh_name not in warehouses:
            warehouses[wh_name] = {
                'name': wh_name,
                'total': 0,
                'products': {}
            }
        
        if article not in warehouses[wh_name]['products']:
            warehouses[wh_name]['products'][article] = 0
        
        warehouses[wh_name]['products'][article] += qty
        warehouses[wh_name]['total'] += qty
    
    # Sort by total descending and take top 15 warehouses
    sorted_warehouses = sorted(warehouses.values(), key=lambda x: x['total'], reverse=True)[:15]
    
    return sorted_warehouses, sorted(all_articles)


def aggregate_orders_by_warehouse_and_region(orders):
    """Aggregate orders by warehouse and region. Uses totalPrice for revenue."""
    by_warehouse = {}
    by_region = {}
    
    for item in orders:
        wh_name = item.get('warehouseName', 'Unknown')
        region = item.get('regionName', 'Unknown')
        # Use priceWithDisc (price after seller discount) - matches WB dashboard
        price = item.get('priceWithDisc', 0) or 0
        
        if wh_name not in by_warehouse:
            by_warehouse[wh_name] = {'name': wh_name, 'count': 0, 'revenue': 0}
        by_warehouse[wh_name]['count'] += 1
        by_warehouse[wh_name]['revenue'] += price
        
        if region not in by_region:
            by_region[region] = {'name': region, 'count': 0, 'revenue': 0}
        by_region[region]['count'] += 1
        by_region[region]['revenue'] += price
    
    sorted_warehouses = sorted(by_warehouse.values(), key=lambda x: x['revenue'], reverse=True)
    sorted_regions = sorted(by_region.values(), key=lambda x: x['revenue'], reverse=True)
    
    return sorted_warehouses, sorted_regions


def aggregate_orders_by_product(orders):
    """Aggregate orders by product (supplierArticle) with warehouse breakdown. Uses totalPrice."""
    products = {}
    
    for item in orders:
        article = item.get('supplierArticle', 'Unknown')
        wh_name = item.get('warehouseName', 'Unknown')
        # Use priceWithDisc (price after seller discount) - matches WB dashboard
        price = item.get('priceWithDisc', 0) or 0
        
        if article not in products:
            products[article] = {
                'article': article,
                'count': 0,
                'revenue': 0,
                'by_warehouse': {}
            }
        products[article]['count'] += 1
        products[article]['revenue'] += price
        
        # Breakdown by warehouse
        if wh_name not in products[article]['by_warehouse']:
            products[article]['by_warehouse'][wh_name] = {
                'name': wh_name,
                'count': 0,
                'revenue': 0
            }
        products[article]['by_warehouse'][wh_name]['count'] += 1
        products[article]['by_warehouse'][wh_name]['revenue'] += price
    
    # Sort by revenue descending
    sorted_products = sorted(products.values(), key=lambda x: x['revenue'], reverse=True)
    
    # Convert warehouse dicts to sorted lists
    for product in sorted_products:
        wh_list = sorted(product['by_warehouse'].values(), key=lambda x: x['revenue'], reverse=True)
        product['by_warehouse'] = wh_list
    
    return sorted_products


if __name__ == "__main__":
    print("Fetching Wildberries data...")
    
    stocks = fetch_wb_stocks()
    orders = fetch_wb_orders()  # Orders (what WB dashboard shows)
    sales = fetch_wb_sales()    # Sales/redemptions (for reference)
    
    # Aggregate stocks by warehouse
    stocks_by_warehouse = aggregate_stocks_by_warehouse(stocks)
    total_stock = sum(s.get('quantityFull', 0) for s in stocks)
    
    # Aggregate stocks by warehouse with product breakdown (for chart)
    stocks_warehouse_products, all_articles = aggregate_stocks_by_warehouse_and_product(stocks)
    
    # Aggregate orders by warehouse and region (using totalPrice)
    orders_by_warehouse, orders_by_region = aggregate_orders_by_warehouse_and_region(orders)
    total_orders_value = sum(o.get('priceWithDisc', 0) or 0 for o in orders)
    
    # Aggregate orders by product
    orders_by_product = aggregate_orders_by_product(orders)
    
    result = {
        "marketplace": "Wildberries",
        "fetch_time": datetime.now().isoformat(),
        "stocks_count": len(stocks),
        "orders_count": len(orders),
        "sales_count": len(sales),
        "total_stock_value": total_stock,
        "total_orders_value": total_orders_value,
        "stocks_by_warehouse": stocks_by_warehouse,
        "stocks_warehouse_products": stocks_warehouse_products,
        "all_articles": all_articles,
        "orders_by_warehouse": orders_by_warehouse,
        "orders_by_region": orders_by_region,
        "orders_by_product": orders_by_product,
        "raw_stocks": stocks,
        "raw_orders": orders,
        "raw_sales": sales
    }
    
    output_path = os.path.join(EXECUTIONS_DIR, 'wb_raw_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    print(f"WB data saved: {result['stocks_count']} stocks, {result['orders_count']} orders")
    print(f"Total stock: {total_stock} units across {len(stocks_by_warehouse)} warehouses")
    print(f"Total orders (7 days): {total_orders_value:.2f} RUB, {len(orders)} orders")
    print(f"Unique articles: {len(all_articles)}")
    
    if orders_by_product:
        print("\nTop 5 products by orders:")
        for p in orders_by_product[:5]:
            print(f"  {p['article']}: {p['count']} orders, {p['revenue']:.2f} RUB")
