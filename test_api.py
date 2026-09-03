#!/usr/bin/env python3
"""
Test Bzzoiro API endpoints
"""

import requests
import json

TOKEN = "acec18e5caf0091791d1afee0a220d04140fc040"
HEADERS = {"Authorization": f"Token {TOKEN}"}
BASE = "https://sports.bzzoiro.com/api/v2"

def test_endpoint(name, url):
    print(f"\n🔍 Testing {name}...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())[:5]}...")
                if 'standings' in data:
                    print(f"  Standings count: {len(data.get('standings', []))}")
            elif isinstance(data, list):
                print(f"  Items: {len(data)}")
        else:
            print(f"  Error: {r.text[:100]}")
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("BZZOIRO API TEST")
    print("=" * 60)
    
    test_endpoint("Live Events", f"{BASE}/events/live/")
    test_endpoint("Standings (Premier League)", f"{BASE}/leagues/1/standings/")
    test_endpoint("Leagues", f"{BASE}/leagues/")