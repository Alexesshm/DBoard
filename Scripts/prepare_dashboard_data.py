"""
Prepare dashboard data from raw API responses.
Combines WB and Ozon data into a single JSON for the frontend.
Includes warehouse breakdown with products for stacked bar chart.
Calculates sales statistics for multiple periods: Today, Yesterday, 3 Days, 7 Days.
"""

import json
import os
from datetime import datetime, timedelta, date

# Dynamic path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXECUTIONS_DIR = os.path.join(PROJECT_DIR, 'Executions')


def load_json(filename):
    """Load JSON file from Executions directory."""
    path = os.path.join(EXECUTIONS_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e}")
            return None
    else:
        print(f"File not found: {filename}")
    return None


def get_article_color(article):
    """
    Get color for article based on user-defined palette.
    """
    article_upper = article.upper()
    
    # User-defined colors
    color_map = {
        'SF0125': '#614701',
        'SF0250': '#80651b',
        'SF0500': '#b38c24',
        'SF2500': '#b38c24',
        'SM0250': '#78011b',
        'SM0500': '#78011b',
        'FSF300': '#015054',
    }
    
    if article_upper in color_map:
        return color_map[article_upper]
    
    # Default fallback by prefix
    if article_upper.startswith('FSF'):
        return '#015054'  # Teal
    if article_upper.startswith('SF'):
        return '#80651b'  # Brown
    if article_upper.startswith('SM'):
        return '#78011b'  # Burgundy
    
    # Generic fallback
    fallback_colors = ['#6366f1', '#14b8a6', '#f97316', '#ef4444', '#22c55e']
    return fallback_colors[hash(article) % len(fallback_colors)]


# WB Warehouse Clusters (based on official WB documentation)
WB_CLUSTERS = {
    'Центральный': [
        'пушкино', 'вёшки', 'вешки', 'иваново', 'подольск', 'радумля', 'обухово', 'чашниково',
        'воронеж', 'истра', 'коледино', 'домодедово', 'никольское', 'тверь', 'голицыно',
        'софьино', 'ярославль', 'цифровой', 'рязань', 'тюшевское', 'сабурово', 'владимир',
        'тула', 'котовск', 'электросталь', 'белая дача', 'щербинка', 'чехов'
    ],
    'Северо-Западный': [
        'вологда', 'шушары', 'красный бор', 'санкт-петербург', 'спб', 'уткина'
    ],
    'Приволжский': [
        'ижевск', 'кузнецк', 'пенза', 'самара', 'новосемейкино', 'сарапул', 'казань'
    ],
    'Уральский': [
        'нижний тагил', 'челябинск', 'екатеринбург'
    ],
    'Южный + Северо-Кавказский': [
        'крыловская', 'краснодар', 'волгоград', 'невинномысск', 'тихорецкая'
    ],
    'Дальневосточный + Сибирский': [
        'хабаровск', 'барнаул', 'владивосток', 'юрга', 'новосибирск'
    ],
    'Казахстан': [
        'байсерке', 'атакент', 'актобе', 'астана'
    ],
    'Беларусь': [
        'минск', 'брест', 'гродно'
    ],
    'Узбекистан': [
        'ташкент'
    ],
    'Армения': [
        'ереван'
    ],
    'Грузия': [
        'тбилиси'
    ]
}

# Ozon Warehouse Clusters (based on official Ozon documentation)
OZON_CLUSTERS = {
    'Москва, МО и Дальние регионы': [
        'хоругвино', 'ногинск', 'пушкино', 'софьино', 'радумля', 'павло', 'слободское',
        'петровское', 'жуковский', 'домодедово', 'гривно'
    ],
    'Санкт-Петербург и СЗО': [
        'колпино', 'шушары', 'волхонка', 'санкт-петербург', 'спб', 'бугры'
    ],
    'Казань': [
        'казань', 'кзн', 'столбище', 'нижний новгород'
    ],
    'Самара': [
        'самара'
    ],
    'Уфа': [
        'уфа'
    ],
    'Оренбург': [
        'оренбург'
    ],
    'Краснодар': [
        'адыгейск', 'южный обход', 'новороссийск'
    ],
    'Ростов': [
        'ростов'
    ],
    'Воронеж': [
        'воронеж'
    ],
    'Саратов': [
        'волгоград', 'саратов'
    ],
    'Невинномысск': [
        'невинномысск'
    ],
    'Махачкала': [
        'махачкала'
    ],
    'Красноярск': [
        'красноярск'
    ],
    'Новосибирск': [
        'новосибирск'
    ],
    'Омск': [
        'омск'
    ],
    'Екатеринбург': [
        'екатеринбург'
    ],
    'Пермь': [
        'пермь'
    ],
    'Тюмень': [
        'тюмень'
    ],
    'Дальний Восток': [
        'хабаровск'
    ],
    'Тверь': [
        'тверь'
    ],
    'Ярославль': [
        'ярославль'
    ],
    'Калининград': [
        'калининград'
    ],
    'Беларусь': [
        'минск'
    ],
    'Астана': [
        'астана'
    ],
    'Алматы': [
        'алматы'
    ],
    'Армения': [
        'ереван'
    ]
}


