#!/usr/bin/env python3
"""
School21 Cluster Seat Occupancy Analyser

Tracks occupancy of all 125 seats in Tillakori cluster every 5 minutes,
saves data to SQLite database, and sends a daily report of the 10 least
occupied seats (or all empty seats if > 10) to Telegram at 10:00 AM.

Author: Antigravity AI
License: MIT
"""

import os
import sys
import time
import sqlite3
import logging
import argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
import requests

# ============================================================================
# Configuration
# ============================================================================

# Default settings
CLUSTER_ID = 36738  # Tillakori
CHECK_INTERVAL = 300  # 5 minutes (in seconds)
DATABASE_FILE = "seat_occupancy.db"
LOG_FILE = "seat_analyser.log"

def load_env():
    """Load environment variables from .env file"""
    env_file = '.env'
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        except Exception as e:
            print(f"Error loading .env file: {e}")

load_env()

SCHOOL21_USERNAME = os.environ.get("SCHOOL21_USERNAME", "")
SCHOOL21_PASSWORD = os.environ.get("SCHOOL21_PASSWORD", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ============================================================================
# Logging Setup
# ============================================================================

logger = logging.getLogger("SeatAnalyser")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ============================================================================
# Database Management
# ============================================================================

class DatabaseManager:
    """Manages SQLite database for seat occupancy logging"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seat_logs (
                    timestamp TEXT NOT NULL,
                    seat TEXT NOT NULL,
                    login TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seat_logs_timestamp ON seat_logs(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seat_logs_seat ON seat_logs(seat)")
            conn.commit()
            
    def log_occupied_seat(self, timestamp: datetime, seat: str, login: str):
        """Log an occupied seat state"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO seat_logs (timestamp, seat, login) VALUES (?, ?, ?)",
                (timestamp.isoformat(), seat.lower(), login)
            )
            conn.commit()

    def get_occupancy_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get aggregation stats for all seats in the database.
        Returns:
            Dict mapping seat name (e.g. 'a1') to stats dict:
            {
                'occupied_count': int,
                'unique_users': int,
                'users': List[str]
            }
        """
        stats = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Fetch total occupied count and unique user count per seat
            cursor.execute("""
                SELECT seat, COUNT(*) as occupied_count, COUNT(DISTINCT login) as unique_users
                FROM seat_logs
                GROUP BY seat
            """)
            rows = cursor.fetchall()
            
            # Fetch list of distinct users per seat
            for seat, occupied_count, unique_users in rows:
                cursor.execute("SELECT DISTINCT login FROM seat_logs WHERE seat = ?", (seat,))
                users = [r[0] for r in cursor.fetchall()]
                stats[seat] = {
                    'occupied_count': occupied_count,
                    'unique_users': unique_users,
                    'users': users
                }
        return stats

# ============================================================================
# School21 API Client
# ============================================================================

class School21API:
    """School21 API Client"""
    
    AUTH_URL = "https://auth.21-school.ru/auth/realms/EduPowerKeycloak/protocol/openid-connect/token"
    BASE_URL = "https://platform.21-school.ru/services/21-school/api/v1"
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        
    def authenticate(self) -> bool:
        """Authenticate and obtain access token"""
        data = {
            'client_id': 's21-open-api',
            'username': self.username,
            'password': self.password,
            'grant_type': 'password'
        }
        try:
            response = requests.post(
                self.AUTH_URL,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            response.raise_for_status()
            tokens = response.json()
            self._access_token = tokens.get('access_token')
            self._token_expires_at = time.time() + 300  # Expires in 5 minutes
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
            
    def _ensure_authenticated(self):
        """Ensure valid token exists"""
        if not self._access_token or time.time() >= self._token_expires_at:
            if not self.authenticate():
                raise Exception("Failed to authenticate with School21 API")
                
    def get_cluster_map(self, cluster_id: int) -> List[Dict[str, Any]]:
        """Get the full cluster map (limit=250 to get all seats)"""
        self._ensure_authenticated()
        try:
            url = f"{self.BASE_URL}/clusters/{cluster_id}/map"
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json'
            }
            params = {'limit': 250}
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get('clusterMap', [])
        except Exception as e:
            logger.error(f"Failed to fetch cluster map: {e}")
            return []

# ============================================================================
# Telegram Client
# ============================================================================

class TelegramBot:
    """Telegram Bot Messenger"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        
    def send_message(self, text: str) -> bool:
        """Send message to Telegram"""
        if not self.token or not self.chat_id:
            logger.warning("Telegram Bot Token or Chat ID not configured. Message: %s", text[:100])
            return False
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

