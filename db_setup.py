import sqlite3
from datetime import datetime

DB_PATH = "smartcycle.db"

def create_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # USERS TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            phone TEXT,
            avatar_url TEXT,
            oauth_provider TEXT,
            oauth_id TEXT UNIQUE,
            user_type TEXT,
            location TEXT,
            created_at TEXT,
            last_login TEXT
        )
    """)

    # ITEMS TABLE
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            data_json TEXT,
            created_at TEXT
        )
    """)
    

if __name__ == "__main__":
    create_tables()
    print("Created smartcycle.db with users and items tables.")
