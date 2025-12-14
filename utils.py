import sqlite3
import json
from datetime import datetime
from pathlib import Path
import hashlib

# Use a path relative to current file (works on Streamlit Cloud)
DB_PATH = Path(__file__).parent / "smartcycle.db"

# ------------------- DB INIT -------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
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

        # Chatrooms table
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

# ------------------- USER MANAGEMENT -------------------
def create_user(name, email, password_hash, location):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            created_at = datetime.now().isoformat()
            c.execute("""
                INSERT INTO users (name, email, password, location, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (name, email, password_hash, location, created_at))
        return True, "User created successfully!"
    except sqlite3.IntegrityError:
        return False, "Email already registered."

def get_user_by_email(email):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        return c.fetchone()

def update_last_login(email):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET last_login=? WHERE email=?", (datetime.now().isoformat(), email))
        conn.commit()

# ------------------- PASSWORD HASH -------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# ------------------- LISTINGS -------------------
def save_listing(user_email, item_data):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO items (user_email, data_json, created_at)
            VALUES (?, ?, ?)
        """, (user_email, json.dumps(item_data), datetime.now().isoformat()))

def load_user_listings(user_email):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT data_json FROM items WHERE user_email=? ORDER BY id DESC", (user_email,))
        rows = c.fetchall()
    return [json.loads(row[0]) for row in rows]

# ------------------- CHATROOMS & MESSAGES -------------------

def create_chatroom(name):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        created_at = datetime.now().isoformat()
        c.execute("INSERT INTO chatrooms (name, created_at) VALUES (?, ?)", (name, created_at))
        return c.lastrowid

def send_message(chatroom_id, sender_email, message):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO messages (chatroom_id, sender_email, message, created_at)
            VALUES (?, ?, ?, ?)
        """, (chatroom_id, sender_email, message, datetime.now().isoformat()))

def get_chatroom_messages(chatroom_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT sender_email, message, created_at FROM messages WHERE chatroom_id=? ORDER BY id ASC", (chatroom_id,))
        rows = c.fetchall()
    return [{"sender": r[0], "message": r[1], "time": r[2]} for r in rows]

def search_messages(query, user_email):
    """
    Search messages only in chatrooms the user has access to
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query_param = f"%{query}%"
    user_param = f"%{user_email}%"

    c.execute("""
        SELECT m.id, m.chatroom_id, m.sender_email, m.message, m.created_at, c.name
        FROM messages m
        JOIN chatrooms c ON m.chatroom_id = c.id
        WHERE
            (
                c.name NOT LIKE 'private:%'
                OR c.name LIKE ?
            )
            AND (
                m.sender_email LIKE ?
                OR m.message LIKE ?
                OR c.name LIKE ?
            )
        ORDER BY m.created_at DESC
    """, (user_param, query_param, query_param, query_param))

    rows = c.fetchall()
    conn.close()

    return [{
        "message_id": r[0],
        "chatroom_id": r[1],
        "sender": r[2],
        "message": r[3],
        "time": r[4],
        "chatroom_name": r[5]
    } for r in rows]

def get_or_create_private_chat(user1, user2):
    """Returns chatroom_id for a private chat between two users.
       If not exists, automatically creates one."""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    chat_name = f"private:{min(user1, user2)}:{max(user1, user2)}"

    # Check if chatroom exists
    c.execute("SELECT id FROM chatrooms WHERE name=?", (chat_name,))
    row = c.fetchone()

    if row:
        chatroom_id = row[0]
    else:
        # Create if not exists
        created_at = datetime.now().isoformat()
        c.execute("INSERT INTO chatrooms (name, created_at) VALUES (?, ?)", 
                  (chat_name, created_at))
        chatroom_id = c.lastrowid

    conn.commit()
    conn.close()
    return chatroom_id

def user_can_access_chat(chatroom_id, user_email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT name FROM chatrooms WHERE id=?", (chatroom_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return False

    name = row[0]

    if name.startswith("private:"):
        return user_email in name

    return True

def list_user_chats(user_email):
    """
    Returns chatrooms visible to a user.
    - Public chatrooms: visible to all
    - Private chatrooms: visible ONLY if user is a participant
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Public chatrooms
    c.execute("""
        SELECT id, name
        FROM chatrooms
        WHERE name NOT LIKE 'private:%'
    """)
    public_rooms = c.fetchall()

    # Private chatrooms where user is a participant
    c.execute("""
        SELECT id, name
        FROM chatrooms
        WHERE name LIKE 'private:%'
        AND name LIKE ?
    """, (f"%{user_email}%",))

    private_rooms = c.fetchall()

    conn.close()

    rooms = public_rooms + private_rooms

    return [{"id": r[0], "name": r[1]} for r in rooms]


    






