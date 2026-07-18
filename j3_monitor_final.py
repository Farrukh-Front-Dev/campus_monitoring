#!/usr/bin/env python3
"""
J3 Workplace Monitor Bot (Entry Point)
Imports logic from src package and runs.
"""

import sys
import logging
import threading
from src.config import Config
from src.api.school21 import School21API
from src.api.telegram import TelegramBot
from src.monitor import WorkplaceMonitor, MessageHandler
from src.web import run_flask_server

def setup_logging(config: Config) -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger('J3Monitor')
    logger.setLevel(config.LOG_LEVEL)
    
    file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
    file_handler.setLevel(config.LOG_LEVEL)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(config.LOG_LEVEL)
    
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def main() -> int:
    config = Config.from_env()
    logger = setup_logging(config)
    
    logger.info("="*70)
    logger.info("J3 Workplace Monitor Bot Starting")
    logger.info("="*70)
    
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.error("Telegram configuration missing in .env file")
        return 1
        
    api = School21API(config.SCHOOL21_USERNAME, config.SCHOOL21_PASSWORD, logger)
    if not api.authenticate():
        logger.error("Initial authentication failed")
        return 1
        
    telegram = TelegramBot(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, logger)
    telegram.send_message("J3 Monitoring Bot ishga tushdi!")
    
    logger.info("Starting Flask web server...")
    flask_thread = threading.Thread(target=run_flask_server, daemon=True, name="FlaskServer")
    flask_thread.start()
    logger.info("Flask server started")
    
    monitor = WorkplaceMonitor(api, telegram, config, logger)
    
    message_handler = MessageHandler(telegram, monitor, logger)
    handler_thread = threading.Thread(target=message_handler.run, daemon=True, name="MessageHandler")
    handler_thread.start()
    
    monitor.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
