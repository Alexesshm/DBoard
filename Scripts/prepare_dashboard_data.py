"""
Prepare dashboard data from raw API responses.
Combines WB and Ozon data into a single JSON for the frontend.
Includes warehouse breakdown with products for stacked bar chart.
Calculates sales statistics for multiple periods: Today, Yesterday, 3 Days, 7 Days.
"""

import json
import os
import re
import unicodedata
from datetime import datetime, timedelta, date

# Dynamic path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXECUTIONS_DIR = os.path.join(PROJECT_DIR, 'Executions')

# Virtual/transit rows returned by WB warehouse reports. They are aggregates,
# not real warehouses, and must never be counted as a warehouse (otherwise
# product totals are doubled).
VIRTUAL_WAREHOUSES = {
    'в пути до получателей',
    'в пути возвраты на склад wb',
    'всего находится на складах',
    'итого на складах',
    'в пути к покупателю',
    'в пути на склад',
    'в пути',
}

# Known FBW labels from the seller's WB warehouse list. warehouseType from the
# Statistics API remains authoritative; these names are a compatibility fallback
# for older cached exports that do not include warehouseType.
WB_FBW_WAREHOUSE_NAMES = {
    'склад wb рф',
    'самара (новосемейкино)',
    'самара',
    'котовск',
    'тула',
    'ск ереван',
    'ереван',
}


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


def build_chart_data(stocks_wp, all_articles, mp_type='wb', single_cluster=False):
    """Build Chart.js-ready stacked data with cluster grouping.

    single_cluster=True puts every warehouse into one "Мои склады" group —
    used for the seller's own warehouses (FBS), where marketplace region
    clusters do not apply.
    """
    if not stocks_wp or not all_articles:
        return None

    from collections import defaultdict

    if single_cluster:
        clustered_warehouses = {'Мои склады': list(stocks_wp)}
        sorted_clusters = ['Мои склады']
    else:
        clustered_warehouses = defaultdict(list)
        for wh in stocks_wp:
            clustered_warehouses[get_warehouse_cluster(wh['name'], mp_type)].append(wh)

        if mp_type == 'wb':
            priority_clusters = ['Центральный', 'Северо-Западный', 'Приволжский', 'Уральский']
        else:
            priority_clusters = ['Москва, МО и Дальние регионы', 'Санкт-Петербург и СЗО', 'Казань', 'Краснодар']

        sorted_clusters = [pc for pc in priority_clusters if pc in clustered_warehouses]
        sorted_clusters += sorted(c for c in clustered_warehouses if c not in priority_clusters)

    chart = {'labels': [], 'datasets': [], 'clusters': []}

    for cluster_name in sorted_clusters:
        warehouses = clustered_warehouses[cluster_name]
        total_stock = sum(sum(wh.get('products', {}).values()) for wh in warehouses)
        start = len(chart['labels'])
        for wh in warehouses:
            chart['labels'].append(wh['name'])
        chart['clusters'].append({
            'name': cluster_name,
            'start_index': start,
            'end_index': len(chart['labels']) - 1,
            'warehouse_count': len(warehouses),
            'total_stock': total_stock,
        })

    for article in all_articles:
        color = get_article_color(article)
        data = []
        for cluster_name in sorted_clusters:
            for wh in clustered_warehouses[cluster_name]:
                data.append(wh.get('products', {}).get(article, 0))
        if any(d > 0 for d in data):
            chart['datasets'].append({
                'label': article,
                'data': data,
                'backgroundColor': color,
                'borderColor': '#1a1a1a',
                'borderWidth': 1,
            })

    return chart


def merge_warehouse_lists(main_list, fbs_list, main_source='marketplace'):
    """Concat marketplace + own warehouse lists into one, tagging the source."""
    merged = []
    for w in (main_list or []):
        item = dict(w)
        item.setdefault('source', main_source)
        merged.append(item)
    for w in (fbs_list or []):
        item = dict(w)
        item['source'] = 'fbs'
        merged.append(item)
    return sorted(merged, key=lambda x: x.get('quantity', 0), reverse=True)


