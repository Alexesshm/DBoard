"""
Fetch Wildberries sales and stock data via API.
Uses the new Analytics API for warehouse stocks (replacement for deprecated /api/v1/supplier/stocks).
Handles WB API rate limits (HTTP 429) with retry + exponential backoff.
"""

import requests
import os
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import json

# Dynamic path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CREDENTIALS_PATH = os.path.join(PROJECT_DIR, 'Credentials.env')
EXECUTIONS_DIR = os.path.join(PROJECT_DIR, 'Executions')

load_dotenv(CREDENTIALS_PATH)
WB_TOKEN = os.getenv('WB_API_TOKEN')

# Base URLs
STATS_BASE = "https://statistics-api.wildberries.ru"
ANALYTICS_BASE = "https://seller-analytics-api.wildberries.ru"
MARKETPLACE_BASE = "https://marketplace-api.wildberries.ru"
CONTENT_BASE = "https://content-api.wildberries.ru"

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
    """Fetch statistics orders data for the last 30 days from Wildberries."""
    url = f"{STATS_BASE}/api/v1/supplier/orders"
    params = {"dateFrom": (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}
    headers = {"Authorization": WB_TOKEN}
    return fetch_with_retry(url, params, headers, "orders")


def fetch_wb_fbs_orders(days=29, page_size=1000, now=None):
    """Fetch FBS assembly tasks by creation date, paging through the full window.

    The Marketplace API returns tasks (one task is one product unit), with the
    seller warehouse ID, seller article, task ID and createdAt. Do not filter
    by current status: the dashboard metric records placed orders, not net sales.
    """
    url = f"{MARKETPLACE_BASE}/api/v3/orders"
    headers = {"Authorization": WB_TOKEN}
    now = now or datetime.now(timezone.utc)
    first_day = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    date_from = int(first_day.timestamp())
    date_to = int(now.timestamp())
    cursor = 0
    seen_cursors = set()
    seen_ids = set()
    all_orders = []

    while cursor not in seen_cursors:
        seen_cursors.add(cursor)
        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "limit": page_size,
            "next": cursor,
        }
        page = fetch_with_retry(url, params, headers, "fbs-orders")
        if not isinstance(page, dict) or not isinstance(page.get("orders"), list):
            print("  ERROR: invalid/failed FBS orders page; refusing partial result")
            return None

        orders = page["orders"]
        added = 0
        for order in orders:
            order_id = order.get("id")
            if order_id is None:
                # Fail closed rather than silently dropping an unkeyed task.
                print("  ERROR: FBS order row has no task id; refusing partial result")
                return None
            key = str(order_id)
            if key not in seen_ids:
                seen_ids.add(key)
                all_orders.append(order)
                added += 1

        print(f"  FBS orders page: {len(orders)} rows, {added} unique (total {len(all_orders)})")
        next_cursor = page.get("next")
        if not orders or next_cursor is None:
            break
        next_cursor = int(next_cursor)
        if next_cursor == cursor or next_cursor in seen_cursors:
            print("  ERROR: repeated FBS orders pagination cursor; refusing partial result")
            return None
        cursor = next_cursor

    return all_orders


