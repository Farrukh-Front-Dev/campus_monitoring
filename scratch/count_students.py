#!/usr/bin/env python3
import os
import sys
import requests
from src.config import Config
from src.api.school21 import School21API

def get_participants_count(api, campus_name, campus_uuid):
    headers = api._get_headers()
    url = f"{api.BASE_URL}/campuses/{campus_uuid}/participants"
    limit = 100
    
    print(f"\n📊 {campus_name} kampusi o'quvchilari sonini aniqlash...")
    
    # We will do a binary search on the page index to find the last page
    # Let's first find the upper bound
    low = 0
    high = 15000 # Upper bound estimate
    
    # Binary search over offsets (multiples of 100)
    while low <= high:
        mid = ((low + high) // 2) // 100 * 100
        resp = requests.get(url, headers=headers, params={"limit": limit, "offset": mid})
        if resp.status_code != 200:
            print(f"❌ Xatolik: {resp.status_code}")
            return None
            
        data = resp.json()
        participants = data.get('participants', [])
        print(f"Tekshirish (offset={mid}): {len(participants)} ta o'quvchi topildi.")
        
        if len(participants) == 0:
            # Too high, search in lower half
            high = mid - 100
        elif len(participants) < limit:
            # We found the exact last page!
            total = mid + len(participants)
            return total
        else:
            # This page is full, the end is higher
            # Let's check if the next page is empty
            resp_next = requests.get(url, headers=headers, params={"limit": limit, "offset": mid + 100})
            if resp_next.status_code == 200:
                next_len = len(resp_next.json().get('participants', []))
                if next_len == 0:
                    # mid was the last full page!
                    return mid + limit
            low = mid + 100
            
    return low

def main():
    config = Config.from_env()
    api = School21API(config.SCHOOL21_USERNAME, config.SCHOOL21_PASSWORD)
    
    if not api.authenticate():
        print("❌ Authentication failed.")
        sys.exit(1)
        
    campuses = [
        {"name": "21 Samarkand", "uuid": "667a42af-5469-4a33-9858-677d9d20956a"},
        {"name": "21 Tashkent", "uuid": "bad03b39-ffd4-4217-9d24-65535fe1f293"}
    ]
    
    results = {}
    for c in campuses:
        count = get_participants_count(api, c["name"], c["uuid"])
        results[c["name"]] = count
        
    print("\n" + "="*40)
    print("📈 YAKUNIY NATIJALAR (ANIQ):")
    print("="*40)
    for name, count in results.items():
        if count is not None:
            print(f"🔹 {name:<15}: {count:,} ta o'quvchi")
        else:
            print(f"🔹 {name:<15}: Aniqlab bo'lmadi")
    print("="*40 + "\n")

if __name__ == "__main__":
    main()
