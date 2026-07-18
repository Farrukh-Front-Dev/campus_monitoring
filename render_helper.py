#!/usr/bin/env python3
import os
import sys
import json
import argparse
import requests
from datetime import datetime

# Load environment variables from .env
def load_env_vars():
    env_vars = {}
    env_files = ['.env', '../.env']
    for env_file in env_files:
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            except Exception:
                pass
            break
    return env_vars

env_vars = load_env_vars()
API_KEY = os.environ.get('RENDER_API_KEY', env_vars.get('RENDER_API_KEY', ''))
BASE_URL = "https://api.render.com/v1"

def get_headers():
    if not API_KEY:
        print("\033[91m❌ Xatolik: RENDER_API_KEY topilmadi. .env fayliga RENDER_API_KEY=kalitingiz ni qo'shing!\033[0m")
        sys.exit(1)
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

def list_services():
    url = f"{BASE_URL}/services"
    headers = get_headers()
    try:
        resp = requests.get(url, headers=headers, params={"limit": 20})
        resp.raise_for_status()
        services = resp.json()
        
        print("\n\033[94m━" * 80)
        print(f"{'ID':<25} | {'Nomi':<20} | {'Turi':<15} | {'Holati':<10}")
        print("━" * 80 + "\033[0m")
        
        for item in services:
            svc = item.get('service', item)
            svc_id = svc.get('id')
            name = svc.get('name')
            svc_type = svc.get('type')
            status = svc.get('status')
            
            status_color = "\033[92m" if status == "active" else "\033[93m" if status == "suspended" else "\033[91m"
            print(f"{svc_id:<25} | {name:<20} | {svc_type:<15} | {status_color}{status:<10}\033[0m")
        print("\033[94m━" * 80 + "\033[0m\n")
    except Exception as e:
        print(f"\033[91m❌ Xatolik yuz berdi: {e}\033[0m")

def get_service_status(service_id):
    headers = get_headers()
    try:
        # Get service details
        url_svc = f"{BASE_URL}/services/{service_id}"
        resp_svc = requests.get(url_svc, headers=headers)
        resp_svc.raise_for_status()
        svc = resp_svc.json()
        
        print("\n\033[94m━" * 50)
        print(f"\033[1m📊 Xizmat Tafsilotlari: {svc.get('name')}\033[0m")
        print("━" * 50 + "\033[0m")
        print(f"ID:          {svc.get('id')}")
        print(f"Turi:        {svc.get('type')}")
        print(f"Holati:      {svc.get('status')}")
        print(f"Repo:        {svc.get('repo')}")
        print(f"Yangilangan: {svc.get('updatedAt')}")
        print(f"Owner ID:    {svc.get('ownerId')}")
        
        # Get latest deploys
        url_deploys = f"{BASE_URL}/services/{service_id}/deploys"
        resp_deploys = requests.get(url_deploys, headers=headers, params={"limit": 5})
        if resp_deploys.status_code == 200:
            deploys = resp_deploys.json()
            print("\n\033[1m🚀 Oxirgi Deploylar:\033[0m")
            for item in deploys:
                d = item.get('deploy', item)
                d_id = d.get('id')
                status = d.get('status')
                trigger = d.get('trigger')
                created = d.get('createdAt')
                
                status_color = "\033[92m" if status == "live" else "\033[93m" if status in ("building", "pre_deploy_in_progress") else "\033[91m"
                print(f"  - {d_id:<24} | {status_color}{status:<15}\033[0m | Trigger: {trigger} | Vaqti: {created}")
        print("\033[94m━" * 50 + "\033[0m\n")
    except Exception as e:
        print(f"\033[91m❌ Xatolik yuz berdi: {e}\033[0m")

def trigger_deploy(service_id, clear_cache=False):
    url = f"{BASE_URL}/services/{service_id}/deploys"
    headers = get_headers()
    data = {}
    if clear_cache:
        data = {"clearCache": "clear"}
    try:
        print(f"⌛ Service {service_id} uchun qayta deploy yuborilmoqda...")
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        deploy = resp.json()
        d = deploy.get('deploy', deploy)
        print(f"\033[92m✅ Deploy muvaffaqiyatli boshlandi!\033[0m")
        print(f"Deploy ID: {d.get('id')}")
        print(f"Status:    {d.get('status')}")
    except Exception as e:
        print(f"\033[91m❌ Deploy qilishda xatolik: {e}\033[0m")

def fetch_logs(service_id):
    headers = get_headers()
    try:
        # First, fetch service details to get ownerId
        url_svc = f"{BASE_URL}/services/{service_id}"
        resp_svc = requests.get(url_svc, headers=headers)
        resp_svc.raise_for_status()
        svc = resp_svc.json()
        owner_id = svc.get('ownerId')
        
        if not owner_id:
            print("\033[91m❌ Xatolik: Xizmat egasining ID (ownerId) topilmadi.\033[0m")
            return
            
        print(f"⌛ Logs yuklanmoqda... (Owner: {owner_id}, Service: {service_id})")
        url_logs = f"{BASE_URL}/logs"
        params = {
            "ownerId": owner_id,
            "resource": service_id
        }
        resp_logs = requests.get(url_logs, headers=headers, params=params)
        resp_logs.raise_for_status()
        logs_data = resp_logs.json()
        
        # Output logs
        print("\n\033[94m━" * 80)
        print("\033[1m📝 Render Logs (Oxirgi 1 soatlik):\033[0m")
        print("━" * 80 + "\033[0m")
        
        # Logs usually come as list of log lines or structure
        if isinstance(logs_data, list):
            for log in logs_data:
                ts = log.get('timestamp', '')
                msg = log.get('text', log.get('message', ''))
                print(f"[{ts}] {msg}")
        elif isinstance(logs_data, dict) and 'logs' in logs_data:
            for log in logs_data['logs']:
                ts = log.get('timestamp', '')
                msg = log.get('text', log.get('message', ''))
                print(f"[{ts}] {msg}")
        else:
            print(json.dumps(logs_data, indent=2))
            
        print("\033[94m━" * 80 + "\033[0m\n")
    except Exception as e:
        print(f"\033[91m❌ Loglarni olishda xatolik yuz berdi: {e}\033[0m")

def main():
    parser = argparse.ArgumentParser(description="Render Resources Management REST API Helper CLI")
    subparsers = parser.add_subparsers(dest="command", help="Amallar")
    
    # list command
    subparsers.add_parser("list", help="Barcha Render xizmatlarini ko'rish")
    
    # status command
    status_parser = subparsers.add_parser("status", help="Bitta xizmat haqida ma'lumot olish")
    status_parser.add_argument("service_id", help="Render xizmati ID (Service ID)")
    
    # deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Xizmatni qayta deploy qilish")
    deploy_parser.add_argument("service_id", help="Render xizmati ID (Service ID)")
    deploy_parser.add_argument("--clear-cache", action="store_true", help="Keshni tozalab qayta deploy qilish")
    
    # logs command
    logs_parser = subparsers.add_parser("logs", help="Xizmat loglarini ko'rish")
    logs_parser.add_argument("service_id", help="Render xizmati ID (Service ID)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    if args.command == "list":
        list_services()
    elif args.command == "status":
        get_service_status(args.service_id)
    elif args.command == "deploy":
        trigger_deploy(args.service_id, args.clear_cache)
    elif args.command == "logs":
        fetch_logs(args.service_id)

if __name__ == "__main__":
    main()
