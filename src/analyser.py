import logging
from datetime import datetime
from typing import Dict, Any, List
from src.database import DatabaseManager
from src.api.school21 import School21API

logger = logging.getLogger("ReportGenerator")

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
            
        # Get occupancy statistics from the database (7 days)
        db_stats = self.db.get_occupancy_stats(days=7)
        
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
        msg += "<i>Statistika dastur fonda ishga tushgan vaqtdan boshlab hisoblangan.</i>"
        return msg
