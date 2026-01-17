"""
Test Ozon API - find accessible endpoints.
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv('Credentials.env')

CLIENT_ID = os.getenv('OZON_CLIENT_ID')
API_KEY = os.getenv('OZON_API_KEY')

print(f"Client ID: {CLIENT_ID}")
print(f"API Key: {API_KEY[:15]}...")
print()

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Test many endpoints to find which are accessible
endpoints = [
    # Seller
    ("v1/seller/info", {}),
    
    # Products - different versions
    ("v1/product/list", {"page": 1, "page_size": 10}),
    ("v2/product/list", {"last_id": "", "limit": 10}),
    ("v2/product/info/list", {"product_id": []}),
    ("v4/product/info/prices", {"last_id": "", "limit": 10}),
    
    # Stocks
    ("v1/product/info/stocks", {}),
    ("v2/product/info/stocks", {"product_id": []}),
    ("v3/product/info/stocks", {"filter": {"visibility": "ALL"}, "last_id": "", "limit": 10}),
    
    # FBO
    ("v2/posting/fbo/list", {"dir": "DESC", "limit": 10, "offset": 0}),
    ("v3/posting/fbo/list", {"dir": "DESC", "limit": 10}),
    
    # FBS
    ("v3/posting/fbs/list", {"dir": "DESC", "limit": 10}),
    
    # Analytics
    ("v1/analytics/data", {"date_from": "2026-01-14", "date_to": "2026-01-15", "metrics": ["revenue"], "dimension": ["sku"], "limit": 10}),
    ("v2/analytics/data", {"date_from": "2026-01-14", "date_to": "2026-01-15", "metrics": ["revenue"], "dimension": ["sku"], "limit": 10}),
    ("v1/analytics/stock_on_warehouses", {"limit": 10}),
    
    # Warehouse
    ("v1/warehouse/list", {}),
    
    # Finance
    ("v3/finance/transaction/list", {"page": 1, "page_size": 10}),
    ("v1/finance/realization", {}),
]

print("Testing endpoints...\n")

for endpoint, payload in endpoints:
    url = f"https://api-seller.ozon.ru/{endpoint}"
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        status = r.status_code
        
        if status == 200:
            print(f"[OK]  {endpoint} - Status: {status}")
            # Show first 200 chars of response
            body = r.text[:200].replace('\n', ' ')
            print(f"      Response: {body}...")
        elif status == 400:
            print(f"[??]  {endpoint} - Status: {status} (bad request - but endpoint exists)")
        elif status == 403:
            print(f"[!!]  {endpoint} - Status: {status} (forbidden - no permission)")
        else:
            print(f"[--]  {endpoint} - Status: {status}")
    except Exception as e:
        print(f"[ERR] {endpoint} - {type(e).__name__}")
    
print("\n--- Done ---")