def fetch_wb_sales():
    """Fetch sales (redemptions) data with overlap for date-window calculations."""
    url = f"{STATS_BASE}/api/v1/supplier/sales"
    params = {"dateFrom": (datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d')}
    headers = {"Authorization": WB_TOKEN}
    return fetch_with_retry(url, params, headers, "sales")


def fetch_wb_seller_warehouses():
    """Get the list of the seller's OWN warehouses (FBS/DBS/DBW).

    Endpoint: GET https://marketplace-api.wildberries.ru/api/v3/warehouses
    Items look like: {"id": 12345, "name": "...", "officeId": 15, "deliveryType": 1}.
    """
    url = f"{MARKETPLACE_BASE}/api/v3/warehouses"
    headers = {"Authorization": WB_TOKEN}
    data = fetch_with_retry(url, None, headers, "seller-warehouses")
    if not isinstance(data, list):
        return []
    # The endpoint also lists DBS/DBW/pickup seller warehouses. This dashboard's
    # WB own-stock lane is FBS only (deliveryType=1); avoid mixing models.
    fbs_warehouses = [wh for wh in data if int(wh.get('deliveryType', 1) or 1) == 1]
    excluded = len(data) - len(fbs_warehouses)
    if excluded:
        print(f"  seller warehouses: excluded {excluded} non-FBS delivery types")
    return fbs_warehouses


def fetch_wb_cards():
    """Get all product cards with sizes (chrtID) so chrtID can be mapped to vendorCode.

    Endpoint: POST https://content-api.wildberries.ru/content/v2/get/cards/list
    """
    url = f"{CONTENT_BASE}/content/v2/get/cards/list?locale=ru"
    headers = {"Authorization": WB_TOKEN, "Content-Type": "application/json"}
    cards = []
    cursor = {"limit": 100}
    seen_signatures = set()

    for _page in range(500):
        signature = (cursor.get("updatedAt"), cursor.get("nmID"))
        if signature in seen_signatures:
            break
        seen_signatures.add(signature)

        payload = {
            "settings": {
                "sort": {"ascending": False},
                "filter": {"withPhoto": -1},
                "cursor": cursor,
            }
        }

        data = None
        for _attempt in range(3):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=60)
                if resp.status_code == 429:
                    print("  cards: rate limited, waiting 5s...")
                    time.sleep(5)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                print(f"  Error fetching cards: {e}")
                data = None
                break

        if data is None:
            break

        page = data.get("cards", [])
        cards.extend(page)
        cur = data.get("cursor", {}) or {}
        limit = cursor.get("limit", 100)
        if len(page) < limit:
            break
        cursor = {"limit": limit, "updatedAt": cur.get("updatedAt"), "nmID": cur.get("nmID")}

    print(f"  ✓ cards: {len(cards)} items")
    return cards


def build_chrt_article_map(cards):
    """Build chrtID -> {"article": vendorCode, "nmId": nmID} lookup from cards."""
    mapping = {}
    for card in cards:
        article = card.get("vendorCode", "Unknown")
        nm_id = card.get("nmID")
        for size in card.get("sizes", []) or []:
            chrt = size.get("chrtID")
            if chrt is not None:
                mapping[int(chrt)] = {"article": article, "nmId": nm_id}
    return mapping


def fetch_wb_chrt_map_from_analytics(orders):
    """Fallback chrtID map when the Content API is not available (403).

    The Content API (cards) requires the "Контент" token category. If it is
    missing, the WB warehouses stock report still returns `chrtId` + `nmId`,
    and supplier orders give us `nmId -> vendorCode`.
    """
    # nmId -> vendorCode from already-fetched orders
    nm_to_article = {}
    for order in (orders or []):
        nm = order.get("nmId")
        article = order.get("supplierArticle")
        if nm is not None and article:
            try:
                nm_to_article[int(nm)] = article
            except (TypeError, ValueError):
                continue

    url = f"{ANALYTICS_BASE}/api/analytics/v1/stocks-report/wb-warehouses"
    headers = {"Authorization": WB_TOKEN, "Content-Type": "application/json"}
    payload = {"limit": 250000}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        if resp.status_code != 200:
            print(f"  wb-warehouses report: HTTP {resp.status_code} - {resp.text[:200]}")
            return {}
        data = resp.json()
    except Exception as e:
        print(f"  wb-warehouses report error: {e}")
        return {}

    items = (data.get("data", {}) or {}).get("items") if isinstance(data, dict) else None
    if not items and isinstance(data, dict):
        items = data.get("items", [])
    items = items or []

    mapping = {}
    for item in items:
        chrt = item.get("chrtId")
        nm = item.get("nmId")
        if chrt is None or nm is None:
            continue
        article = nm_to_article.get(int(nm))
        if article:
            mapping[int(chrt)] = {"article": article, "nmId": nm}

    print(f"  ✓ chrtIds from wb-warehouses report: {len(mapping)}")
    return mapping


def fetch_wb_fbs_stocks(orders=None):
    """Fetch stocks from ALL seller own warehouses (FBS).

    Per WB docs the only way to get a per-warehouse detail for own warehouses is
    POST https://marketplace-api.wildberries.ru/api/v3/stocks/{warehouseId}
    with an explicit list of chrtIds (size IDs). We collect chrtIds from the
    product cards and query every own warehouse.

    Returns:
      flat_stocks: list of {"supplierArticle", "warehouseName", "quantity", "source"}
      warehouses:  the seller warehouse list
      cards:       the product cards (for diagnostics)
    """
    warehouses = fetch_wb_seller_warehouses()
    if not warehouses:
        print("  ⚠ No seller warehouses found — FBS stocks will be empty")
        return [], [], []

    cards = fetch_wb_cards()
    chrt_map = build_chrt_article_map(cards)
    if not chrt_map:
        print("  ⚠ Content API unavailable (cards), falling back to analytics report for chrtIds")
        chrt_map = fetch_wb_chrt_map_from_analytics(orders)
    all_chrt_ids = list(chrt_map.keys())
    print(f"  Seller warehouses: {len(warehouses)}, chrtIds: {len(all_chrt_ids)}")

    flat = []
    headers = {"Authorization": WB_TOKEN, "Content-Type": "application/json"}
    for wh in warehouses:
        wh_id = wh.get("id")
        wh_name = wh.get("name") or f"Склад {wh_id}"
        if wh_id is None:
            continue

        # API accepts up to 1000 chrtIds per request
        for i in range(0, len(all_chrt_ids), 1000):
            chunk = all_chrt_ids[i:i + 1000]
            if not chunk:
                continue
            try:
                resp = requests.post(
                    f"{MARKETPLACE_BASE}/api/v3/stocks/{wh_id}",
                    json={"chrtIds": chunk},
                    headers=headers,
                    timeout=60,
                )
                if resp.status_code == 429:
                    print(f"  [{wh_name}] rate limited, waiting 5s...")
                    time.sleep(5)
                    resp = requests.post(
                        f"{MARKETPLACE_BASE}/api/v3/stocks/{wh_id}",
                        json={"chrtIds": chunk},
                        headers=headers,
                        timeout=60,
                    )
                resp.raise_for_status()
                stocks = resp.json().get("stocks", []) or []
            except Exception as e:
                print(f"  FBS stocks error for {wh_name}: {e}")
                continue

            for s in stocks:
                chrt = s.get("chrtId")
                amount = int(s.get("amount", 0) or 0)
                info = chrt_map.get(int(chrt)) if chrt is not None else None
                article = info["article"] if info else (f"chrt{chrt}" if chrt is not None else "Unknown")
                flat.append({
                    "supplierArticle": article,
                    "warehouseName": wh_name,
                    "quantity": amount,
                    "source": "fbs",
                })

    print(f"  ✓ FBS stock rows: {len(flat)}")
    return flat, warehouses, cards


def aggregate_stocks_by_warehouse(stocks, source='fbw'):
    """Aggregate stocks by warehouse, excluding virtual entries."""
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
                'items_count': 0,
                'source': source,
            }
        warehouses[wh_name]['quantity'] += qty
        warehouses[wh_name]['items_count'] += 1

    sorted_warehouses = sorted(warehouses.values(), key=lambda x: x['quantity'], reverse=True)
    return sorted_warehouses


