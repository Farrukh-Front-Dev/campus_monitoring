#!/usr/bin/env python3
"""
School21 Cluster Seat Occupancy Analyser (Entry Point)
Imports database, API, bot clients and ReportGenerator from src package and runs.
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime

from src.config import Config
from src.database import DatabaseManager
from src.api.school21 import School21API
from src.api.telegram import TelegramBot
from src.analyser import ReportGenerator

# Setup logging
LOG_FILE = "seat_analyser.log"
logger = logging.getLogger("SeatAnalyser")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def main():
    parser = argparse.ArgumentParser(description="School21 Cluster Seat Occupancy Analyser")
    parser.add_argument('--test-report', action='store_true', help='Generate and send report immediately, then exit')
    args = parser.parse_args()

    logger.info("Initializing Seat Occupancy Analyser...")
    
    config = Config.from_env()
    
    if not config.SCHOOL21_USERNAME or not config.SCHOOL21_PASSWORD:
        logger.error("School21 credentials missing in .env file")
        sys.exit(1)
        
    db = DatabaseManager(config.DATABASE_FILE)
    api = School21API(config.SCHOOL21_USERNAME, config.SCHOOL21_PASSWORD, logger)
    telegram = TelegramBot(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, logger)
    report_gen = ReportGenerator(db, api)
    
    # 1. Test report mode
    if args.test_report:
        logger.info("Test report mode active. Authenticating...")
        if not api.authenticate():
            logger.error("API authentication failed.")
            sys.exit(1)
            
        logger.info("Fetching cluster map...")
        current_map_data = api.get_cluster_map(config.CLUSTER_ID)
        if not current_map_data:
            logger.error("Could not fetch cluster map.")
            sys.exit(1)
            
        current_map = current_map_data.get('clusterMap', [])
        logger.info("Generating report...")
        report_text = report_gen.generate_report_text(current_map)
        
        logger.info("Sending report to Telegram...")
        if telegram.send_message(report_text):
            logger.info("Test report successfully sent to Telegram!")
            print("Test report successfully sent to Telegram!")
        else:
            logger.error("Failed to send test report.")
            print("Failed to send test report.")
        sys.exit(0)
        
    # 2. Background daemon mode
    logger.info("Background daemon mode starting. Interval: %s seconds", config.CHECK_INTERVAL * 5)
    logger.info("Report scheduled daily at 10:00 AM")
    
    if not api.authenticate():
        logger.error("Initial API authentication failed. Please check credentials.")
        sys.exit(1)
        
    last_report_date = None
    
    while True:
        try:
            now = datetime.now()
            logger.info("Polling cluster map for occupancy...")
            current_map_data = api.get_cluster_map(config.CLUSTER_ID)
            
            if current_map_data:
                current_map = current_map_data.get('clusterMap', [])
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
                current_map = []
                
            # Check if it is time to send the daily report (10:00 AM)
            if now.hour == 10 and last_report_date != now.date():
                logger.info("Time is 10:00 AM. Generating daily report...")
                if not current_map:
                    current_map_data = api.get_cluster_map(config.CLUSTER_ID)
                    current_map = current_map_data.get('clusterMap', []) if current_map_data else []
                    
                if current_map:
                    report_text = report_gen.generate_report_text(current_map)
                    logger.info("Sending daily report to Telegram...")
                    if telegram.send_message(report_text):
                        logger.info("Daily report sent successfully. Pruning logs...")
                        last_report_date = now.date()
                        db.prune_old_logs(30)
                    else:
                        logger.error("Failed to send daily report to Telegram.")
                else:
                    logger.error("Could not generate daily report because cluster map is unavailable.")
                    
        except Exception as e:
            logger.exception("Error in main analysis loop: %s", e)
            
        time.sleep(config.CHECK_INTERVAL * 5)

if __name__ == "__main__":
    main()
