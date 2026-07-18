import os
from dataclasses import dataclass
from typing import Dict

@dataclass
class Config:
    """Application configuration for campus monitoring"""
    SCHOOL21_USERNAME: str = ""
    SCHOOL21_PASSWORD: str = ""
    CLUSTER_ID: int = 36738  # Tillakori
    TARGET_ROW: str = "j"
    TARGET_NUMBER: int = 3
    CHECK_INTERVAL: int = 60  # seconds
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    LOG_FILE: str = "j3_monitor.log"
    LOG_LEVEL: int = 20  # INFO
    DATABASE_FILE: str = "seat_occupancy.db"

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables or .env file"""
        config = cls()
        env_vars = cls._load_env_file()
        
        config.TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', env_vars.get('TELEGRAM_BOT_TOKEN', ''))
        config.TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', env_vars.get('TELEGRAM_CHAT_ID', ''))
        config.SCHOOL21_USERNAME = os.environ.get('SCHOOL21_USERNAME', env_vars.get('SCHOOL21_USERNAME', ''))
        config.SCHOOL21_PASSWORD = os.environ.get('SCHOOL21_PASSWORD', env_vars.get('SCHOOL21_PASSWORD', ''))
        
        target_row = os.environ.get('TARGET_ROW', env_vars.get('TARGET_ROW', 'j'))
        config.TARGET_ROW = target_row.lower()
        
        target_number = os.environ.get('TARGET_NUMBER', env_vars.get('TARGET_NUMBER', '3'))
        config.TARGET_NUMBER = int(target_number)
        
        return config
    
    @staticmethod
    def _load_env_file() -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_vars = {}
        env_files = ['.env', '../.env', os.path.expanduser('~/.env')]
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
                    continue
                break
        return env_vars

# Global configuration for CLI tool
CLI_CONFIG = {
    'auth_url': "https://auth.21-school.ru/auth/realms/EduPowerKeycloak/protocol/openid-connect/token",
    'base_url': "https://platform.21-school.ru/services/21-school/api/v1",
    'username': "",
    'password': "",
    'timeout': 15,
    'max_retries': 3,
    'retry_delay': 2,
    'cluster_id': 36738,
}

def load_cli_config():
    """Load configuration for the CLI analytics tool"""
    env_vars = Config._load_env_file()
    CLI_CONFIG['username'] = os.environ.get('SCHOOL21_USERNAME', env_vars.get('SCHOOL21_USERNAME', ''))
    CLI_CONFIG['password'] = os.environ.get('SCHOOL21_PASSWORD', env_vars.get('SCHOOL21_PASSWORD', ''))
    
    # Expose them to os.environ for compatibility with other modules
    if CLI_CONFIG['username'] and not os.environ.get('SCHOOL21_USERNAME'):
        os.environ['SCHOOL21_USERNAME'] = CLI_CONFIG['username']
    if CLI_CONFIG['password'] and not os.environ.get('SCHOOL21_PASSWORD'):
        os.environ['SCHOOL21_PASSWORD'] = CLI_CONFIG['password']
