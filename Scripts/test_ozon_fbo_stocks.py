
import os
import requests
import json
from dotenv import load_dotenv

# Load credentials
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(PROJECT_DIR, 'Credentials.env')
load_dotenv(ENV_PATH)
CLIENT_ID = os.getenv('OZON_CLIENT_ID')
API_KEY = os.getenv('OZON_API_KEY')

HEADERS = {
    "Client-Id": CLIENT_ID,
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}

def test_fbo_stocks():
    url = "https://api-seller.ozon.ru/v1/analytics/stock_on_warehouses"
    payload = {"limit": 1000, "offset": 0}
    
    print(f"Testing {url}...")
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_fbo_stocks()