def aggregate_stocks_by_product(stocks, source='fbw'):
    """Aggregate stocks by product (supplierArticle) with per-warehouse breakdown."""
    products = {}
    for item in stocks:
        article = item.get('supplierArticle', 'Unknown')
        wh_name = item.get('warehouseName', 'Unknown')
        qty = item.get('quantity', 0)

        # Skip virtual warehouses and zero rows
        if wh_name.lower() in VIRTUAL_WAREHOUSES or qty <= 0:
            continue

        if article not in products:
            products[article] = {'article': article, 'quantity': 0, 'warehouses': {}}
        products[article]['quantity'] += qty
        products[article]['warehouses'][wh_name] = products[article]['warehouses'].get(wh_name, 0) + qty

    result = []
    for article, data in products.items():
        by_warehouse = sorted(
            [{'name': name, 'quantity': qty} for name, qty in data['warehouses'].items()],
            key=lambda x: x['quantity'],
            reverse=True,
        )
        result.append({
            'article': article,
            'quantity': data['quantity'],
            'warehouses_count': len(by_warehouse),
            'by_warehouse': by_warehouse,
            'source': source,
        })

    return sorted(result, key=lambda x: x['quantity'], reverse=True)


def aggregate_stocks_by_warehouse_and_product(stocks, source='fbw', limit=15):
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
                'products': {},
                'source': source,
            }

        if article not in warehouses[wh_name]['products']:
            warehouses[wh_name]['products'][article] = 0

        warehouses[wh_name]['products'][article] += qty
        warehouses[wh_name]['total'] += qty

    # Sort by total descending and take top N warehouses
    sorted_warehouses = sorted(warehouses.values(), key=lambda x: x['total'], reverse=True)[:limit]

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

    # FBS order placements come from Marketplace API, not from realized sales.
    print("--- FBS assembly orders (last 30 days) ---")
    fbs_orders = fetch_wb_fbs_orders(days=29)
    if fbs_orders is None:
        raise RuntimeError("Failed to retrieve complete WB FBS order history")

    # Keep only required task data in the ignored raw execution file; drop buyer PII.
    fbs_orders = [
        {key: order.get(key) for key in ('id', 'createdAt', 'article', 'warehouseId', 'nmId')}
        for order in fbs_orders
    ]

    # Wait before next stats API call
    print(f"\n  Waiting {INTER_REQUEST_DELAY}s before orders request (stats API rate limit)...")
    time.sleep(INTER_REQUEST_DELAY)

    print("--- Orders ---")
    orders = fetch_wb_orders()

    print(f"\n  Waiting {INTER_REQUEST_DELAY}s before sales request...")
    time.sleep(INTER_REQUEST_DELAY)

    print("--- Sales ---")
    sales = fetch_wb_sales()

    # --- Own warehouses (FBS) ---
    print("\n--- Seller warehouses (FBS) ---")
    fbs_stocks, seller_warehouses, seller_cards = fetch_wb_fbs_stocks(orders)
    warehouse_names = {str(wh.get('id')): wh.get('name') or f"Склад {wh.get('id')}"
                       for wh in seller_warehouses if wh.get('id') is not None}

    # Aggregate stocks by warehouse (marketplace / FBW)
    stocks_by_warehouse = aggregate_stocks_by_warehouse(stocks, source='fbw')

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
    stocks_warehouse_products, all_articles = aggregate_stocks_by_warehouse_and_product(stocks, source='fbw')

    # Aggregate own warehouses (FBS) stocks
    stocks_by_warehouse_fbs = aggregate_stocks_by_warehouse(fbs_stocks, source='fbs')
    stocks_warehouse_products_fbs, all_articles_fbs = aggregate_stocks_by_warehouse_and_product(fbs_stocks, source='fbs')
    stocks_by_product_fbs = aggregate_stocks_by_product(fbs_stocks, source='fbs')
    total_stock_fbs = sum(int(item.get('quantity', 0)) for item in fbs_stocks)

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
        "stocks_by_warehouse_fbs": stocks_by_warehouse_fbs,
        "stocks_warehouse_products_fbs": stocks_warehouse_products_fbs,
        "stocks_by_product_fbs": stocks_by_product_fbs,
        "all_articles_fbs": all_articles_fbs,
        "total_stock_fbs": total_stock_fbs,
        "seller_warehouses": seller_warehouses,
        "raw_fbs_orders": fbs_orders,
        "orders_by_warehouse": orders_by_warehouse,
        "orders_by_region": orders_by_region,
        "orders_by_product": orders_by_product,
        "raw_stocks": stocks,
        "raw_stocks_fbs": fbs_stocks,
        "raw_warehouse_remains": raw_warehouse_data,
        "raw_orders": orders,
        "raw_sales": sales
    }

    os.makedirs(EXECUTIONS_DIR, exist_ok=True)
    output_path = os.path.join(EXECUTIONS_DIR, 'wb_raw_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"\nWB data saved: {result['stocks_count']} stock records, {result['orders_count']} orders")
    print(f"Total stock: {total_stock} units across {len(stocks_by_warehouse)} warehouses")
    print(f"Total orders (30 days): {total_orders_value:.2f} RUB, {len(orders)} orders")
    print(f"Unique articles in stock: {len(all_articles)}")
    print(f"Own warehouses (FBS): {len(stocks_by_warehouse_fbs)} warehouses, {total_stock_fbs} units")

    if stocks_by_warehouse:
        print("\nTop 5 warehouses by stock:")
        for wh in stocks_by_warehouse[:5]:
            print(f"  {wh['name']}: {wh['quantity']} units")

    if orders_by_product:
        print("\nTop 5 products by orders:")
        for p in orders_by_product[:5]:
            print(f"  {p['article']}: {p['count']} orders, {p['revenue']:.2f} RUB")
