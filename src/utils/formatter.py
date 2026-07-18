from datetime import datetime
from typing import Dict, Any, Optional

class UserDetailsFormatter:
    """Format user details for display in Telegram messages"""
    
    @staticmethod
    def format_short_message(login: str, event_type: str) -> str:
        """Format short notification message"""
        if event_type == "LOGIN":
            return f"<b>Login qilindi</b>\nNick: <code>{login}</code>"
        else:
            return f"<b>Logout qilindi</b>\nNick: <code>{login}</code>"
    
    @staticmethod
    def format_detailed_message(details: Dict[str, Any]) -> str:
        """Format detailed user information"""
        msg = f"<b>Login:</b> <code>{details.get('login', 'N/A')}</code>\n"
        msg += f"<b>Vaqt:</b> {details.get('timestamp', 'N/A')}\n"
        msg += "─────────────────────────\n"
        
        msg += f"<b>Sinf:</b> {details.get('class', 'N/A')}\n"
        msg += f"<b>Level:</b> {details.get('level', 'N/A')} | <b>XP:</b> {details.get('xp', 'N/A')}\n"
        
        if details.get('coalition'):
            msg += f"<b>Tribe:</b> {details['coalition']}\n"
        
        if details.get('weekly_hours') is not None:
            msg += f"<b>Haftalik logtime:</b> {details['weekly_hours']} soat\n"
        
        if 'prp' in details or 'coins' in details:
            msg += "─────────────────────────\n"
            msg += f"<b>PRP:</b> {details.get('prp', 0)} | <b>Coins:</b> {details.get('coins', 0)}"
        
        return msg