# ============================================================================
# Report Generator
# ============================================================================

class ReportGenerator:
    """Generates the seat occupancy report"""
    
    def __init__(self, db: DatabaseManager, api: School21API):
        self.db = db
        self.api = api
        
    def generate_report_text(self, current_map: List[Dict[str, Any]]) -> str:
        """Analyze database logs and generate report text"""
        # Discover all seats from the current map to make sure we know the full layout
        all_seats = set()
        for wp in current_map:
            row = wp.get('row', '').lower()
            num = wp.get('number', 0)
            if row and num:
                all_seats.add(f"{row}{num}")
                
        if not all_seats:
            logger.error("Could not discover seats from cluster map.")
            return "⚠️ <b>Hisobot xatoligi:</b> Klaster xaritasi ma'lumotlarini olish imkoni bo'lmadi."
            
        # Get occupancy statistics from the database
        db_stats = self.db.get_occupancy_stats()
        
        # Merge discovered seats with database statistics
        merged_stats = []
        for seat in all_seats:
            stats = db_stats.get(seat, {'occupied_count': 0, 'unique_users': 0, 'users': []})
            merged_stats.append({
                'seat': seat.upper(),
                'occupied_count': stats['occupied_count'],
                'unique_users': stats['unique_users'],
                'users': stats['users']
            })
            
        # Sort seats:
        # 1. Least times occupied (occupied_count ascending)
        # 2. Fewest unique users (unique_users ascending)
        merged_stats.sort(key=lambda x: (x['occupied_count'], x['unique_users']))
        
        # Separate completely empty seats (occupied_count == 0)
        empty_seats = [s for s in merged_stats if s['occupied_count'] == 0]
        non_empty_seats = [s for s in merged_stats if s['occupied_count'] > 0]
        
        # Check condition: if more than 10 seats are completely empty, show all of them.
        # Otherwise, show the empty ones plus next least occupied ones to make it exactly 10.
        report_seats = []
        is_all_empty = False
        
        if len(empty_seats) > 10:
            report_seats = empty_seats
            is_all_empty = True
        else:
            report_seats = empty_seats + non_empty_seats[:(10 - len(empty_seats))]
            
        # Construct the message
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        msg = f"📊 <b>TILLAKORI KLASTERI: ENG KAM BAND BO'LGAN JOYLAR</b>\n"
        msg += f"📅 Hisobot vaqti: <code>{now_str}</code>\n"
        msg += f"🖥️ Jami joylar soni: <b>{len(all_seats)} ta</b>\n"
        msg += "─────────────────────────\n"
        
        if is_all_empty:
            msg += f"⚠️ <b>{len(empty_seats)} ta joy</b> umuman band qilinmagan (0% bandlik):\n\n"
            # Format list of empty seats neatly (10 per line for readability)
            seat_names = [s['seat'] for s in empty_seats]
            # Sort alphabetically
            seat_names.sort(key=lambda x: (x[0], int(x[1:])))
            for i in range(0, len(seat_names), 8):
                msg += " • " + ", ".join(seat_names[i:i+8]) + "\n"
        else:
            msg += "<b>Top 10 eng kam band bo'lgan joylar:</b>\n\n"
            for idx, item in enumerate(report_seats, 1):
                seat = item['seat']
                occupied_count = item['occupied_count']
                unique_users = item['unique_users']
                
                # Check interval is 5 minutes, so each count = 5 minutes
                occupied_minutes = occupied_count * 5
                if occupied_minutes >= 60:
                    time_str = f"{occupied_minutes / 60:.1f} soat"
                else:
                    time_str = f"{occupied_minutes} daqiqa"
                    
                users_preview = ""
                if unique_users > 0:
                    users_preview = f" (Odamlar: <code>{', '.join(item['users'][:3])}</code>"
                    if len(item['users']) > 3:
                        users_preview += "..."
                    users_preview += ")"
                
                msg += f"<b>{idx}. Joy {seat}</b>:\n"
                msg += f"   └ Band vaqt: <code>{time_str}</code> | Alohida odamlar: <b>{unique_users} ta</b>{users_preview}\n"
                
        msg += "─────────────────────────\n"
        msg += "<i>Statistika dastur fona ishga tushgan vaqtdan boshlab hisoblangan.</i>"
        return msg

