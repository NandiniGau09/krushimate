
import requests

try:
    response = requests.get('http://127.0.0.1:5000/api/market_prices')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")

