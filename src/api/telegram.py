import logging
import requests
from typing import Optional, Dict, Any

class TelegramBot:
    """Telegram Bot Messenger Client"""
    
    def __init__(self, bot_token: str, chat_id: str, logger: Optional[logging.Logger] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logger or logging.getLogger("TelegramBot")
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.user_data_cache: Dict[str, Dict[str, Any]] = {}
        
    def send_message(self, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        """Send message to Telegram"""
        if not self.bot_token or not self.chat_id:
            self.logger.warning("Telegram Bot Token or Chat ID not configured.")
            return False
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }
            if reply_markup:
                data['reply_markup'] = reply_markup
            
            response = requests.post(url, json=data, timeout=15)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False
            
    def get_updates(self, offset: int = 0) -> Optional[Dict[str, Any]]:
        """Get bot updates"""
        if not self.bot_token:
            return None
        try:
            url = f"{self.base_url}/getUpdates"
            params = {'offset': offset, 'timeout': 30}
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get updates: {e}")
        return None
        
    @staticmethod
    def create_keyboard() -> Dict[str, Any]:
        """Create reply keyboard with 'Batafsil', 'Kunlik logtime', and 'Bo'sh joylar' buttons"""
        return {
            'keyboard': [[{'text': 'Batafsil'}, {'text': 'Kunlik logtime'}, {'text': "Bo'sh joylar"}]],
            'resize_keyboard': True,
            'one_time_keyboard': False
        }
