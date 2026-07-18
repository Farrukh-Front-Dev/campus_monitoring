import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError as e:
    HAS_PSYCOPG2 = False
    logging.getLogger("DatabaseManager").error(f"Failed to import psycopg2: {e}")


logger = logging.getLogger("DatabaseManager")

class DatabaseManager:
    """Manages SQLite or PostgreSQL database for seat occupancy logging"""
    
    def __init__(self, db_path: str = "seat_occupancy.db"):
        self.db_path = db_path
        self.db_url = os.environ.get("DATABASE_URL", "")
        self.is_postgres = self.db_url.startswith(("postgresql://", "postgres://"))
        if self.is_postgres and self.db_url.startswith("postgres://"):
            self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
        self._init_db()
        
    def _get_connection(self):
        if self.is_postgres:
            if not HAS_PSYCOPG2:
                raise ImportError("PostgreSQL selected but psycopg2 is not installed.")
            return psycopg2.connect(self.db_url)
        else:
            return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize database schema"""
        conn = self._get_connection()
        try:
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
            cursor.close()
        except Exception as e:
            logger.error("Failed to initialize database: %s", e)
        finally:
            conn.close()
            
    def log_occupied_seat(self, timestamp: datetime, seat: str, login: str):
        """Log an occupied seat state"""
        query = "INSERT INTO seat_logs (timestamp, seat, login) VALUES (?, ?, ?)"
        if self.is_postgres:
            query = query.replace('?', '%s')
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (timestamp.isoformat(), seat.lower(), login))
            conn.commit()
            cursor.close()
        except Exception as e:
            logger.error("Failed to log occupied seat: %s", e)
        finally:
            conn.close()

    def prune_old_logs(self, keep_days: int = 30):
        """Delete logs older than keep_days"""
        threshold = (datetime.now() - timedelta(days=keep_days)).isoformat()
        query = "DELETE FROM seat_logs WHERE timestamp < ?"
        if self.is_postgres:
            query = query.replace('?', '%s')
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (threshold,))
            conn.commit()
            deleted = cursor.rowcount
            cursor.close()
            if deleted > 0:
                logger.info("Pruned %d logs older than %d days.", deleted, keep_days)
        except Exception as e:
            logger.error("Failed to prune old logs: %s", e)
        finally:
            conn.close()

    def get_occupancy_stats(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """
        Get aggregation stats for all seats in the database for the last N days.
        """
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
        
        if self.is_postgres:
            q1 = q1.replace('?', '%s')
            q2 = q2.replace('?', '%s')
            
        conn = self._get_connection()
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
        except Exception as e:
            logger.error("Failed to get occupancy stats: %s", e)
        finally:
            conn.close()
            
        return stats