def get_warehouse_cluster(warehouse_name, mp_type='wb'):
    """
    Determine the cluster/region for a warehouse.
    
    Args:
        warehouse_name: Name of the warehouse
        mp_type: Marketplace type ('wb' or 'ozon')
    
    Returns:
        Cluster name or 'Прочие' if not found
    """
    name = warehouse_name.lower()
    clusters = WB_CLUSTERS if mp_type == 'wb' else OZON_CLUSTERS
    
    for cluster_name, keywords in clusters.items():
        for keyword in keywords:
            if keyword in name:
                return cluster_name
    
    return 'Прочие'


def parse_date(date_str):
    """Parse date string to datetime object."""
    if not date_str:
        return None
    try:
        # Handle ISO format with potential timezone Z
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            # Fallback for simple date format
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None


def calculate_total_stocks_by_product(raw_stocks):
    """Calculate total stocks by product (article) across all warehouses."""
    products = {}
    product_warehouses = {}  # Track warehouses per product: article -> {warehouse: qty}
    
    for item in raw_stocks:
        article = item.get('supplierArticle', 'Unknown')
        qty = item.get('quantityFull', 0)
        warehouse = item.get('warehouseName', 'Unknown')
        
        if article not in products:
            products[article] = {
                'article': article,
                'quantity': 0,
                'warehouses_count': 0,
                'color': get_article_color(article)
            }
            product_warehouses[article] = {}
        
        products[article]['quantity'] += qty
        if qty > 0:
            if warehouse not in product_warehouses[article]:
                product_warehouses[article][warehouse] = 0
            product_warehouses[article][warehouse] += qty
    
    # Update warehouse counts and add warehouse details
    for article in products:
        wh_data = product_warehouses.get(article, {})
        products[article]['warehouses_count'] = len(wh_data)
        # Add sorted warehouse details (by quantity descending)
        products[article]['by_warehouse'] = sorted(
            [{'name': name, 'quantity': qty} for name, qty in wh_data.items()],
            key=lambda x: x['quantity'],
            reverse=True
        )
    
    # Sort by quantity descending
    sorted_products = sorted(products.values(), key=lambda x: x['quantity'], reverse=True)
    return sorted_products