def merge_product_lists(main_list, fbs_list, main_source='marketplace'):
    """Merge by-product lists (sum quantity, merge per-warehouse breakdown)."""
    merged = {}
    for src, items in ((main_source, main_list or []), ('fbs', fbs_list or [])):
        for p in items:
            article = p.get('article', 'Unknown')
            m = merged.setdefault(article, {'article': article, 'quantity': 0, 'by_warehouse': {}})
            m['quantity'] += p.get('quantity', 0)
            for w in p.get('by_warehouse', []) or []:
                wm = m['by_warehouse'].setdefault(
                    w['name'], {'name': w['name'], 'quantity': 0, 'source': w.get('source', src)})
                wm['quantity'] += w.get('quantity', 0)
    out = []
    for article, m in merged.items():
        by_wh = sorted(m['by_warehouse'].values(), key=lambda x: x['quantity'], reverse=True)
        out.append({
            'article': article,
            'quantity': m['quantity'],
            'warehouses_count': len(by_wh),
            'by_warehouse': by_wh,
            'color': get_article_color(article),
        })
    return sorted(out, key=lambda x: x['quantity'], reverse=True)


def build_combined_chart_data(stocks_wp, stocks_wp_fbs, all_articles, mp_type='wb'):
    """Chart data for the "Все склады" view: marketplace clusters + "Мои склады"."""
    main = list(stocks_wp or [])
    own = list(stocks_wp_fbs or [])
    if not main and not own:
        return None

    from collections import defaultdict

    articles = set(all_articles or [])
    for wh in own:
        articles.update((wh.get('products') or {}).keys())
    for wh in main:
        articles.update((wh.get('products') or {}).keys())

    clustered = defaultdict(list)
    for wh in main:
        clustered[get_warehouse_cluster(wh['name'], mp_type)].append(wh)

    if mp_type == 'wb':
        priority = ['Центральный', 'Северо-Западный', 'Приволжский', 'Уральский']
    else:
        priority = ['Москва, МО и Дальние регионы', 'Санкт-Петербург и СЗО', 'Казань', 'Краснодар']

    order = [c for c in priority if c in clustered]
    order += sorted(c for c in clustered if c not in priority)
    if own:
        clustered['Мои склады'] = own
        order.append('Мои склады')

    chart = {'labels': [], 'datasets': [], 'clusters': []}
    for cluster_name in order:
        warehouses = clustered[cluster_name]
        total = sum(sum((w.get('products') or {}).values()) for w in warehouses)
        start = len(chart['labels'])
        for w in warehouses:
            chart['labels'].append(w['name'])
        chart['clusters'].append({
            'name': cluster_name,
            'start_index': start,
            'end_index': len(chart['labels']) - 1,
            'warehouse_count': len(warehouses),
            'total_stock': total,
        })

    for article in articles:
        data = []
        for cluster_name in order:
            for w in clustered[cluster_name]:
                data.append((w.get('products') or {}).get(article, 0))
        if any(data):
            chart['datasets'].append({
                'label': article,
                'data': data,
                'backgroundColor': get_article_color(article),
                'borderColor': '#1a1a1a',
                'borderWidth': 1,
            })
    return chart


def normalize_warehouse_name(name):
    """Canonicalize names, ignoring case, spaces, underscores, emoji and punctuation."""
    value = unicodedata.normalize('NFKC', str(name or '')).casefold().replace('ё', 'е')
    return ''.join(char for char in value if char.isalnum())


def warehouse_source_lookup(own_warehouse_names, main_source='fbw'):
    """Build canonical known-name sources; seller API names override defaults."""
    names = {normalize_warehouse_name(n): 'fbs' for n in (own_warehouse_names or []) if normalize_warehouse_name(n)}
    for name in WB_FBW_WAREHOUSE_NAMES:
        names.setdefault(normalize_warehouse_name(name), main_source)
    return names


