"""
Fetch Ozon sales and stock data via API.
Includes warehouse breakdown for stocks (FBO) and sales with region info.
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

CLIENT_ID = os.getenv('OZON_CLIENT_ID')
API_KEY = os.getenv('OZON_API_KEY')

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}


def fetch_ozon_stocks():
    """Fetch current stock levels from Ozon.
    
    NOTE: v2/v3 product/info/stocks return 404.
    Using v4/product/info/stocks which works correctly.
    """
    url = "https://api-seller.ozon.ru/v4/product/info/stocks"
    payload = {
        "filter": {"visibility": "ALL"},
        "last_id": "",
        "limit": 1000
    }
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json().get('items', [])
    except requests.exceptions.Timeout:
        print("Error: Ozon API timeout (stocks)")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching Ozon stocks: HTTP {e.response.status_code}")
        try:
            print(f"Response: {e.response.text[:200]}")
        except:
            pass
        return []
    except Exception as e:
        print(f"Error fetching Ozon stocks: {e}")
        return []


def fetch_ozon_warehouses():
    """Fetch list of Ozon warehouses. Tries v1, falls back to v2."""
    for version, url in [
        ('v1', 'https://api-seller.ozon.ru/v1/warehouse/list'),
        ('v2', 'https://api-seller.ozon.ru/v2/warehouse/list'),
    ]:
        try:
            response = requests.post(url, json={}, headers=HEADERS, timeout=30)
            response.raise_for_status()
            result = response.json().get('result', [])
            print(f"  ✓ warehouses ({version}): {len(result)} items")
            return result
        except requests.exceptions.HTTPError as e:
            print(f"  Warehouses {version} failed: HTTP {e.response.status_code} - {e.response.text[:200]}")
        except Exception as e:
            print(f"  Warehouses {version} failed: {e}")
    
    print("  ⚠ All warehouse endpoints failed, continuing without warehouse mapping")
    return []


def fetch_ozon_fbo_stocks():
    """Fetch FBO stock analytics by warehouse using v2 endpoint."""
    url = "https://api-seller.ozon.ru/v2/analytics/stock_on_warehouses"
    payload = {"limit": 1000, "offset": 0}
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json().get('result', {}).get('rows', [])
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching Ozon FBO stocks: HTTP {e.response.status_code}")
        return []
    except Exception as e:
        print(f"Error fetching Ozon FBO stocks: {e}")
        return []


def fetch_ozon_fbs_stocks():
    """Fetch stock on the seller's OWN warehouses (FBS / rFBS / FBP).

    Canonical endpoint: POST /v2/product/info/stocks-by-warehouse/fbs
    (v1 was disabled on 07.04.2026).

    Returns a flat list of rows:
      [{"article", "warehouse_id", "warehouse_name", "quantity"}, ...]
    The response shape has changed between API revisions, so parsing is
    defensive: both `result`-wrapped and top-level payloads are accepted.
    """
    url = "https://api-seller.ozon.ru/v2/product/info/stocks-by-warehouse/fbs"
    rows = []
    cursor = ""

    for _page in range(200):
        payload = {"limit": 1000}
        if cursor:
            payload["cursor"] = cursor

        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching Ozon FBS stocks: HTTP {e.response.status_code}")
            try:
                print(f"  Response: {e.response.text[:200]}")
            except Exception:
                pass
            break
        except Exception as e:
            print(f"Error fetching Ozon FBS stocks: {e}")
            break

        result = data.get('result', data) if isinstance(data, dict) else {}
        products = result.get('products', []) if isinstance(result, dict) else []

        for prod in products:
            article = prod.get('offer_id') or prod.get('sku') or 'Unknown'
            # Per-warehouse breakdown may live in `stocks` or `warehouses`
            for key in ('stocks', 'warehouses'):
                for st in (prod.get(key) or []):
                    if not isinstance(st, dict):
                        continue
                    qty = st.get('present', st.get('quantity', st.get('amount')))
                    if qty is None:
                        continue
                    rows.append({
                        'article': article,
                        'warehouse_id': st.get('warehouse_id', st.get('warehouseId')),
                        'warehouse_name': st.get('warehouse_name', st.get('warehouseName')),
                        'quantity': int(qty or 0),
                    })

        cursor = result.get('cursor', '') if isinstance(result, dict) else ''
        if not (isinstance(result, dict) and result.get('has_next')) or not cursor:
            break

    print(f"  ✓ FBS (own warehouses) rows: {len(rows)}")
    return rows


def fetch_ozon_orders():
    """Fetch FBO orders for the last 30 days with region info.
    
    NOTE: Using v2 endpoint as per OZON documentation.
    v3 was returning 404 - it's for FBS only.
    Implements pagination to get all orders beyond the 1000 limit.
    """
    url = "https://api-seller.ozon.ru/v2/posting/fbo/list"
    dt_now = datetime.now()
    dt_from = dt_now - timedelta(days=28)
    
    all_orders = []
    offset = 0
    
    while True:
        payload = {
            "dir": "DESC",
            "filter": {
                "since": dt_from.strftime('%Y-%m-%dT00:00:00.000Z'),
                "to": dt_now.strftime('%Y-%m-%dT23:59:59.999Z'),
                "status": ""
            },
            "limit": 1000,
            "offset": offset,
            "with": {
                "analytics_data": True,
                "financial_data": True
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
            response.raise_for_status()
            result = response.json().get('result', [])
            if isinstance(result, dict):
                result = result.get('postings', [])
            
            if not result:
                break
            
            all_orders.extend(result)
            print(f"  ✓ orders page {offset // 1000 + 1}: {len(result)} items (total: {len(all_orders)})")
            
            if len(result) < 1000:
                break  # Last page
            
            offset += 1000
            
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching Ozon orders: HTTP {e.response.status_code} - {e.response.text[:200]}")
            break
        except Exception as e:
            print(f"Error fetching Ozon orders: {e}")
            break
    
    print(f"  ✓ orders total: {len(all_orders)} orders")
    return all_orders


def fetch_ozon_sales_analytics():
    """Fetch sales analytics for the last 7 days from Ozon.
    
    NOTE: Using v1 endpoint as per OZON documentation.
    v2 was returning 404.
    """
    url = "https://api-seller.ozon.ru/v1/analytics/data"
    dt_now = datetime.now()
    dt_from = dt_now - timedelta(days=7)
    
    payload = {
        "date_from": dt_from.strftime('%Y-%m-%d'),
        "date_to": dt_now.strftime('%Y-%m-%d'),
        "metrics": ["revenue", "ordered_units"],
        "dimension": ["sku"],
        "limit": 1000,
        "offset": 0
    }
    
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.json().get('result', {}).get('data', [])
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching Ozon sales: HTTP {e.response.status_code}")
        return []
    except Exception as e:
        print(f"Error fetching Ozon sales: {e}")
        return []


def fetch_ozon_finance_transactions():
    """Fetch finance transactions for the last 30 days from Ozon.
    
    Returns transactions of type 'OperationAgentDeliveredToCustomer' (delivered/redeemed).
    This gives accurate redemption data by actual operation date.
    """
    url = "https://api-seller.ozon.ru/v3/finance/transaction/list"
    dt_now = datetime.now()
    dt_from = dt_now - timedelta(days=28)
    
    all_transactions = []
    page = 1
    
    while True:
        payload = {
            "filter": {
                "date": {
                    "from": dt_from.strftime('%Y-%m-%dT00:00:00.000Z'),
                    "to": dt_now.strftime('%Y-%m-%dT23:59:59.999Z')
                },
                "operation_type": [],  # Empty = all types
                "posting_number": "",
                "transaction_type": "all"
            },
            "page": page,
            "page_size": 1000
        }
        
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=60)
            response.raise_for_status()
            result = response.json().get('result', {})
            operations = result.get('operations', [])
            
            if not operations:
                break
                
            all_transactions.extend(operations)
            
            # Check if more pages
            row_count = result.get('row_count', 0)
            if len(all_transactions) >= row_count:
                break
            
            page += 1
            
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching Ozon finance transactions: HTTP {e.response.status_code}")
            try:
                print(f"  Response body: {e.response.text[:500]}")
            except Exception:
                pass
            break
        except Exception as e:
            print(f"Error fetching Ozon finance transactions: {e}")
            break
    
    # Diagnostic: log all unique operation_types
    if all_transactions:
        all_types = set(t.get('operation_type', 'NONE') for t in all_transactions)
        print(f"  Finance operation_types found ({len(all_types)}): {all_types}")
    else:
        print(f"  ⚠ No finance transactions retrieved (API may have returned error)")
    
    # Filter for delivered transactions (redemptions)
    # Try multiple known operation_type values
    delivery_types = {
        'OperationAgentDeliveredToCustomer',
        'MarketplaceRedistributionOfAcquiringOperation',
    }
    redemptions = [t for t in all_transactions 
                   if t.get('operation_type') in delivery_types]
    
    # If no matches with known types, try matching by type='orders' and positive accruals
    if not redemptions and all_transactions:
        print(f"  ⚠ No redemptions matched by operation_type, trying fallback filter")
        redemptions = [t for t in all_transactions 
                       if t.get('type') == 'orders' and t.get('accruals_for_sale', 0) > 0]
        print(f"  Fallback found {len(redemptions)} redemptions by type='orders'")
    
    return redemptions, all_transactions


def aggregate_stocks_by_warehouse(stocks, warehouses):
    """Aggregate stocks by warehouse (FBO warehouses)."""
    # Build warehouse id to name map
    wh_map = {str(wh.get('warehouse_id', '')): wh.get('name', 'Unknown') for wh in warehouses}
    
    warehouse_totals = {}
    for item in stocks:
        for stock in item.get('stocks', []):
            wh_type = stock.get('type', '')
            # Only FBO stocks
            if wh_type == 'fbo':
                wh_id = str(stock.get('warehouse_id', 'Unknown'))
                wh_name = wh_map.get(wh_id, f"Warehouse {wh_id}")
                present = stock.get('present', 0)
                
                if wh_name not in warehouse_totals:
                    warehouse_totals[wh_name] = {
                        'name': wh_name,
                        'warehouse_id': wh_id,
                        'quantity': 0,
                        'items_count': 0
                    }
                warehouse_totals[wh_name]['quantity'] += present
                warehouse_totals[wh_name]['items_count'] += 1
    
    sorted_warehouses = sorted(warehouse_totals.values(), key=lambda x: x['quantity'], reverse=True)
    return sorted_warehouses


def aggregate_orders_by_warehouse_and_region(orders):
    """
    Aggregate orders by:
    - warehouse (FBO - откуда едет товар)
    - region/cluster (куда доставляется)
    """
    by_warehouse = {}
    by_region = {}
    
    for order in orders:
        analytics = order.get('analytics_data', {})
        financial = order.get('financial_data', {})
        
        wh_name = analytics.get('warehouse_name', 'Unknown')
        
        # For region, use cluster_to (delivery cluster) or city as fallback
        cluster_to = financial.get('cluster_to', '')
        city = analytics.get('city', '')
        
        # Calculate order value
        total_price = 0
        for prod in financial.get('products', []):
            total_price += prod.get('price', 0) * prod.get('quantity', 1)
        
        # By warehouse (FBO)
        if wh_name not in by_warehouse:
            by_warehouse[wh_name] = {
                'name': wh_name,
                'count': 0,
                'revenue': 0
            }
        by_warehouse[wh_name]['count'] += 1
        by_warehouse[wh_name]['revenue'] += total_price
        
        # By region/cluster - prefer cluster_to, fallback to city
        region_key = cluster_to if cluster_to else city
        if not region_key:
            region_key = 'Unknown'
        if region_key not in by_region:
            by_region[region_key] = {
                'name': region_key,
                'count': 0,
                'revenue': 0
            }
        by_region[region_key]['count'] += 1
        by_region[region_key]['revenue'] += total_price
    
    sorted_warehouses = sorted(by_warehouse.values(), key=lambda x: x['revenue'], reverse=True)
    sorted_regions = sorted(by_region.values(), key=lambda x: x['revenue'], reverse=True)
    
    return sorted_warehouses, sorted_regions


def aggregate_sales_by_product(orders):
    """Aggregate sales by product (offer_id/article) with warehouse breakdown."""
    by_product = {}
    
    for order in orders:
        analytics = order.get('analytics_data') or {}
        wh_name = analytics.get('warehouse_name', 'Unknown')
        
        for product in order.get('products', []):
            article = product.get('offer_id', 'Unknown')
            price = float(product.get('price', 0))
            qty = int(product.get('quantity', 1))
            revenue = price * qty
            
            if article not in by_product:
                by_product[article] = {
                    'article': article,
                    'count': 0,
                    'revenue': 0,
                    'by_warehouse': {}
                }
            
            by_product[article]['count'] += qty
            by_product[article]['revenue'] += revenue
            
            # Warehouse breakdown
            if wh_name not in by_product[article]['by_warehouse']:
                by_product[article]['by_warehouse'][wh_name] = {
                    'name': wh_name,
                    'count': 0,
                    'revenue': 0
                }
            by_product[article]['by_warehouse'][wh_name]['count'] += qty
            by_product[article]['by_warehouse'][wh_name]['revenue'] += revenue
    
    # Convert warehouse dict to sorted list for each product
    result = []
    for article, data in by_product.items():
        wh_list = sorted(data['by_warehouse'].values(), key=lambda x: x['revenue'], reverse=True)
        result.append({
            'article': data['article'],
            'count': data['count'],
            'revenue': data['revenue'],
            'by_warehouse': wh_list
        })
    
    return sorted(result, key=lambda x: x['revenue'], reverse=True)


def aggregate_stocks_by_product(stocks):
    """Aggregate stocks by product (offer_id/article).
    
    NOTE: For proper warehouse count, we need to use fbo_analytics data
    since v4/product/info/stocks returns warehouses grouped differently.
    This function is kept for backward compatibility but will be 
    supplemented by aggregate_stocks_by_product_from_fbo.
    """
    by_product = {}
    
    for item in stocks:
        article = item.get('offer_id', 'Unknown')
        
        # Get FBO stock count
        fbo_present = 0
        warehouses_count = 0
        for stock in item.get('stocks', []):
            if stock.get('type') == 'fbo':
                fbo_present += stock.get('present', 0)
                if stock.get('present', 0) > 0:
                    warehouses_count += 1
        
        if fbo_present > 0:
            if article not in by_product:
                by_product[article] = {
                    'article': article,
                    'quantity': 0,
                    'warehouses_count': 0
                }
            by_product[article]['quantity'] += fbo_present
            by_product[article]['warehouses_count'] += warehouses_count
    
    return sorted(by_product.values(), key=lambda x: x['quantity'], reverse=True)


def aggregate_stocks_by_product_from_fbo(fbo_analytics):
    """Aggregate stocks by product from FBO analytics.
    
    This correctly counts unique warehouses per product.
    """
    by_product = {}
    
    for row in fbo_analytics:
        article = row.get('item_code', 'Unknown')
        wh_name = row.get('warehouse_name', 'Unknown')
        qty = int(row.get('free_to_sell_amount', 0))
        
        if qty <= 0:
            continue
        
        if article not in by_product:
            by_product[article] = {
                'article': article,
                'quantity': 0,
                'warehouses': set()  # Use set to count unique warehouses
            }
        
        by_product[article]['quantity'] += qty
        by_product[article]['warehouses'].add(wh_name)
    
    # Convert set to count
    result = []
    for article, data in by_product.items():
        result.append({
            'article': data['article'],
            'quantity': data['quantity'],
            'warehouses_count': len(data['warehouses'])
        })
    
    return sorted(result, key=lambda x: x['quantity'], reverse=True)


def aggregate_stocks_warehouse_products(fbo_analytics):
    """
    Aggregate FBO stocks by warehouse AND product.
    Format identical to WB for stacked bar chart.
    """
    warehouse_data = {}
    all_articles = set()
    
    for row in fbo_analytics:
        wh_name = row.get('warehouse_name', 'Unknown')
        article = row.get('item_code', 'Unknown')
        # free_to_sell_amount is the available stock
        qty = int(row.get('free_to_sell_amount', 0))
        
        if qty <= 0:
            continue
            
        all_articles.add(article)
        
        if wh_name not in warehouse_data:
            warehouse_data[wh_name] = {
                'name': wh_name,
                'total': 0,
                'products': {}
            }
        
        if article not in warehouse_data[wh_name]['products']:
            warehouse_data[wh_name]['products'][article] = 0
            
        warehouse_data[wh_name]['products'][article] += qty
        warehouse_data[wh_name]['total'] += qty
        
    # Convert to sorted list
    result = sorted(warehouse_data.values(), key=lambda x: x['total'], reverse=True)
    return result, sorted(list(all_articles))


def _is_fbs_type(stock_type):
    """Return True if the stock row belongs to a seller own warehouse (FBS/rFBS/FBP)."""
    return (stock_type or '').lower() != 'fbo'


def _resolve_ozon_warehouse_name(stock, wh_map):
    """Resolve a readable warehouse name for an Ozon stock row."""
    wh_id = str(stock.get('warehouse_id', '') or '')
    return (stock.get('warehouse_name') or wh_map.get(wh_id)
            or (f'Склад {wh_id}' if wh_id else 'Склад продавца'))


def aggregate_fbs_warehouse_products(stocks, warehouses):
    """Aggregate seller own warehouse (FBS) stocks by warehouse AND product.

    Input is the v4/product/info/stocks `items` list; each item has a `stocks`
    array with `type` (fbo/fbs/rfbs/fbp), `present` and `warehouse_id`.
    FBO rows are skipped here because FBO comes from the analytics endpoint.
    """
    wh_map = {str(wh.get('warehouse_id', wh.get('id', ''))): wh.get('name', 'Unknown')
              for wh in warehouses}
    warehouse_data = {}
    all_articles = set()

    for item in stocks:
        article = item.get('offer_id', 'Unknown')
        for stock in item.get('stocks', []) or []:
            if not _is_fbs_type(stock.get('type')):
                continue
            qty = int(stock.get('present', 0) or 0)
            if qty <= 0:
                continue
            wh_name = _resolve_ozon_warehouse_name(stock, wh_map)
            wh_id = str(stock.get('warehouse_id', '') or '')
            all_articles.add(article)
            if wh_name not in warehouse_data:
                warehouse_data[wh_name] = {
                    'name': wh_name,
                    'warehouse_id': wh_id,
                    'total': 0,
                    'products': {},
                    'source': 'fbs',
                }
            warehouse_data[wh_name]['products'][article] = \
                warehouse_data[wh_name]['products'].get(article, 0) + qty
            warehouse_data[wh_name]['total'] += qty

    result = sorted(warehouse_data.values(), key=lambda x: x['total'], reverse=True)
    return result, sorted(all_articles)


def aggregate_fbs_rows(rows, warehouses):
    """Aggregate a flat FBS row list into (warehouse-products, all_articles)."""
    wh_map = {str(wh.get('warehouse_id', wh.get('id', ''))): wh.get('name', 'Unknown')
              for wh in warehouses}
    warehouse_data = {}
    all_articles = set()

    for row in rows:
        qty = int(row.get('quantity', 0) or 0)
        if qty <= 0:
            continue
        article = row.get('article', 'Unknown')
        wh_id = str(row.get('warehouse_id', '') or '')
        wh_name = (row.get('warehouse_name') or wh_map.get(wh_id)
                   or (f'Склад {wh_id}' if wh_id else 'Склад продавца'))
        all_articles.add(article)
        if wh_name not in warehouse_data:
            warehouse_data[wh_name] = {
                'name': wh_name,
                'warehouse_id': wh_id,
                'total': 0,
                'products': {},
                'source': 'fbs',
            }
        warehouse_data[wh_name]['products'][article] = \
            warehouse_data[wh_name]['products'].get(article, 0) + qty
        warehouse_data[wh_name]['total'] += qty

    result = sorted(warehouse_data.values(), key=lambda x: x['total'], reverse=True)
    return result, sorted(all_articles)


def aggregate_fbs_rows_by_product(rows, warehouses):
    """Aggregate a flat FBS row list by product with warehouse breakdown."""
    wh_map = {str(wh.get('warehouse_id', wh.get('id', ''))): wh.get('name', 'Unknown')
              for wh in warehouses}
    products = {}

    for row in rows:
        qty = int(row.get('quantity', 0) or 0)
        if qty <= 0:
            continue
        article = row.get('article', 'Unknown')
        wh_id = str(row.get('warehouse_id', '') or '')
        wh_name = (row.get('warehouse_name') or wh_map.get(wh_id)
                   or (f'Склад {wh_id}' if wh_id else 'Склад продавца'))
        p = products.setdefault(article, {'article': article, 'quantity': 0, 'warehouses': {}})
        p['quantity'] += qty
        p['warehouses'][wh_name] = p['warehouses'].get(wh_name, 0) + qty

    result = []
    for article, data in products.items():
        by_warehouse = sorted(
            [{'name': n, 'quantity': q} for n, q in data['warehouses'].items()],
            key=lambda x: x['quantity'], reverse=True,
        )
        result.append({
            'article': article,
            'quantity': data['quantity'],
            'warehouses_count': len(by_warehouse),
            'by_warehouse': by_warehouse,
            'source': 'fbs',
        })
    return sorted(result, key=lambda x: x['quantity'], reverse=True)


def build_stocks_by_warehouse_fbs(stocks_warehouse_products_fbs):
    """Convert the FBS chart structure into the by_warehouse list format."""
    return [{
        'name': w['name'],
        'warehouse_id': w.get('warehouse_id') or w['name'],
        'quantity': w['total'],
        'items_count': len(w['products']),
        'source': 'fbs',
    } for w in stocks_warehouse_products_fbs]


def aggregate_fbs_by_product(stocks, warehouses):
    """Aggregate seller own warehouse (FBS) stocks by product with warehouse breakdown."""
    wh_map = {str(wh.get('warehouse_id', wh.get('id', ''))): wh.get('name', 'Unknown')
              for wh in warehouses}
    products = {}
    for item in stocks:
        article = item.get('offer_id', 'Unknown')
        for stock in item.get('stocks', []) or []:
            if not _is_fbs_type(stock.get('type')):
                continue
            qty = int(stock.get('present', 0) or 0)
            if qty <= 0:
                continue
            wh_name = _resolve_ozon_warehouse_name(stock, wh_map)
            p = products.setdefault(article, {'article': article, 'quantity': 0, 'warehouses': {}})
            p['quantity'] += qty
            p['warehouses'][wh_name] = p['warehouses'].get(wh_name, 0) + qty

    result = []
    for article, data in products.items():
        by_warehouse = sorted(
            [{'name': n, 'quantity': q} for n, q in data['warehouses'].items()],
            key=lambda x: x['quantity'], reverse=True,
        )
        result.append({
            'article': article,
            'quantity': data['quantity'],
            'warehouses_count': len(by_warehouse),
            'by_warehouse': by_warehouse,
            'source': 'fbs',
        })
    return sorted(result, key=lambda x: x['quantity'], reverse=True)


if __name__ == "__main__":
    print("Fetching Ozon data...")
    
    # Fetch stock data
    stocks = fetch_ozon_stocks()
    warehouses = fetch_ozon_warehouses()
    fbo_analytics = fetch_ozon_fbo_stocks()
    
    # Fetch orders for sales analysis
    orders = fetch_ozon_orders()
    sales_analytics = fetch_ozon_sales_analytics()
    
    # Fetch finance transactions for accurate redemptions
    print("Fetching finance transactions...")
    finance_redemptions, all_transactions = fetch_ozon_finance_transactions()
    print(f"  Found {len(finance_redemptions)} redemption transactions")
    
    # Aggregate stocks by warehouse (DETAILED from analytics v2)
    stocks_warehouse_products, all_articles = aggregate_stocks_warehouse_products(fbo_analytics)
    
    # Map detailed warehouse results to stocks_by_warehouse format
    stocks_by_warehouse = []
    for wh in stocks_warehouse_products:
        stocks_by_warehouse.append({
            'name': wh['name'],
            'warehouse_id': wh['name'], # Name as ID for Ozon analytics
            'quantity': wh['total'],
            'items_count': len(wh['products']),
            'source': 'fbo',
        })
        
    total_stock = sum(wh['total'] for wh in stocks_warehouse_products)

    # --- Seller own warehouses (FBS) ---
    # Primary source: canonical per-warehouse FBS endpoint.
    # Fallback: FBS rows from v4/product/info/stocks (already fetched above).
    fbs_rows = fetch_ozon_fbs_stocks()
    if fbs_rows:
        fbs_warehouse_products, all_articles_fbs = aggregate_fbs_rows(fbs_rows, warehouses)
        stocks_by_product_fbs = aggregate_fbs_rows_by_product(fbs_rows, warehouses)
    else:
        print("  ⚠ FBS endpoint returned no rows, falling back to v4 product/info/stocks")
        fbs_warehouse_products, all_articles_fbs = aggregate_fbs_warehouse_products(stocks, warehouses)
        stocks_by_product_fbs = aggregate_fbs_by_product(stocks, warehouses)

    stocks_by_warehouse_fbs = build_stocks_by_warehouse_fbs(fbs_warehouse_products)
    total_stock_fbs = sum(w['total'] for w in fbs_warehouse_products)
    
    # Aggregate orders by warehouse and region
    sales_by_warehouse, sales_by_region = aggregate_orders_by_warehouse_and_region(orders)
    total_sales_value = sum(wh['revenue'] for wh in sales_by_warehouse)
    
    # Aggregate by product
    sales_by_product = aggregate_sales_by_product(orders)
    # Use FBO analytics for correct warehouse count per product
    stocks_by_product = aggregate_stocks_by_product_from_fbo(fbo_analytics)
    
    # Calculate revenue from analytics
    total_analytics_revenue = 0
    for item in sales_analytics:
        metrics = item.get('metrics', [])
        if metrics and len(metrics) > 0:
            try:
                total_analytics_revenue += float(metrics[0])
            except (ValueError, TypeError):
                pass
    
    result = {
        "marketplace": "Ozon",
        "fetch_time": datetime.now().isoformat(),
        "stocks_count": len(stocks),
        "orders_count": len(orders),
        "total_stock_value": total_stock,
        "total_sales_value": total_sales_value,
        "total_analytics_revenue": total_analytics_revenue,
        "stocks_by_warehouse": stocks_by_warehouse,
        "stocks_warehouse_products": stocks_warehouse_products,
        "all_articles": all_articles,
        "stocks_by_warehouse_fbs": stocks_by_warehouse_fbs,
        "stocks_warehouse_products_fbs": fbs_warehouse_products,
        "stocks_by_product_fbs": stocks_by_product_fbs,
        "all_articles_fbs": all_articles_fbs,
        "total_stock_fbo": total_stock,
        "total_stock_fbs": total_stock_fbs,
        "sales_by_warehouse": sales_by_warehouse,
        "sales_by_region": sales_by_region,
        "sales_by_product": sales_by_product,
        "stocks_by_product": stocks_by_product,
        "warehouses": warehouses,
        "raw_stocks": stocks[:50],
        "raw_orders": orders,
        "finance_redemptions": finance_redemptions  # Redemptions by operation date
    }
    
    output_path = os.path.join(EXECUTIONS_DIR, 'ozon_raw_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    print(f"Ozon data saved: {len(stocks)} products, {len(orders)} orders")
    print(f"Total FBO stock: {total_stock} units across {len(stocks_warehouse_products)} warehouses")
    print(f"Total FBS (own) stock: {total_stock_fbs} units across {len(fbs_warehouse_products)} warehouses")
    print(f"Total sales (7 days): {total_sales_value:.2f} RUB, {len(orders)} orders")
    
    if sales_by_product:
        print(f"\nTop 5 products by sales:")
        for p in sales_by_product[:5]:
            print(f"  {p['article']}: {p['count']} orders, {p['revenue']:.2f} RUB")
    
    if stocks_by_product:
        print(f"\nTop 5 products by stock:")
        for p in stocks_by_product[:5]:
            print(f"  {p['article']}: {p['quantity']} units")