def aggregate_sales_data(sales_list, mp_type='wb'):
    """
    Aggregate sales data for a specific period.
    Returns summary metrics, warehouse breakdown, region breakdown, and product breakdown.
    """
    total_revenue = 0
    orders_count = 0
    by_warehouse = {}
    by_region = {}
    by_product = {}
    
    for item in sales_list:
        orders_count += 1
        
        # Extract fields based on marketplace type
        if mp_type == 'wb':
            # Use priceWithDisc (price after seller discount) - matches WB dashboard
            price = item.get('priceWithDisc', 0) or 0
            wh_name = item.get('warehouseName', 'Unknown')
            region = item.get('regionName', 'Unknown')
            article = item.get('supplierArticle', 'Unknown')
        else: # Ozon
            financial = item.get('financial_data', {})
            analytics = item.get('analytics_data', {})
            
            # Calculate price from products in order
            price = 0
            for prod in financial.get('products', []):
                price += prod.get('price', 0) * prod.get('quantity', 1)
                
            wh_name = analytics.get('warehouse_name', 'Unknown')
            
            # For region, use cluster_to (delivery cluster) or city as fallback
            cluster_to = financial.get('cluster_to', '')
            city = analytics.get('city', '')
            region = cluster_to if cluster_to else city
            if not region:
                region = 'Unknown'
            
            # Ozon can have multiple products per order, we pick the first one's article 
            # for primary grouping or iterate? Simplification: iterate products for product stats.
            # But here we are iterating orders. Let's handle product aggregation separately below.
            pass

        total_revenue += price
        
        # Warehouse aggregation (with product breakdown)
        if wh_name not in by_warehouse:
            by_warehouse[wh_name] = {'name': wh_name, 'count': 0, 'revenue': 0, 'by_product': {}}
        by_warehouse[wh_name]['count'] += 1
        by_warehouse[wh_name]['revenue'] += price
        
        # Add product to warehouse breakdown (for WB)
        if mp_type == 'wb':
            if article not in by_warehouse[wh_name]['by_product']:
                by_warehouse[wh_name]['by_product'][article] = {'article': article, 'count': 0, 'revenue': 0}
            by_warehouse[wh_name]['by_product'][article]['count'] += 1
            by_warehouse[wh_name]['by_product'][article]['revenue'] += price
        
        # Region aggregation
        if region not in by_region:
            by_region[region] = {'name': region, 'count': 0, 'revenue': 0}
        by_region[region]['count'] += 1
        by_region[region]['revenue'] += price

        # Product aggregation
        if mp_type == 'wb':
            if article not in by_product:
                by_product[article] = {'article': article, 'count': 0, 'revenue': 0, 'by_warehouse': {}}
            
            by_product[article]['count'] += 1
            by_product[article]['revenue'] += price
            
            if wh_name not in by_product[article]['by_warehouse']:
                 by_product[article]['by_warehouse'][wh_name] = {'name': wh_name, 'count': 0, 'revenue': 0}
            by_product[article]['by_warehouse'][wh_name]['count'] += 1
            by_product[article]['by_warehouse'][wh_name]['revenue'] += price
            
        else: # Ozon - iterate products in order
            for prod in item.get('products', []): # Top level products? No, in 'products' list of order (v2/posting/fbo/list)
                # Wait, raw_orders has 'products' at top level? No, check fetch_ozon_orders.
                # fetch_ozon_orders returns list of postings. Posting has 'products'.
                p_article = prod.get('offer_id', 'Unknown')
                p_price = float(prod.get('price', 0))
                p_qty = int(prod.get('quantity', 1))
                p_revenue = p_price * p_qty
                
                if p_article not in by_product:
                    by_product[p_article] = {'article': p_article, 'count': 0, 'revenue': 0, 'by_warehouse': {}}
                
                by_product[p_article]['count'] += p_qty
                by_product[p_article]['revenue'] += p_revenue
                
                if wh_name not in by_product[p_article]['by_warehouse']:
                     by_product[p_article]['by_warehouse'][wh_name] = {'name': wh_name, 'count': 0, 'revenue': 0}
                by_product[p_article]['by_warehouse'][wh_name]['count'] += p_qty
                by_product[p_article]['by_warehouse'][wh_name]['revenue'] += p_revenue

    # Convert dicts to sorted lists
    sorted_warehouses = sorted(by_warehouse.values(), key=lambda x: x['revenue'], reverse=True)[:15]
    # Flatten product breakdown inside each warehouse
    for wh in sorted_warehouses:
        wh['by_product'] = sorted(wh.get('by_product', {}).values(), key=lambda x: x['count'], reverse=True)
    
    sorted_regions = sorted(by_region.values(), key=lambda x: x['revenue'], reverse=True)[:15]
    
    sorted_products = sorted(by_product.values(), key=lambda x: x['revenue'], reverse=True)
    # Flatten product warehouse breakdown
    for p in sorted_products:
        p['by_warehouse'] = sorted(p['by_warehouse'].values(), key=lambda x: x['revenue'], reverse=True)

    return {
        "revenue": total_revenue,
        "orders_count": orders_count,
        "sales_by_warehouse": sorted_warehouses,
        "sales_by_region": sorted_regions,
        "sales_by_product": sorted_products
    }