def classify_wb_warehouse(item, known_warehouse_sources, main_source='fbw'):
    """Classify a WB statistics row using documented warehouseType first.

    Name matching is only a fallback for older exports/fixtures that omit
    warehouseType. Unknown types are not silently treated as FBW.
    """
    warehouse_type = normalize_warehouse_name(item.get('warehouseType') or item.get('warehouse_type'))
    name = normalize_warehouse_name(item.get('warehouseName') or item.get('warehouse_name') or item.get('name'))
    if warehouse_type in {'складпродавца', 'warehouseofseller', 'sellerwarehouse'}:
        return 'fbs'
    if warehouse_type in {'складwb', 'складвайлдберриз', 'wildberrieswarehouse'}:
        return main_source

    if name in known_warehouse_sources:
        return known_warehouse_sources[name]
    return 'unknown'


def tag_sales_sources(agg, own_warehouse_names, main_source='fbw'):
    """Tag sales rows by authoritative WB warehouseType, retaining name fallback."""
    known_warehouse_sources = warehouse_source_lookup(own_warehouse_names, main_source)

    def tag(wh):
        # Preserve separate rows with identical names but different warehouseType.
        # The API type wins per record; known seller/FBW names are fallback only.
        wh['source'] = classify_wb_warehouse(wh, known_warehouse_sources, main_source)

    for wh in agg.get('sales_by_warehouse', []):
        tag(wh)
    for product in agg.get('sales_by_product', []):
        for wh in product.get('by_warehouse', []):
            tag(wh)

    fbs_warehouses = [w for w in agg.get('sales_by_warehouse', []) if w.get('source') == 'fbs']
    unknown_warehouses = [w for w in agg.get('sales_by_warehouse', []) if w.get('source') == 'unknown']
    fbs_revenue = sum(w.get('revenue', 0) for w in fbs_warehouses)
    fbs_count = sum(w.get('count', 0) for w in fbs_warehouses)
    unknown_revenue = sum(w.get('revenue', 0) for w in unknown_warehouses)
    unknown_count = sum(w.get('count', 0) for w in unknown_warehouses)

    agg['revenue_fbs'] = fbs_revenue
    agg['revenue_unknown_source'] = unknown_revenue
    agg['revenue_marketplace'] = agg.get('revenue', 0) - fbs_revenue - unknown_revenue
    agg['orders_count_fbs'] = fbs_count
    agg['orders_count_unknown_source'] = unknown_count
    agg['orders_count_marketplace'] = agg.get('orders_count', 0) - fbs_count - unknown_count
    return agg


def tag_all_sources(agg, source):
    """Tag every warehouse/product row with one source."""
    for wh in agg.get('sales_by_warehouse', []):
        wh['source'] = source
    for product in agg.get('sales_by_product', []):
        for wh in product.get('by_warehouse', []):
            wh['source'] = source
    return agg


def aggregate_wb_fbs_order_placements(orders, seller_warehouses, period_start=None, period_end=None):
    """Aggregate gross FBS assembly-task placements by article and seller warehouse.

    Every task counts once regardless of current/later status. The API's task id
    is used for deduplication; ``createdAt`` defines rolling window membership.
    """
    warehouse_names = {
        str(warehouse_id): str(name)
        for warehouse_id, name in (seller_warehouses or {}).items()
    } if isinstance(seller_warehouses, dict) else {
        str(wh.get('id')): (wh.get('name') or f"Склад {wh.get('id')}")
        for wh in (seller_warehouses or []) if wh.get('id') is not None
    }
    unique = {}
    for order in orders or []:
        order_id = order.get('id')
        article = order.get('article') or 'Unknown'
        warehouse_id = order.get('warehouseId')
        dt = parse_date(order.get('createdAt'))
        if order_id is None or warehouse_id is None or dt is None:
            continue
        if period_start and dt.date() < period_start:
            continue
        if period_end and dt.date() > period_end:
            continue
        unique[str(order_id)] = (str(article), str(warehouse_id), dt)

    products = {}
    for article, warehouse_id, _created_at in unique.values():
        warehouse = warehouse_names.get(warehouse_id, f"Склад {warehouse_id}")
        product = products.setdefault(article, {
            'article': article, 'count': 0, 'revenue': 0, 'by_warehouse': {},
        })
        product['count'] += 1
        row = product['by_warehouse'].setdefault(warehouse, {
            'name': warehouse, 'count': 0, 'revenue': 0, 'source': 'fbs',
        })
        row['count'] += 1

    result = sorted(products.values(), key=lambda item: item['count'], reverse=True)
    for product in result:
        product['by_warehouse'] = sorted(
            product['by_warehouse'].values(), key=lambda item: item['count'], reverse=True
        )
    return result


