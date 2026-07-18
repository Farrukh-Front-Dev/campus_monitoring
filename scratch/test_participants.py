#!/usr/bin/env python3
import os
import sys
import requests
from src.config import Config
from src.api.school21 import School21API

def main():
    config = Config.from_env()
    api = School21API(config.SCHOOL21_USERNAME, config.SCHOOL21_PASSWORD)
    
    if not api.authenticate():
        print("❌ Authentication failed.")
        sys.exit(1)
        
    headers = api._get_headers()
    
    # Campus UUIDs discovered from the code
    campuses = [
        {"name": "21 Samarkand", "uuid": "667a42af-5469-4a33-9858-677d9d20956a"},
        {"name": "21 Tashkent", "uuid": "bad03b39-ffd4-4217-9d24-65535fe1f293"}
    ]
    
    for c in campuses:
        uuid = c["uuid"]
        name = c["name"]
        
        # Test request to get participants
        url = f"{api.BASE_URL}/campuses/{uuid}/participants"
        print(f"\n⏳ Fetching participants for {name} ({uuid})...")
        
        # S21 participants endpoint uses limit and offset
        resp = requests.get(url, headers=headers, params={"limit": 50, "offset": 0})
        print(f"Status Code: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            # print response keys or first few records
            if isinstance(data, dict):
                print("Response keys:", list(data.keys()))
                participants = data.get('participants', [])
                print(f"Joriy sahifadagi o'quvchilar soni (limit=50): {len(participants)}")
                # Check if total count is returned in the response
                total = data.get('total') or data.get('count') or data.get('totalCount')
                if total is not None:
                    print(f"💰 Jami o'quvchilar soni (Total): {total}")
                else:
                    # Let's see if we can read other fields
                    print("Example participants list:", participants[:5])
            else:
                print(f"Response: {str(data)[:200]}")
        else:
            print(f"Response failed: {resp.text}")

if __name__ == "__main__":
    main()