def prepare():
    """Prepare combined dashboard data."""
    print("Preparing dashboard data with multi-period support...")
    
    wb_data = load_json('wb_raw_data.json')
    ozon_data = load_json('ozon_raw_data.json')
    
    dashboard = {
        "last_update": datetime.now().strftime('%d.%m.%Y %H:%M'),
        "summary": { # Current stocks (aggregated)
            "wb_stocks": 0,
            "ozon_stocks": 0,
            "total_stocks": 0,
            "total_sales_today": 0 # Placeholder for quick access
        },
        "marketplaces": [], # Current status info
        "stocks": { # Stocks are point-in-time, no periods
            "wb": {},
            "ozon": {}
        },
        "period_data": { # Sales data by period
            "today": {},
            "yesterday": {},
            "days_3": {},
            "days_7": {},
            "days_30": {}
        }
    }
    
    periods_config = [
        {"key": "today", "days": 0, "label": "Сегодня"},
        {"key": "yesterday", "days": 1, "exact_day": True, "label": "Вчера"},
        {"key": "days_3", "days": 2, "label": "3 дня"},
        {"key": "days_7", "days": 6, "label": "7 дней"},
        {"key": "days_30", "days": 29, "label": "30 дней"}
    ]
    
    today = date.today()
    
    # --- Process Wildberries Data ---
    if wb_data:
        # Stocks (No changes, take from raw)
        dashboard["summary"]["wb_stocks"] = wb_data.get('total_stock_value', 0)
        
        # Save structured stocks data
        dashboard["stocks"]["wb"] = {
            "by_warehouse": wb_data.get('stocks_by_warehouse', [])[:15],
            "by_product": calculate_total_stocks_by_product(wb_data.get('raw_stocks', [])),
            "chart_data": wb_data.get('stocks_warehouse_products', []), # Raw for chart reconstruction or use pre-built
            "all_articles": wb_data.get('all_articles', [])
        }
        # Re-construct chart data later or reuse existing logic if possible. 
        # Actually fetch_wb_data pre-calculates chart data 'stocks_warehouse_products'.
        # Let's rebuild chart data structure here to ensure consistency? 
        # Or just use what fetch_wb_data gave us. fetch_wb_data gave 'stocks_warehouse_products'.
        # let's assume UI can handle it or we construct it here. 
        # Existing logic constructed 'stocks_chart_data' in prepare. Let's keep that.
        
        # Chart Data Construction for WB with Cluster Grouping
        stocks_wp = wb_data.get('stocks_warehouse_products', [])
        all_articles = wb_data.get('all_articles', [])
        wb_chart_data = None
        if stocks_wp and all_articles:
            # Group warehouses by cluster
            from collections import defaultdict
            clustered_warehouses = defaultdict(list)
            
            for wh in stocks_wp:
                cluster = get_warehouse_cluster(wh['name'], 'wb')
                clustered_warehouses[cluster].append(wh)
            
            # Sort clusters (critical regions first, then alphabetically)
            priority_clusters = ['Центральный', 'Северо-Западный', 'Приволжский', 'Уральский']
            sorted_clusters = []
            for pc in priority_clusters:
                if pc in clustered_warehouses:
                    sorted_clusters.append(pc)
            for cluster in sorted(clustered_warehouses.keys()):
                if cluster not in priority_clusters:
                    sorted_clusters.append(cluster)
            
            # Build chart data with cluster information
            wb_chart_data = {
                "labels": [],
                "datasets": [],
                "clusters": []  # Cluster metadata
            }
            
            for cluster_name in sorted_clusters:
                warehouses = clustered_warehouses[cluster_name]
                
                # Calculate cluster totals
                total_stock = sum(sum(wh['products'].values()) for wh in warehouses)
                
                cluster_info = {
                    "name": cluster_name,
                    "start_index": len(wb_chart_data["labels"]),
                    "warehouse_count": len(warehouses),
                    "total_stock": total_stock
                }
                
                # Add warehouse labels for this cluster
                for wh in warehouses:
                    wb_chart_data["labels"].append(wh['name'])
                
                cluster_info["end_index"] = len(wb_chart_data["labels"]) - 1
                wb_chart_data["clusters"].append(cluster_info)
            
            # Build datasets (unchanged logic, but using new warehouse order)
            for article in all_articles:
                color = get_article_color(article)
                dataset = {
                    "label": article,
                    "data": [],
                    "backgroundColor": color,
                    "borderColor": '#1a1a1a', 
                    "borderWidth": 1
                }
                
                # Add data in cluster order
                for cluster_name in sorted_clusters:
                    for wh in clustered_warehouses[cluster_name]:
                        qty = wh['products'].get(article, 0)
                        dataset["data"].append(qty)
                
                if any(d > 0 for d in dataset["data"]):
                    wb_chart_data["datasets"].append(dataset)
        
        dashboard["stocks"]["wb"]["chart_data"] = wb_chart_data

        # Sales (Orders) Processing Per Period
        raw_orders = wb_data.get('raw_orders', [])
        
        for p in periods_config:
            p_key = p['key']
            filtered_sales = []
            
            for item in raw_orders:
                d_str = item.get('date') or item.get('dateFull')
                dt = parse_date(d_str)
                if not dt: continue
                d = dt.date()
                
                if p.get('exact_day'):
                    target_day = today - timedelta(days=p['days'])
                    if d == target_day:
                        filtered_sales.append(item)
                else:
                    start_day = today - timedelta(days=p['days'])
                    if d >= start_day:
                         filtered_sales.append(item)
            
            # Aggregate
            agg = aggregate_sales_data(filtered_sales, 'wb')
            if p_key not in dashboard["period_data"]: dashboard["period_data"][p_key] = {}
            dashboard["period_data"][p_key]["wb"] = agg
        
        # Redemptions (Sales/Buyouts) Processing Per Period
        raw_sales = wb_data.get('raw_sales', [])
        
        for p in periods_config:
            p_key = p['key']
            filtered_redemptions = []
            
            for item in raw_sales:
                d_str = item.get('date') or item.get('dateFull')
                dt = parse_date(d_str)
                if not dt: continue
                d = dt.date()
                
                if p.get('exact_day'):
                    target_day = today - timedelta(days=p['days'])
                    if d == target_day:
                        filtered_redemptions.append(item)
                else:
                    start_day = today - timedelta(days=p['days'])
                    if d >= start_day:
                         filtered_redemptions.append(item)
            
            # Calculate redemptions total (forPay field for sales)
            redemptions_revenue = sum(item.get('forPay', 0) or 0 for item in filtered_redemptions)
            redemptions_count = len(filtered_redemptions)
            
            # Add to existing period data
            if p_key in dashboard["period_data"] and "wb" in dashboard["period_data"][p_key]:
                dashboard["period_data"][p_key]["wb"]["redemptions_revenue"] = redemptions_revenue
                dashboard["period_data"][p_key]["wb"]["redemptions_count"] = redemptions_count
            
    # --- Process Ozon Data ---
    if ozon_data:
        # Stocks
        dashboard["summary"]["ozon_stocks"] = ozon_data.get('total_stock_value', 0)
        
        # Save structured stocks data
        # Note: ozon_raw_data has 'stocks_warehouse_products' and 'stocks_by_product' pre-calculated
        # We can reuse them but ensure consistency.
        
        ozon_stocks_by_product = ozon_data.get('stocks_by_product', [])
        for item in ozon_stocks_by_product:
            item['color'] = get_article_color(item.get('article', ''))
            
        dashboard["stocks"]["ozon"] = {
            "by_warehouse": ozon_data.get('stocks_by_warehouse', [])[:15],
            "by_product": ozon_stocks_by_product,
            "chart_data": None, # Constructed below
            "all_articles": ozon_data.get('all_articles', [])
        }
        
        # Chart Data Construction for Ozon with Cluster Grouping
        stocks_wp = ozon_data.get('stocks_warehouse_products', [])
        all_articles = ozon_data.get('all_articles', [])
        ozon_chart_data = None
        if stocks_wp and all_articles:
            # Group warehouses by cluster
            from collections import defaultdict
            clustered_warehouses = defaultdict(list)
            
            for wh in stocks_wp:
                cluster = get_warehouse_cluster(wh['name'], 'ozon')
                clustered_warehouses[cluster].append(wh)
            
            # Sort clusters (priority for Moscow and SPb regions)
            priority_clusters = ['Москва, МО и Дальние регионы', 'Санкт-Петербург и СЗО', 'Казань', 'Краснодар']
            sorted_clusters = []
            for pc in priority_clusters:
                if pc in clustered_warehouses:
                    sorted_clusters.append(pc)
            for cluster in sorted(clustered_warehouses.keys()):
                if cluster not in priority_clusters:
                    sorted_clusters.append(cluster)
            
            # Build chart data with cluster information
            ozon_chart_data = {
                "labels": [],
                "datasets": [],
                "clusters": []
            }
            
            for cluster_name in sorted_clusters:
                warehouses = clustered_warehouses[cluster_name]
                
                total_stock = sum(sum(wh['products'].values()) for wh in warehouses)
                
                cluster_info = {
                    "name": cluster_name,
                    "start_index": len(ozon_chart_data["labels"]),
                    "warehouse_count": len(warehouses),
                    "total_stock": total_stock
                }
                
                for wh in warehouses:
                    ozon_chart_data["labels"].append(wh['name'])
                
                cluster_info["end_index"] = len(ozon_chart_data["labels"]) - 1
                ozon_chart_data["clusters"].append(cluster_info)
            
            # Build datasets
            for article in all_articles:
                color = get_article_color(article)
                dataset = {
                    "label": article,
                    "data": [],
                    "backgroundColor": color,
                    "borderColor": '#1a1a1a', 
                    "borderWidth": 1
                }
                
                for cluster_name in sorted_clusters:
                    for wh in clustered_warehouses[cluster_name]:
                        qty = wh['products'].get(article, 0)
                        dataset["data"].append(qty)
                
                if any(d > 0 for d in dataset["data"]):
                    ozon_chart_data["datasets"].append(dataset)
        
        dashboard["stocks"]["ozon"]["chart_data"] = ozon_chart_data

        # Sales Processing Per Period
        raw_orders = ozon_data.get('raw_orders', [])
        
        for p in periods_config:
            p_key = p['key']
            filtered_sales = []
            
            for item in raw_orders:
                # Ozon date field: created_at
                d_str = item.get('created_at')
                dt = parse_date(d_str)
                if not dt: continue
                d = dt.date()
                
                if p.get('exact_day'):
                    target_day = today - timedelta(days=p['days'])
                    if d == target_day:
                        filtered_sales.append(item)
                else:
                    start_day = today - timedelta(days=p['days'])
                    if d >= start_day:
                         filtered_sales.append(item)
            
            # Aggregate
            agg = aggregate_sales_data(filtered_sales, 'ozon')
            if p_key not in dashboard["period_data"]: dashboard["period_data"][p_key] = {}
            dashboard["period_data"][p_key]["ozon"] = agg
            
            # Ozon Redemptions: use finance transactions for accurate redemption data
            # Filter by operation_date (actual transaction date)
            finance_redemptions = ozon_data.get('finance_redemptions', [])
            redemptions_filtered = []
            
            for txn in finance_redemptions:
                d_str = txn.get('operation_date')
                dt = parse_date(d_str)
                if not dt:
                    continue
                d = dt.date()
                
                # Filter by transaction date (when redemption was recorded)
                if p.get('exact_day'):
                    target_day = today - timedelta(days=p['days'])
                    if d == target_day:
                        redemptions_filtered.append(txn)
                else:
                    start_day = today - timedelta(days=p['days'])
                    if d >= start_day:
                        redemptions_filtered.append(txn)
            
            # Calculate redemptions revenue from transaction amount
            # Note: amount is negative for seller revenue (money goes TO seller)
            redemptions_revenue = sum(abs(txn.get('amount', 0)) for txn in redemptions_filtered)
            redemptions_count = len(redemptions_filtered)
            
            dashboard["period_data"][p_key]["ozon"]["redemptions_revenue"] = redemptions_revenue
            dashboard["period_data"][p_key]["ozon"]["redemptions_count"] = redemptions_count

    # Final Summary and Marketplace Status (Default to Today)
    today_wb = dashboard["period_data"]["today"].get("wb", {})
    today_ozon = dashboard["period_data"]["today"].get("ozon", {})
    
    dashboard["summary"]["total_stocks"] = dashboard["summary"]["wb_stocks"] + dashboard["summary"]["ozon_stocks"]
    dashboard["summary"]["total_sales_today"] = today_wb.get("revenue", 0) + today_ozon.get("revenue", 0)
    
    # Marketplaces array for initial render
    dashboard["marketplaces"] = [
        {
            "name": "Wildberries",
            "status": "Online" if wb_data else "No Data"
        },
        {
            "name": "Ozon",
            "status": "Online" if ozon_data else "No Data"
        }
    ]

    output_path = os.path.join(PROJECT_DIR, 'dashboard_data.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=4)
    
    print(f"Dashboard data prepared with multi-period support.")
    print(f"Total sales (Today): {dashboard['summary']['total_sales_today']:.2f} RUB")
    print(f"Saved to: dashboard_data.json")


if __name__ == "__main__":
    prepare()