def aggregate_wb_orders_by_warehouse(products):
    """Aggregate FBS placed-task counts per seller warehouse."""
    warehouses = {}
    for product in products or []:
        for row in product.get('by_warehouse', []):
            name = row.get('name') or 'Склад продавца'
            target = warehouses.setdefault(name, {
                'name': name, 'count': 0, 'revenue': 0, 'by_product': [], 'source': 'fbs',
            })
            count = int(row.get('count', 0) or 0)
            target['count'] += count
            target['by_product'].append({
                'article': product.get('article', 'Unknown'), 'count': count, 'revenue': 0,
            })
    return sorted(warehouses.values(), key=lambda item: item['count'], reverse=True)


def aggregate_wb_realized_sales(sales_list, own_warehouse_names, period_start=None, period_end=None):
    """Build net realized sold units by article and source from WB sales rows."""
    known = warehouse_source_lookup(own_warehouse_names, 'fbw')
    unique = {}
    for item in sales_list or []:
        article = item.get('supplierArticle') or 'Unknown'
        name = item.get('warehouseName') or item.get('warehouse_name') or 'Unknown'
        source = classify_wb_warehouse(item, known, 'fbw')
        if source == 'unknown':
            continue
        sale_id = str(item.get('saleID') or item.get('saleId') or '')
        dt = parse_date(item.get('date') or item.get('dateFull'))
        if dt and period_start and period_end and not (period_start <= dt.date() <= period_end):
            continue
        unique[(article, name, source, sale_id)] = item

    products = {}
    for (article, name, source, sale_id), item in unique.items():
        qty = -1 if sale_id.upper().startswith('R') else 1
        # FBW order labels are a pooled reporting bucket, not warehouse attribution.
        name = 'Склад WB РФ' if source == 'fbw' else name
        product = products.setdefault(article, {'article': article, 'count': 0, 'revenue': 0, 'by_warehouse': {}})
        product['count'] += qty
        row = product['by_warehouse'].setdefault((name, source), {
            'name': name, 'count': 0, 'revenue': 0, 'source': source,
        })
        row['count'] += qty

    result = []
    for product in products.values():
        product['by_warehouse'] = list(product['by_warehouse'].values())
        result.append(product)
    return sorted(result, key=lambda p: p['count'], reverse=True)


def aggregate_fbs_sales_data(sales_list):
    """Aggregate Ozon FBS postings (sales from the seller's own warehouses)."""
    total_revenue = 0
    orders_count = 0
    by_warehouse = {}
    by_region = {}
    by_product = {}

    for item in sales_list:
        orders_count += 1
        analytics = item.get('analytics_data') or {}
        wh_name = (item.get('warehouse_name')
                   or (item.get('warehouse') or {}).get('name')
                   or analytics.get('warehouse_name')
                   or 'Свой склад')
        region = analytics.get('region') or analytics.get('city') or 'Свой склад'

        if wh_name not in by_warehouse:
            by_warehouse[wh_name] = {'name': wh_name, 'count': 0, 'revenue': 0,
                                     'by_product': {}, 'source': 'fbs'}
        wh = by_warehouse[wh_name]

        order_price = 0
        for prod in (item.get('products') or []):
            article = prod.get('offer_id', 'Unknown')
            p_price = _to_float(prod.get('price'))
            p_qty = int(prod.get('quantity', 1) or 1)
            p_revenue = p_price * p_qty
            order_price += p_revenue

            p = by_product.setdefault(article, {'article': article, 'count': 0,
                                               'revenue': 0, 'by_warehouse': {}})
            p['count'] += p_qty
            p['revenue'] += p_revenue
            w = p['by_warehouse'].setdefault(wh_name, {'name': wh_name, 'count': 0,
                                                       'revenue': 0, 'source': 'fbs'})
            w['count'] += p_qty
            w['revenue'] += p_revenue

            wp = wh['by_product'].setdefault(article, {'article': article, 'count': 0, 'revenue': 0})
            wp['count'] += p_qty
            wp['revenue'] += p_revenue

        total_revenue += order_price
        wh['count'] += 1
        wh['revenue'] += order_price

        rg = by_region.setdefault(region, {'name': region, 'count': 0, 'revenue': 0, 'source': 'fbs'})
        rg['count'] += 1
        rg['revenue'] += order_price

    for wh in by_warehouse.values():
        wh['by_product'] = sorted(wh['by_product'].values(), key=lambda x: x['count'], reverse=True)

    sorted_products = sorted(by_product.values(), key=lambda x: x['revenue'], reverse=True)
    for p in sorted_products:
        p['by_warehouse'] = sorted(p['by_warehouse'].values(), key=lambda x: x['revenue'], reverse=True)

    return {
        'revenue': total_revenue,
        'orders_count': orders_count,
        'sales_by_warehouse': sorted(by_warehouse.values(), key=lambda x: x['revenue'], reverse=True)[:15],
        'sales_by_region': sorted(by_region.values(), key=lambda x: x['revenue'], reverse=True)[:15],
        'sales_by_product': sorted_products,
        'source': 'fbs',
    }


