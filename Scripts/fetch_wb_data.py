"""
Fetch Wildberries sales and stock data via API.
Uses the new Analytics API for warehouse stocks (replacement for deprecated /api/v1/supplier/stocks).
Handles WB API rate limits (HTTP 429) with retry + exponential backoff.
"""

import requests
import os
import time
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

# Base URLs
STATS_BASE = "https://statistics-api.wildberries.ru"
ANALYTICS_BASE = "https://seller-analytics-api.wildberries.ru"

# Rate limit settings for statistics API (orders/sales)
MAX_RETRIES = 5
RETRY_DELAY = 90       # seconds on 429
INTER_REQUEST_DELAY = 90  # Delay between stats API calls (1 req/min limit)

# Warehouses to exclude from per-region breakdown (virtual/transit entries)
VIRTUAL_WAREHOUSES = {
    'в пути до получателей',
    'в пути возвраты на склад wb',
    'всего находится на складах',
    'итого на складах',
    'в пути к покупателю',
    'в пути на склад',
    'в пути',
}


def fetch_with_retry(url, params, headers, endpoint_name, max_retries=MAX_RETRIES, method='GET', json_body=None):
    """
    Fetch data from WB API with retry on HTTP 429 (rate limit).
    Uses Retry-After header if available, otherwise exponential backoff.
    """
    for attempt in range(max_retries):
        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=60)
            else:
                response = requests.post(url, json=json_body, headers=headers, timeout=60)

            # Diagnostic logging
            print(f"  [{endpoint_name}] HTTP {response.status_code}, "
                  f"Content-Length: {len(response.content)} bytes")

            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    wait_time = int(retry_after) + 10
                else:
                    wait_time = RETRY_DELAY

                print(f"  Rate limited ({endpoint_name}), attempt {attempt + 1}/{max_retries}. "
                      f"Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            data = response.json()
            print(f"  ✓ {endpoint_name}: {len(data) if isinstance(data, list) else 'OK'} items")
            return data

        except requests.exceptions.Timeout:
            print(f"Error: WB API timeout ({endpoint_name}), attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(30)
                continue
            return []
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching WB {endpoint_name}: HTTP {e.response.status_code}")
            if e.response.status_code == 429:
                continue
            return []
        except Exception as e:
            print(f"Error fetching WB {endpoint_name}: {e}")
            return []

    print(f"All {max_retries} retries exhausted for {endpoint_name}")
    return []


def fetch_wb_stocks_warehouse_remains():
    """
    Fetch current stock levels from Wildberries using the new Analytics API.
    Replaces deprecated /api/v1/supplier/stocks.

    Flow:
      1. POST  /api/v1/warehouse_remains  → get taskId
      2. Poll  /api/v1/warehouse_remains/tasks/{taskId}/status
      3. GET   /api/v1/warehouse_remains/tasks/{taskId}/download  → data

    Returns a flat list compatible with the old format:
      [{"supplierArticle": ..., "warehouseName": ..., "quantity": ...}, ...]
    """
    headers = {"Authorization": WB_TOKEN}

    # Step 1: Create report task (group by supplier article)
    print("  Requesting warehouse_remains report task...")
    url_create = f"{ANALYTICS_BASE}/api/v1/warehouse_remains"
    params = {
        "locale": "ru",
        "groupBySa": "true",      # group by vendorCode (supplier article)
        "groupByNm": "false",
        "groupByBarcode": "false",
        "groupBySize": "false",
        "groupByBrand": "false",
        "groupBySubject": "false",
    }

    resp = requests.get(url_create, headers=headers, params=params, timeout=60)
    print(f"  [warehouse_remains create] HTTP {resp.status_code}")

    if resp.status_code == 429:
        print("  Rate limited on task creation, waiting 65s...")
        time.sleep(65)
        resp = requests.get(url_create, headers=headers, params=params, timeout=60)
        print(f"  [warehouse_remains create retry] HTTP {resp.status_code}")

    if resp.status_code != 200:
        print(f"  ERROR creating task: {resp.text[:300]}")
        return []

    task_id = resp.json().get("data", {}).get("taskId")
    if not task_id:
        print(f"  ERROR: no taskId in response: {resp.text[:200]}")
        return []

    print(f"  Task created: {task_id}")

    # Step 2: Poll for status (max 5 minutes)
    url_status = f"{ANALYTICS_BASE}/api/v1/warehouse_remains/tasks/{task_id}/status"
    max_poll_attempts = 60  # 60 × 5s = 5 min

    for attempt in range(max_poll_attempts):
        time.sleep(5)
        try:
            resp_status = requests.get(url_status, headers=headers, timeout=30)
            if resp_status.status_code == 200:
                status = resp_status.json().get("data", {}).get("status", "")
                print(f"  Poll {attempt + 1}: status = {status}")
                if status == "done":
                    break
                elif status in ("error", "canceled"):
                    print(f"  Task failed: {status}")
                    return []
            else:
                print(f"  Poll error: HTTP {resp_status.status_code}")
        except Exception as e:
            print(f"  Poll exception: {e}")
    else:
        print("  Timeout waiting for warehouse_remains report")
        return []

    # Step 3: Download report
    url_download = f"{ANALYTICS_BASE}/api/v1/warehouse_remains/tasks/{task_id}/download"
    try:
        resp_dl = requests.get(url_download, headers=headers, timeout=120)
        print(f"  [warehouse_remains download] HTTP {resp_dl.status_code}")

        if resp_dl.status_code == 204:
            print("  No data (204)")
            return []

        if resp_dl.status_code != 200:
            print(f"  Download error: {resp_dl.text[:300]}")
            return []

        raw_data = resp_dl.json()
        print(f"  ✓ Downloaded {len(raw_data)} articles from warehouse_remains")

        # Convert to flat list compatible with old format
        flat_stocks = []
        for item in raw_data:
            vendor_code = item.get("vendorCode", "Unknown")
            warehouses = item.get("warehouses", [])

            for wh in warehouses:
                wh_name = wh.get("warehouseName", "Unknown")
                qty = wh.get("quantity", 0)

                # Skip virtual/transit warehouses from the flat list
                # (they will be excluded in aggregation)
                flat_stocks.append({
                    "supplierArticle": vendor_code,
                    "warehouseName": wh_name,
                    "quantity": qty,
                })

        return flat_stocks, raw_data

    except Exception as e:
        print(f"  Download exception: {e}")
        return []


def fetch_wb_orders():
    """Fetch orders data for the last 30 days from Wildberries."""
    url = f"{STATS_BASE}/api/v1/supplier/orders"
    params = {"dateFrom": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}
    headers = {"Authorization": WB_TOKEN}
    return fetch_with_retry(url, params, headers, "orders")


def fetch_wb_sales():
    """Fetch sales (redemptions) data for the last 30 days from Wildberries."""
    url = f"{STATS_BASE}/api/v1/supplier/sales"
    params = {"dateFrom": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}
    headers = {"Authorization": WB_TOKEN}
    return fetch_with_retry(url, params, headers, "sales")


def aggregate_stocks_by_warehouse(stocks):
    """Aggregate stocks by warehouse (FBW warehouses), excluding virtual entries."""
    warehouses = {}
    for item in stocks:
        wh_name = item.get('warehouseName', 'Unknown')

        # Skip virtual warehouses
        if wh_name.lower() in VIRTUAL_WAREHOUSES:
            continue

        qty = item.get('quantity', 0)

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
    Excludes virtual/transit warehouse entries.
    Returns structure: { warehouse_name: { article: quantity } }
    """
    warehouses = {}
    all_articles = set()

    for item in stocks:
        wh_name = item.get('warehouseName', 'Unknown')
        article = item.get('supplierArticle', 'Unknown')
        qty = item.get('quantity', 0)

        # Skip virtual warehouses
        if wh_name.lower() in VIRTUAL_WAREHOUSES:
            continue

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
    """Aggregate orders by warehouse and region. Uses priceWithDisc for revenue."""
    by_warehouse = {}
    by_region = {}

    for item in orders:
        wh_name = item.get('warehouseName', 'Unknown')
        region = item.get('regionName', 'Unknown')
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
    """Aggregate orders by product (supplierArticle) with warehouse breakdown."""
    products = {}

    for item in orders:
        article = item.get('supplierArticle', 'Unknown')
        wh_name = item.get('warehouseName', 'Unknown')
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

        if wh_name not in products[article]['by_warehouse']:
            products[article]['by_warehouse'][wh_name] = {
                'name': wh_name,
                'count': 0,
                'revenue': 0
            }
        products[article]['by_warehouse'][wh_name]['count'] += 1
        products[article]['by_warehouse'][wh_name]['revenue'] += price

    sorted_products = sorted(products.values(), key=lambda x: x['revenue'], reverse=True)

    for product in sorted_products:
        wh_list = sorted(product['by_warehouse'].values(), key=lambda x: x['revenue'], reverse=True)
        product['by_warehouse'] = wh_list

    return sorted_products


if __name__ == "__main__":
    print("Fetching Wildberries data...")
    print(f"  Token: {WB_TOKEN[:8]}...{WB_TOKEN[-4:] if WB_TOKEN else 'N/A'}")
    print()

    # Fetch stocks via new Analytics API (no delay needed before this)
    print("--- Stocks (warehouse_remains) ---")
    stocks_result = fetch_wb_stocks_warehouse_remains()

    if isinstance(stocks_result, tuple):
        stocks, raw_warehouse_data = stocks_result
    else:
        stocks = stocks_result or []
        raw_warehouse_data = []

    print(f"  Flat stocks records: {len(stocks)}")

    # Wait before next stats API call
    print(f"\n  Waiting {INTER_REQUEST_DELAY}s before orders request (stats API rate limit)...")
    time.sleep(INTER_REQUEST_DELAY)

    print("--- Orders ---")
    orders = fetch_wb_orders()

    print(f"\n  Waiting {INTER_REQUEST_DELAY}s before sales request...")
    time.sleep(INTER_REQUEST_DELAY)

    print("--- Sales ---")
    sales = fetch_wb_sales()

    # Aggregate stocks by warehouse
    stocks_by_warehouse = aggregate_stocks_by_warehouse(stocks)

    # Total stock: use "Всего находится на складах" if present, otherwise sum real warehouses
    total_stock = 0
    for item in stocks:
        if item.get('warehouseName', '').lower() == 'всего находится на складах':
            total_stock += item.get('quantity', 0)
    if total_stock == 0:
        total_stock = sum(
            item.get('quantity', 0) for item in stocks
            if item.get('warehouseName', '').lower() not in VIRTUAL_WAREHOUSES
        )

    # Aggregate stocks by warehouse with product breakdown (for chart)
    stocks_warehouse_products, all_articles = aggregate_stocks_by_warehouse_and_product(stocks)

    # Aggregate orders
    orders_by_warehouse, orders_by_region = aggregate_orders_by_warehouse_and_region(orders)
    total_orders_value = sum(o.get('priceWithDisc', 0) or 0 for o in orders)

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
        "raw_warehouse_remains": raw_warehouse_data,
        "raw_orders": orders,
        "raw_sales": sales
    }

    output_path = os.path.join(EXECUTIONS_DIR, 'wb_raw_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"\nWB data saved: {result['stocks_count']} stock records, {result['orders_count']} orders")
    print(f"Total stock: {total_stock} units across {len(stocks_by_warehouse)} warehouses")
    print(f"Total orders (30 days): {total_orders_value:.2f} RUB, {len(orders)} orders")
    print(f"Unique articles in stock: {len(all_articles)}")

    if stocks_by_warehouse:
        print("\nTop 5 warehouses by stock:")
        for wh in stocks_by_warehouse[:5]:
            print(f"  {wh['name']}: {wh['quantity']} units")

    if orders_by_product:
        print("\nTop 5 products by orders:")
        for p in orders_by_product[:5]:
            print(f"  {p['article']}: {p['count']} orders, {p['revenue']:.2f} RUB")
