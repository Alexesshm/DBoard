"""
Diagnostic script for Ozon API - detailed error checking.
Tests multiple API endpoints and reports detailed errors.
"""

import requests
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8')

# Dynamic path resolution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CREDENTIALS_PATH = os.path.join(PROJECT_DIR, 'Credentials.env')

load_dotenv(CREDENTIALS_PATH)

CLIENT_ID = os.getenv('OZON_CLIENT_ID')
API_KEY = os.getenv('OZON_API_KEY')

# Mask the API key for display
KEY_MASKED = f"{API_KEY[:8]}...{API_KEY[-4:]}" if API_KEY and len(API_KEY) > 12 else "NOT SET"

print("=" * 60)
print("OZON API DIAGNOSTIC")
print("=" * 60)
print(f"Client ID: {CLIENT_ID}")
print(f"API Key: {KEY_MASKED}")
print("-" * 60)

HEADERS = {
    "Client-Id": str(CLIENT_ID),  # Ensure string
    "Api-Key": str(API_KEY),
    "Content-Type": "application/json"
}

def test_endpoint(name, url, payload, method="POST"):
    """Test a single API endpoint and print detailed results."""
    print(f"\n[TEST] {name}")
    print(f"   URL: {url}")
    
    try:
        if method == "POST":
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        else:
            response = requests.get(url, headers=HEADERS, timeout=30)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # Count items in result
            result = data.get('result', data)
            if isinstance(result, dict):
                if 'items' in result:
                    print(f"   [OK] Success! Items: {len(result['items'])}")
                elif 'rows' in result:
                    print(f"   [OK] Success! Rows: {len(result['rows'])}")
                elif 'data' in result:
                    print(f"   [OK] Success! Data: {len(result['data'])}")
                elif 'postings' in result:
                    print(f"   [OK] Success! Postings: {len(result['postings'])}")
                else:
                    print(f"   [OK] Success! Keys: {list(result.keys())[:5]}")
            elif isinstance(result, list):
                print(f"   [OK] Success! List: {len(result)} items")
            else:
                print(f"   [OK] Success! Response type: {type(result)}")
            return True, data
        else:
            print(f"   [FAIL] Status: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"   Error details: {json.dumps(error_detail, ensure_ascii=False, indent=2)[:500]}")
            except:
                print(f"   Response: {response.text[:300]}")
            return False, None
            
    except requests.exceptions.Timeout:
        print(f"   [TIMEOUT]")
        return False, None
    except Exception as e:
        print(f"   [ERROR] Exception: {e}")
        return False, None


# Test 1: Seller Info (basic auth check)
test_endpoint(
    "Seller Info (Auth Check)",
    "https://api-seller.ozon.ru/v3/seller/info",
    {}
)

# Test 2: Warehouse list
test_endpoint(
    "Warehouse List",
    "https://api-seller.ozon.ru/v1/warehouse/list",
    {}
)

# Test 3: Product list (simpler endpoint)
test_endpoint(
    "Product List (v2)",
    "https://api-seller.ozon.ru/v2/product/list",
    {
        "filter": {},
        "last_id": "",
        "limit": 10
    }
)

# Test 4: Product info/stocks (the one that fails with 404)
test_endpoint(
    "Product Info Stocks (v3)",
    "https://api-seller.ozon.ru/v3/product/info/stocks",
    {
        "filter": {"visibility": "ALL"},
        "last_id": "",
        "limit": 100
    }
)

# Test 5: FBO stocks on warehouses
test_endpoint(
    "FBO Stocks on Warehouses",
    "https://api-seller.ozon.ru/v1/analytics/stock_on_warehouses",
    {"limit": 10, "offset": 0}
)

# Test 6: FBO postings list
dt_now = datetime.now()
dt_from = dt_now - timedelta(days=7)  # Last 7 days
test_endpoint(
    "FBO Postings List (v3)",
    "https://api-seller.ozon.ru/v3/posting/fbo/list",
    {
        "dir": "DESC",
        "filter": {
            "since": dt_from.strftime('%Y-%m-%dT00:00:00.000Z'),
            "to": dt_now.strftime('%Y-%m-%dT23:59:59.999Z'),
            "status": ""
        },
        "limit": 10,
        "offset": 0
    }
)

# Test 7: FBS postings list (alternative)
test_endpoint(
    "FBS Postings List (v3)",
    "https://api-seller.ozon.ru/v3/posting/fbs/list",
    {
        "dir": "DESC",
        "filter": {
            "since": dt_from.strftime('%Y-%m-%dT00:00:00.000Z'),
            "to": dt_now.strftime('%Y-%m-%dT23:59:59.999Z'),
            "status": ""
        },
        "limit": 10,
        "offset": 0
    }
)

# Test 8: Analytics data (CORRECT - v1, not v2!)
test_endpoint(
    "Analytics Data (v1 - CORRECT)",
    "https://api-seller.ozon.ru/v1/analytics/data",
    {
        "date_from": dt_from.strftime('%Y-%m-%d'),
        "date_to": dt_now.strftime('%Y-%m-%d'),
        "metrics": ["revenue", "ordered_units"],
        "dimension": ["sku"],
        "limit": 10,
        "offset": 0
    }
)

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
print("""
📋 Обзор ошибок:
   
HTTP 404 - Endpoint не найден или недоступен для вашего типа аккаунта
HTTP 403 - Недостаточно прав у API ключа  
HTTP 400 - Неверные параметры запроса
HTTP 401 - Неверная авторизация (Client-Id или Api-Key)

💡 Рекомендации:
1. Проверьте права API ключа в личном кабинете Ozon Seller
2. Убедитесь, что у вас есть активные товары на FBO/FBS
3. Проверьте, что склады не отключены (status != "disabled")
4. Если все склады RFBS - используйте другие эндпоинты для rFBS
""")