def merge_sales_aggs(main_agg, fbs_agg):
    """Merge FBO/FBW aggregate and FBS aggregate into one combined aggregate."""
    out = {
        'revenue': main_agg.get('revenue', 0) + fbs_agg.get('revenue', 0),
        'orders_count': main_agg.get('orders_count', 0) + fbs_agg.get('orders_count', 0),
        'sales_by_warehouse': [],
        'sales_by_region': [],
        'sales_by_product': [],
        'revenue_marketplace': main_agg.get('revenue', 0),
        'revenue_fbs': fbs_agg.get('revenue', 0),
        'orders_count_marketplace': main_agg.get('orders_count', 0),
        'orders_count_fbs': fbs_agg.get('orders_count', 0),
    }

    wh = {}
    for agg in (main_agg, fbs_agg):
        for w in agg.get('sales_by_warehouse', []):
            m = wh.setdefault(w['name'], {'name': w['name'], 'count': 0, 'revenue': 0,
                                          'by_product': {}, 'source': w.get('source', 'marketplace')})
            m['count'] += w.get('count', 0)
            m['revenue'] += w.get('revenue', 0)
            for p in w.get('by_product', []):
                pp = m['by_product'].setdefault(p['article'], {'article': p['article'],
                                                               'count': 0, 'revenue': 0})
                pp['count'] += p.get('count', 0)
                pp['revenue'] += p.get('revenue', 0)
    out['sales_by_warehouse'] = sorted(wh.values(), key=lambda x: x['revenue'], reverse=True)
    for w in out['sales_by_warehouse']:
        w['by_product'] = sorted(w['by_product'].values(), key=lambda x: x['count'], reverse=True)

    rg = {}
    for agg in (main_agg, fbs_agg):
        for r in agg.get('sales_by_region', []):
            m = rg.setdefault(r['name'], {'name': r['name'], 'count': 0, 'revenue': 0})
            m['count'] += r.get('count', 0)
            m['revenue'] += r.get('revenue', 0)
    out['sales_by_region'] = sorted(rg.values(), key=lambda x: x['revenue'], reverse=True)[:15]

    pr = {}
    for agg in (main_agg, fbs_agg):
        for p in agg.get('sales_by_product', []):
            m = pr.setdefault(p['article'], {'article': p['article'], 'count': 0,
                                             'revenue': 0, 'by_warehouse': {}})
            m['count'] += p.get('count', 0)
            m['revenue'] += p.get('revenue', 0)
            for w in p.get('by_warehouse', []):
                ww = m['by_warehouse'].setdefault(w['name'], {'name': w['name'], 'count': 0,
                                                              'revenue': 0,
                                                              'source': w.get('source', 'marketplace')})
                ww['count'] += w.get('count', 0)
                ww['revenue'] += w.get('revenue', 0)
    out['sales_by_product'] = sorted(pr.values(), key=lambda x: x['revenue'], reverse=True)
    for p in out['sales_by_product']:
        p['by_warehouse'] = sorted(p['by_warehouse'].values(), key=lambda x: x['revenue'], reverse=True)

    return out


