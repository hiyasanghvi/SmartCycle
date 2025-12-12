# utils.py
import sqlite3
import json
from datetime import datetime
from pathlib import Path
import hashlib

DB_PATH = Path(__file__).parent / "smartcycle.db"

# ------------------- DB INIT -------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        location TEXT,
        created_at TEXT,
        last_login TEXT
    )
    """)

    # Items table
    c.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        data_json TEXT,
        created_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS chatrooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        created_at TEXT
    )
    """)

    # Messages table
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chatroom_id INTEGER NOT NULL,
        sender_email TEXT NOT NULL,
        message TEXT,
        created_at TEXT,
        FOREIGN KEY (chatroom_id) REFERENCES chatrooms(id)
    )
    """) 
    conn.commit()
    conn.close()

# ------------------- USER MANAGEMENT -------------------
def create_user(name, email, password_hash, location):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        created_at = datetime.now().isoformat()
        c.execute("""
        INSERT INTO users (name, email, password_hash, location, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (name, email, password_hash, location, created_at))
        conn.commit()
        conn.close()
        return True, "User created successfully!"
    except sqlite3.IntegrityError:
        return False, "Email already registered."

def get_user_by_email(email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    user = c.fetchone()
    conn.close()
    return user

def update_last_login(email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET last_login=? WHERE email=?", (datetime.now().isoformat(), email))
    conn.commit()
    conn.close()

# ------------------- PASSWORD HASH -------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ------------------- LISTINGS -------------------
def save_listing(user_email, item_data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO items (user_email, data_json, created_at)
        VALUES (?, ?, ?)
    """, (user_email, json.dumps(item_data), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def load_user_listings(user_email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT data_json FROM items WHERE user_email=? ORDER BY id DESC", (user_email,))
    rows = c.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]

# ------------------- CHATROOMS & MESSAGES -------------------
def create_chatroom(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute("INSERT INTO chatrooms (name, created_at) VALUES (?, ?)", (name, created_at))
    chatroom_id = c.lastrowid
    conn.commit()
    conn.close()
    return chatroom_id

def send_message(chatroom_id, sender_email, message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO messages (chatroom_id, sender_email, message, created_at)
        VALUES (?, ?, ?, ?)
    """, (chatroom_id, sender_email, message, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_chatroom_messages(chatroom_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT sender_email, message, created_at FROM messages WHERE chatroom_id=? ORDER BY id ASC", (chatroom_id,))
    rows = c.fetchall()
    conn.close()
    return [{"sender": r[0], "message": r[1], "time": r[2]} for r in rows]

def search_messages(query):
    """Search messages by user email, sender name, or message content"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query_param = f"%{query}%"
    c.execute("""
        SELECT m.id, m.chatroom_id, m.sender_email, m.message, m.created_at, c.name
        FROM messages m
        JOIN chatrooms c ON m.chatroom_id = c.id
        WHERE m.sender_email LIKE ?
        OR m.message LIKE ?
        OR c.name LIKE ?
        ORDER BY m.created_at DESC
    """, (query_param, query_param, query_param))
    rows = c.fetchall()
    conn.close()
    return [{"message_id": r[0], "chatroom_id": r[1], "sender": r[2], "message": r[3], "time": r[4], "chatroom_name": r[5]} for r in rows]
def create_private_chatroom_if_not_exists(user1, user2):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    room_name = f"Private: {user1} ↔ {user2}"

    # Check if exists
    c.execute("SELECT id FROM chatrooms WHERE name=?", (room_name,))
    row = c.fetchone()

    if row:
        conn.close()
        return row[0]

    # Create new private chatroom
    c.execute("INSERT INTO chatrooms (name) VALUES (?)", (room_name,))
    conn.commit()
    new_id = c.lastrowid

    conn.close()
    return new_id


def list_user_chats(user_email):
    """Returns all chatrooms where the user has sent or received messages."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT DISTINCT c.id, c.name, MAX(m.created_at)
        FROM messages m
        JOIN chatrooms c ON m.chatroom_id = c.id
        WHERE m.sender_email = ?
        GROUP BY c.id, c.name
        ORDER BY MAX(m.created_at) DESC
    """, (user_email,))

    rows = c.fetchall()
    conn.close()

    return [{"id": r[0], "name": r[1]} for r in rows]