# ============================================================================
# Main Loop and Logic
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="School21 Cluster Seat Occupancy Analyser")
    parser.add_argument('--test-report', action='store_true', help='Generate and send report immediately, then exit')
    args = parser.parse_args()

    logger.info("Initializing Seat Occupancy Analyser...")
    
    # Check credentials
    if not SCHOOL21_USERNAME:
        logger.error("SCHOOL21_USERNAME environment variable not set in .env file")
        sys.exit(1)
    if not SCHOOL21_PASSWORD:
        logger.error("SCHOOL21_PASSWORD environment variable not set in .env file")
        sys.exit(1)
        
    # Initialize clients
    db = DatabaseManager(DATABASE_FILE)
    api = School21API(SCHOOL21_USERNAME, SCHOOL21_PASSWORD)
    telegram = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    report_gen = ReportGenerator(db, api)
    
    # 1. Test report mode
    if args.test_report:
        logger.info("Test report mode active. Authenticating...")
        if not api.authenticate():
            logger.error("API authentication failed.")
            sys.exit(1)
            
        logger.info("Fetching cluster map...")
        current_map = api.get_cluster_map(CLUSTER_ID)
        if not current_map:
            logger.error("Could not fetch cluster map.")
            sys.exit(1)
            
        logger.info("Generating report...")
        report_text = report_gen.generate_report_text(current_map)
        
        logger.info("Sending report to Telegram...")
        if telegram.send_message(report_text):
            logger.info("Test report successfully sent to Telegram!")
            print("Test report successfully sent to Telegram!")
        else:
            logger.error("Failed to send test report to Telegram.")
            print("Failed to send test report.")
        sys.exit(0)
        
    # 2. Background daemon mode
    logger.info("Background daemon mode starting. Interval: %s seconds", CHECK_INTERVAL)
    logger.info("Report scheduled daily at 10:00 AM")
    
    # Test API connection first
    if not api.authenticate():
        logger.error("Initial API authentication failed. Please check credentials.")
        sys.exit(1)
        
    last_report_date = None
    
    while True:
        try:
            now = datetime.now()
            logger.info("Polling cluster map for occupancy...")
            
            # Fetch current map
            current_map = api.get_cluster_map(CLUSTER_ID)
            
            if current_map:
                logger.info("Successfully fetched cluster map. Logging occupied seats...")
                occupied_count = 0
                for wp in current_map:
                    row = wp.get('row', '')
                    num = wp.get('number', 0)
                    login = wp.get('login')
                    
                    if row and num and login:
                        seat_name = f"{row}{num}".lower()
                        db.log_occupied_seat(now, seat_name, login)
                        occupied_count += 1
                logger.info("Logged %d occupied seats out of %d total seats.", occupied_count, len(current_map))
            else:
                logger.warning("Failed to fetch map during this interval, will retry next time.")
                
            # Check if it is time to send the daily report (10:00 AM)
            # If the current hour is 10 and we haven't sent the report today
            if now.hour == 10 and last_report_date != now.date():
                logger.info("Time is 10:00 AM. Generating daily report...")
                # We need a fresh map to know the current seat layout
                if not current_map:
                    current_map = api.get_cluster_map(CLUSTER_ID)
                    
                if current_map:
                    report_text = report_gen.generate_report_text(current_map)
                    logger.info("Sending daily report to Telegram...")
                    if telegram.send_message(report_text):
                        logger.info("Daily report sent successfully.")
                        last_report_date = now.date()
                    else:
                        logger.error("Failed to send daily report to Telegram.")
                else:
                    logger.error("Could not generate daily report because cluster map is unavailable.")
                    
        except Exception as e:
            logger.exception("Error in main analysis loop: %s", e)
            
        # Sleep for the configured interval (e.g., 5 minutes)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