def get_order_date(item):
    """Return the first available order date field."""
    for key in ('created_at', 'in_process_at', 'order_date', 'date', 'dateFull'):
        value = item.get(key)
        if value:
            return value
    return None


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
        qty = item.get('quantity', 0)  # Остатки, доступные для заказа
        warehouse = item.get('warehouseName', 'Unknown')

        # Never count virtual/transit rows — they duplicate real warehouses
        if warehouse.lower() in VIRTUAL_WAREHOUSES:
            continue

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


def _to_float(value):
    """Coerce an Ozon price field (str | float | int | dict) to float."""
    if value is None:
        return 0.0
    if isinstance(value, dict):
        for key in ('amount', 'price', 'value'):
            if key in value:
                return _to_float(value[key])
        return 0.0
    if isinstance(value, str):
        value = value.replace('\u00a0', '').replace(' ', '').replace(',', '.')
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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
            
            # Calculate total order price from products (price x quantity)
            price = 0
            for prod in item.get('products', []) or []:
                price += _to_float(prod.get('price')) * int(prod.get('quantity', 1) or 1)
                
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
        
        # Keep WB warehouses with the same display name but different API types
        # separate; `warehouseType` is the authoritative FBW/FBS distinction.
        warehouse_type = item.get('warehouseType') or item.get('warehouse_type') or ''
        warehouse_key = (wh_name, warehouse_type) if mp_type == 'wb' else wh_name
        if warehouse_key not in by_warehouse:
            by_warehouse[warehouse_key] = {
                'name': wh_name, 'warehouseType': warehouse_type,
                'count': 0, 'revenue': 0, 'by_product': {},
            }
        by_warehouse[warehouse_key]['count'] += 1
        by_warehouse[warehouse_key]['revenue'] += price
        
        # Add product to warehouse breakdown (for WB)
        if mp_type == 'wb':
            if article not in by_warehouse[warehouse_key]['by_product']:
                by_warehouse[warehouse_key]['by_product'][article] = {'article': article, 'count': 0, 'revenue': 0}
            by_warehouse[warehouse_key]['by_product'][article]['count'] += 1
            by_warehouse[warehouse_key]['by_product'][article]['revenue'] += price
        
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
            
            if warehouse_key not in by_product[article]['by_warehouse']:
                 by_product[article]['by_warehouse'][warehouse_key] = {
                     'name': wh_name, 'warehouseType': warehouse_type,
                     'count': 0, 'revenue': 0,
                 }
            by_product[article]['by_warehouse'][warehouse_key]['count'] += 1
            by_product[article]['by_warehouse'][warehouse_key]['revenue'] += price
            
        else: # Ozon - iterate products in order
            for prod in item.get('products', []): # Top level products? No, in 'products' list of order (v2/posting/fbo/list)
                # Wait, raw_orders has 'products' at top level? No, check fetch_ozon_orders.
                # fetch_ozon_orders returns list of postings. Posting has 'products'.
                p_article = prod.get('offer_id', 'Unknown')
                p_price = _to_float(prod.get('price'))
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
        dashboard["summary"]["wb_stocks_fbo"] = wb_data.get('total_stock_value', 0)
        dashboard["summary"]["wb_stocks_fbs"] = wb_data.get('total_stock_fbs', 0)
        
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

        # Seller own warehouses (FBS) — a separate "Мои склады" source.
        # These never fall into marketplace region clusters, so one synthetic
        # cluster is used for the chart.
        wb_by_product_fbs = calculate_total_stocks_by_product(wb_data.get('raw_stocks_fbs', []))
        for item in wb_by_product_fbs:
            item['color'] = get_article_color(item.get('article', ''))
        dashboard["stocks"]["wb"]["by_warehouse_fbs"] = wb_data.get('stocks_by_warehouse_fbs', [])[:15]
        dashboard["stocks"]["wb"]["by_product_fbs"] = wb_by_product_fbs
        dashboard["stocks"]["wb"]["chart_data_fbs"] = build_chart_data(
            wb_data.get('stocks_warehouse_products_fbs'),
            wb_data.get('all_articles_fbs'),
            'wb',
            single_cluster=True,
        )
        dashboard["stocks"]["wb"]["all_articles_fbs"] = wb_data.get('all_articles_fbs', [])

        # Combined view ("Все склады") — the default
        dashboard["stocks"]["wb"]["by_warehouse_all"] = merge_warehouse_lists(
            dashboard["stocks"]["wb"].get("by_warehouse", []),
            dashboard["stocks"]["wb"].get("by_warehouse_fbs", []),
            main_source='fbw',
        )
        dashboard["stocks"]["wb"]["by_product_all"] = merge_product_lists(
            dashboard["stocks"]["wb"].get("by_product", []),
            dashboard["stocks"]["wb"].get("by_product_fbs", []),
            main_source='fbw',
        )
        dashboard["stocks"]["wb"]["chart_data_all"] = build_combined_chart_data(
            wb_data.get('stocks_warehouse_products'),
            wb_data.get('stocks_warehouse_products_fbs'),
            wb_data.get('all_articles'),
            'wb',
        )
        dashboard["stocks"]["wb"]["all_articles_all"] = sorted(
            set(wb_data.get('all_articles', [])) | set(wb_data.get('all_articles_fbs', []))
        )

        # Sales (Orders) Processing Per Period
        raw_orders = wb_data.get('raw_orders', [])
        raw_fbs_orders = wb_data.get('raw_fbs_orders', [])
        seller_warehouses = wb_data.get('seller_warehouses', [])
        wb_own_names = [w.get('name') for w in seller_warehouses if w.get('name')]
        
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
            
            # Aggregate (tag own vs marketplace warehouses)
            agg = aggregate_sales_data(filtered_sales, 'wb')
            tag_sales_sources(agg, wb_own_names, main_source='fbw')
            if p_key not in dashboard["period_data"]: dashboard["period_data"][p_key] = {}
            dashboard["period_data"][p_key]["wb"] = agg

            # Gross placed FBS assembly tasks from Marketplace API. This is a
            # separate metric: do not decrement on cancellation/return and do
            # not mix it with sale/redemption accounting.
            period_end = today - timedelta(days=p['days']) if p.get('exact_day') else today
            period_start = period_end if p.get('exact_day') else today - timedelta(days=p['days'])
            fbs_placements = aggregate_wb_fbs_order_placements(
                raw_fbs_orders, seller_warehouses, period_start, period_end
            )
            dashboard["period_data"][p_key]["wb"]["orders_by_product_fbs"] = fbs_placements
            dashboard["period_data"][p_key]["wb"]["orders_by_warehouse_fbs"] = aggregate_wb_orders_by_warehouse(
                fbs_placements
            )
            dashboard["period_data"][p_key]["wb"]["fbs_placed_orders_count"] = sum(
                int(product.get('count', 0) or 0) for product in fbs_placements
            )
            dashboard["period_data"][p_key]["wb"]["fbs_orders_metric"] = 'placed_assembly_tasks'
            dashboard["period_data"][p_key]["wb"]["consumption_by_product_fbs"] = fbs_placements
        
        # Redemptions (Sales/Buyouts) Processing Per Period
        raw_sales = wb_data.get('raw_sales', [])
        
        raw_sales_by_id = {
            str(item.get('saleID') or item.get('saleId')): item
            for item in raw_sales
            if item.get('saleID') or item.get('saleId')
        }
        for p in periods_config:
            p_key = p['key']
            period_end = today - timedelta(days=p['days']) if p.get('exact_day') else today
            period_start = period_end if p.get('exact_day') else today - timedelta(days=p['days'])
            filtered_redemptions = []
            
            for item in raw_sales_by_id.values():
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
            
            # Add redemption totals and a warehouse/article consumption series.
            # This powers coverage calculations; order placements remain separately
            # available in sales_by_product for the order analytics screen.
            if p_key in dashboard["period_data"] and "wb" in dashboard["period_data"][p_key]:
                wb_period = dashboard["period_data"][p_key]["wb"]
                wb_period["redemptions_revenue"] = redemptions_revenue
                wb_period["redemptions_count"] = redemptions_count
                wb_period["consumption_by_product"] = aggregate_wb_realized_sales(
                    raw_sales_by_id.values(), wb_own_names, period_start, period_end
                )
                wb_period["consumption_as_of"] = wb_data.get('fetch_time')
            
    # --- Process Ozon Data ---
    if ozon_data:
        # Stocks
        dashboard["summary"]["ozon_stocks"] = ozon_data.get('total_stock_value', 0)
        dashboard["summary"]["ozon_stocks_fbo"] = ozon_data.get('total_stock_value', 0)
        dashboard["summary"]["ozon_stocks_fbs"] = ozon_data.get('total_stock_fbs', 0)
        
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

        # Seller own warehouses (FBS) — a separate "Мои склады" source
        ozon_by_product_fbs = ozon_data.get('stocks_by_product_fbs', [])
        for item in ozon_by_product_fbs:
            item['color'] = get_article_color(item.get('article', ''))
        dashboard["stocks"]["ozon"]["by_warehouse_fbs"] = ozon_data.get('stocks_by_warehouse_fbs', [])[:15]
        dashboard["stocks"]["ozon"]["by_product_fbs"] = ozon_by_product_fbs
        dashboard["stocks"]["ozon"]["chart_data_fbs"] = build_chart_data(
            ozon_data.get('stocks_warehouse_products_fbs'),
            ozon_data.get('all_articles_fbs'),
            'ozon',
            single_cluster=True,
        )
        dashboard["stocks"]["ozon"]["all_articles_fbs"] = ozon_data.get('all_articles_fbs', [])

        # Combined view ("Все склады") — the default
        dashboard["stocks"]["ozon"]["by_warehouse_all"] = merge_warehouse_lists(
            dashboard["stocks"]["ozon"].get("by_warehouse", []),
            dashboard["stocks"]["ozon"].get("by_warehouse_fbs", []),
            main_source='fbo',
        )
        dashboard["stocks"]["ozon"]["by_product_all"] = merge_product_lists(
            dashboard["stocks"]["ozon"].get("by_product", []),
            dashboard["stocks"]["ozon"].get("by_product_fbs", []),
            main_source='fbo',
        )
        dashboard["stocks"]["ozon"]["chart_data_all"] = build_combined_chart_data(
            ozon_data.get('stocks_warehouse_products'),
            ozon_data.get('stocks_warehouse_products_fbs'),
            ozon_data.get('all_articles'),
            'ozon',
        )
        dashboard["stocks"]["ozon"]["all_articles_all"] = sorted(
            set(ozon_data.get('all_articles', [])) | set(ozon_data.get('all_articles_fbs', []))
        )

        # Sales Processing Per Period (FBO + FBS)
        raw_orders = ozon_data.get('raw_orders', [])
        raw_orders_fbs = ozon_data.get('raw_orders_fbs', [])

        def _filter_by_period(items, p):
            result = []
            for item in items:
                dt = parse_date(get_order_date(item))
                if not dt:
                    continue
                d = dt.date()
                if p.get('exact_day'):
                    if d == today - timedelta(days=p['days']):
                        result.append(item)
                else:
                    if d >= today - timedelta(days=p['days']):
                        result.append(item)
            return result

        for p in periods_config:
            p_key = p['key']
            # Marketplace (FBO) orders
            fbo_agg = aggregate_sales_data(_filter_by_period(raw_orders, p), 'ozon')
            tag_all_sources(fbo_agg, 'fbo')
            # Seller own warehouse (FBS) orders
            fbs_agg = aggregate_fbs_sales_data(_filter_by_period(raw_orders_fbs, p))
            # Combined view
            agg = merge_sales_aggs(fbo_agg, fbs_agg)
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
    
    dashboard["summary"]["total_stocks"] = (
        dashboard["summary"]["wb_stocks"]
        + dashboard["summary"]["ozon_stocks"]
        + dashboard["summary"].get("wb_stocks_fbs", 0)
        + dashboard["summary"].get("ozon_stocks_fbs", 0)
    )
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
