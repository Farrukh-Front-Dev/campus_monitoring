import os
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError as e:
    HAS_PSYCOPG2 = False
    logging.getLogger("J3Monitor").error(f"Failed to import psycopg2: {e}")


from src.api.school21 import School21API
from src.api.telegram import TelegramBot
from src.config import Config
from src.utils.formatter import UserDetailsFormatter


class UserDetailsFetcher:
    """Fetch and aggregate user details from API"""
    
    def __init__(self, api: School21API):
        self.api = api
    
    def fetch(self, login: str) -> Dict[str, Any]:
        """Fetch complete user details"""
        details = {
            'login': login,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Basic info
        info = self.api.get_participant_info(login)
        if info:
            details['class'] = info.get('className', 'N/A')
            details['level'] = info.get('level', 'N/A')
            details['xp'] = info.get('expValue', 'N/A')
        
        # Logtime
        logtime = self.api.get_participant_logtime(login)
        if logtime:
            details['weekly_hours'] = self._parse_logtime(logtime)
        
        # Points
        points = self.api.get_participant_points(login)
        if points:
            details['prp'] = points.get('peerReviewPoints', 0)
            details['coins'] = points.get('coins', 0)
        
        # Coalition
        coalition = self.api.get_participant_coalition(login)
        if coalition:
            details['coalition'] = coalition.get('name', 'N/A')
        
        return details
    
    @staticmethod
    def _parse_logtime(logtime: Any) -> Optional[float]:
        """Parse logtime data"""
        if isinstance(logtime, dict):
            days = logtime.get('days', [])
            if days:
                total_minutes = sum(day.get('minutes', 0) for day in days)
                return round(total_minutes / 60, 1)
        elif isinstance(logtime, (int, float)):
            return round(logtime, 1)
        return None


class WorkplaceMonitor:
    """Monitor specific workplace for login/logout events"""
    
    def __init__(
        self,
        api: School21API,
        telegram: TelegramBot,
        config: Config,
        logger: logging.Logger
    ):
        self.api = api
        self.telegram = telegram
        self.config = config
        self.logger = logger
        self.formatter = UserDetailsFormatter()
        self.fetcher = UserDetailsFetcher(api)
        
        self.current_user: Optional[str] = None
        self.login_time: Optional[datetime] = None
    
    def get_current_user(self) -> Optional[str]:
        """Get current user at monitored workplace"""
        cluster_map = self.api.get_cluster_map(self.config.CLUSTER_ID)
        if not cluster_map:
            return None
        
        workplaces = cluster_map.get('clusterMap', [])
        for wp in workplaces:
            if (wp.get('row') == self.config.TARGET_ROW and 
                wp.get('number') == self.config.TARGET_NUMBER):
                return wp.get('login')
        
        return None
    
    def handle_login(self, login: str) -> None:
        """Handle user login event"""
        self.logger.info(f"Login detected: {login}")
        
        # Fetch and cache user details
        details = self.fetcher.fetch(login)
        self.telegram.user_data_cache[login] = details
        
        # Send notification
        message = self.formatter.format_short_message(login, "LOGIN")
        keyboard = TelegramBot.create_keyboard()
        self.telegram.send_message(message, keyboard)
        
        # Update state
        self.current_user = login
        self.login_time = datetime.now()
    
    def handle_logout(self, login: str) -> None:
        """Handle user logout event"""
        duration = (datetime.now() - self.login_time).total_seconds() / 60
        self.logger.info(f"Logout detected: {login} (duration: {duration:.1f} min)")
        
        # Send notification
        message = self.formatter.format_short_message(login, "LOGOUT")
        message += f"\n<b>Davomiyligi:</b> {duration:.1f} daqiqa"
        self.telegram.send_message(message)
        
        # Update state
        self.current_user = None
        self.login_time = None
    
    def run(self) -> None:
        """Run monitoring loop"""
        self.logger.info("Workplace monitor started")
        self.logger.info(f"Monitoring: Cluster {self.config.CLUSTER_ID}, "
                        f"{self.config.TARGET_ROW.upper()}{self.config.TARGET_NUMBER}")
        
        # Check initial state
        current_login = self.get_current_user()
        if current_login:
            self.handle_login(current_login)
        else:
            self.logger.info("Workplace is currently empty")
        
        # Monitoring loop
        try:
            while True:
                time.sleep(self.config.CHECK_INTERVAL)
                
                new_login = self.get_current_user()
                
                # Login event
                if new_login and new_login != self.current_user:
                    self.handle_login(new_login)
                
                # Logout event
                elif not new_login and self.current_user:
                    self.handle_logout(self.current_user)
        
        except KeyboardInterrupt:
            self.logger.info("Monitor stopped by user")


class MessageHandler:
    """Handle incoming Telegram messages"""
    
    def __init__(
        self,
        telegram: TelegramBot,
        monitor: WorkplaceMonitor,
        logger: logging.Logger
    ):
        self.telegram = telegram
        self.monitor = monitor
        self.logger = logger
        self.formatter = UserDetailsFormatter()
        self.fetcher = UserDetailsFetcher(monitor.api)
    
    def handle_batafsil_request(self) -> None:
        """Handle 'Batafsil' button press"""
        if not self.monitor.current_user:
            self.telegram.send_message("Hozirda bo'sh.")
            return
        
        login = self.monitor.current_user
        
        # Get details from cache or fetch new
        if login in self.telegram.user_data_cache:
            details = self.telegram.user_data_cache[login]
        else:
            details = self.fetcher.fetch(login)
        
        # Send detailed message
        message = self.formatter.format_detailed_message(details)
        self.telegram.send_message(message)
        
    def handle_kunlik_logtime_request(self) -> None:
        """Handle 'Kunlik logtime' button press"""
        if not self.monitor.current_user:
            self.telegram.send_message("Hozirda bo'sh.")
            return
        
        login = self.monitor.current_user
        logtime_data = self.monitor.api.get_participant_logtime(login)
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        total_minutes = 0
        
        if isinstance(logtime_data, dict):
            days = logtime_data.get('days', [])
        elif isinstance(logtime_data, list):
            days = logtime_data
        else:
            days = []
            
        found_today = False
        if isinstance(days, list):
            for day in days:
                if isinstance(day, dict) and day.get('date') == today_str:
                    total_minutes = day.get('minutes', 0)
                    found_today = True
                    break
            if not found_today and days:
                last_day = days[-1]
                if isinstance(last_day, dict):
                    total_minutes = last_day.get('minutes', 0)
                    today_str = last_day.get('date', today_str)
        elif isinstance(logtime_data, (int, float)):
            total_minutes = int(float(logtime_data) * 60)
            today_str = "bugun"

        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        message = f"👤 Foydalanuvchi: <code>{login}</code>\n"
        message += f"⏱️ <b>Bugungi logtime ({today_str}):</b> {hours} soat {minutes} daqiqa ({round(total_minutes/60, 1)} soat)"
        self.telegram.send_message(message)
    
    def _get_occupancy_stats(self, db_path: str, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """Get occupancy statistics from SQLite or PostgreSQL database for the last N days"""
        db_url = os.environ.get("DATABASE_URL", "")
        is_postgres = db_url.startswith(("postgresql://", "postgres://"))
        if is_postgres and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            
        threshold = (datetime.now() - timedelta(days=days)).isoformat()
        stats = {}
        
        q1 = """
            SELECT seat, COUNT(*) as occupied_count, COUNT(DISTINCT login) as unique_users
            FROM seat_logs
            WHERE timestamp >= ?
            GROUP BY seat
        """
        q2 = """
            SELECT DISTINCT login 
            FROM seat_logs 
            WHERE seat = ? AND timestamp >= ?
        """
        
        if is_postgres:
            q1 = q1.replace('?', '%s')
            q2 = q2.replace('?', '%s')
            
        try:
            if is_postgres:
                if not HAS_PSYCOPG2:
                    raise ImportError("PostgreSQL selected but psycopg2 is not installed.")
                conn = psycopg2.connect(db_url)
            else:
                conn = sqlite3.connect(db_path)
                
            try:
                cursor = conn.cursor()
                cursor.execute(q1, (threshold,))
                rows = cursor.fetchall()
                
                for seat, occupied_count, unique_users in rows:
                    cursor.execute(q2, (seat, threshold))
                    users = [r[0] for r in cursor.fetchall()]
                    stats[seat] = {
                        'occupied_count': occupied_count,
                        'unique_users': unique_users,
                        'users': users
                    }
                cursor.close()
            finally:
                conn.close()
        except Exception as e:
            self.logger.error(f"Failed to query seat occupancy database: {e}")
        return stats

    def handle_boshyolar_request(self) -> None:
        """Handle 'Bo'sh joylar' button press"""
        self.telegram.send_message("📊 Oxirgi 7 kunlik ma'lumotlar tahlil qilinmoqda, iltimos kuting...")
        
        db_path = self.monitor.config.DATABASE_FILE
        db_url = os.environ.get("DATABASE_URL", "")
        is_postgres = db_url.startswith(("postgresql://", "postgres://"))
        
        if not is_postgres and not os.path.exists(db_path):
            self.telegram.send_message("⚠️ <b>Xatolik:</b> Ma'lumotlar bazasi topilmadi. Tahlil yig'ilishi hali boshlanmagan bo'lishi mumkin.")
            return

        current_map_data = self.monitor.api.get_cluster_map(self.monitor.config.CLUSTER_ID)
        if not current_map_data:
            self.telegram.send_message("⚠️ <b>Xatolik:</b> Klaster xaritasi ma'lumotlarini yuklab bo'lmadi.")
            return
            
        workplaces = current_map_data.get('clusterMap', [])
        all_seats = set()
        for wp in workplaces:
            row = wp.get('row', '').lower()
            num = wp.get('number', 0)
            if row and num:
                all_seats.add(f"{row}{num}")
                
        if not all_seats:
            self.telegram.send_message("⚠️ <b>Xatolik:</b> Klasterda ish joylari topilmadi.")
            return
            
        db_stats = self._get_occupancy_stats(db_path, days=7)
        
        merged_stats = []
        for seat in all_seats:
            stats = db_stats.get(seat, {'occupied_count': 0, 'unique_users': 0, 'users': []})
            merged_stats.append({
                'seat': seat.upper(),
                'occupied_count': stats['occupied_count'],
                'unique_users': stats['unique_users'],
                'users': stats['users']
            })
            
        merged_stats.sort(key=lambda x: (x['occupied_count'], x['unique_users']))
        
        empty_seats = [s for s in merged_stats if s['occupied_count'] == 0]
        non_empty_seats = [s for s in merged_stats if s['occupied_count'] > 0]
        
        report_seats = []
        is_all_empty = False
        
        if len(empty_seats) > 10:
            report_seats = empty_seats
            is_all_empty = True
        else:
            report_seats = empty_seats + non_empty_seats[:(10 - len(empty_seats))]
            
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        msg = f"📊 <b>OXIRGI 7 KUNLIK TAHLIL (TILLAKORI KLASTERI)</b>\n"
        msg += f"📅 Hisobot vaqti: <code>{now_str}</code>\n"
        msg += f"🖥️ Jami joylar soni: <b>{len(all_seats)} ta</b>\n"
        msg += "─────────────────────────\n"
        
        if is_all_empty:
            msg += f"⚠️ <b>{len(empty_seats)} ta joy</b> oxirgi 1 haftada umuman band qilinmagan (0% bandlik):\n\n"
            seat_names = [s['seat'] for s in empty_seats]
            seat_names.sort(key=lambda x: (x[0], int(x[1:])))
            for i in range(0, len(seat_names), 8):
                msg += " • " + ", ".join(seat_names[i:i+8]) + "\n"
        else:
            msg += "<b>Top 10 eng kam band bo'lgan joylar (oxirgi 7 kun):</b>\n\n"
            for idx, item in enumerate(report_seats, 1):
                seat = item['seat']
                occupied_count = item['occupied_count']
                unique_users = item['unique_users']
                
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
        msg += "<i>Statistika seat_analyser fonda ishga tushgan vaqtdan boshlab hisoblanadi.</i>"
        
        self.telegram.send_message(msg)

    def run(self) -> None:
        """Run message handling loop"""
        offset = 0
        
        while True:
            try:
                updates = self.telegram.get_updates(offset)
                
                if updates and updates.get('result'):
                    for update in updates['result']:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            message = update['message']
                            text = message.get('text', '').strip()
                            
                            if text == 'Batafsil':
                                self.handle_batafsil_request()
                            elif text == 'Kunlik logtime':
                                self.handle_kunlik_logtime_request()
                            elif text == "Bo'sh joylar":
                                self.handle_boshyolar_request()
            
            except Exception as e:
                self.logger.error(f"Message handler error: {e}")
                time.sleep(5)
