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

        c.execute("""
        CREATE TABLE IF NOT EXISTS chat_participants (
            chatroom_id INTEGER,
            user_email TEXT,
            PRIMARY KEY (chatroom_id, user_email),
            FOREIGN KEY (chatroom_id) REFERENCES chatrooms(id)
        )
        """)

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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    q = f"%{query}%"

    c.execute("""
        SELECT m.id, m.chatroom_id, m.sender_email, m.message, m.created_at, c.name
        FROM messages m
        JOIN chatrooms c ON m.chatroom_id = c.id
        WHERE
            (
                -- public chats
                m.chatroom_id NOT IN (
                    SELECT chatroom_id FROM chat_participants
                )
                OR
                -- private chats user participates in
                m.chatroom_id IN (
                    SELECT chatroom_id FROM chat_participants
                    WHERE user_email = ?
                )
            )
        AND (
            m.sender_email LIKE ?
            OR m.message LIKE ?
            OR c.name LIKE ?
        )
        ORDER BY m.created_at DESC
    """, (user_email, q, q, q))

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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # existing private chat?
    c.execute("""
        SELECT chatroom_id
        FROM chat_participants
        GROUP BY chatroom_id
        HAVING COUNT(*) = 2
        AND SUM(user_email = ?) = 1
        AND SUM(user_email = ?) = 1
    """, (user1, user2))

    row = c.fetchone()
    if row:
        conn.close()
        return row[0]

    chat_name = f"Private: {user1} ↔ {user2}"

    c.execute(
        "INSERT INTO chatrooms (name, created_at) VALUES (?, ?)",
        (chat_name, datetime.now().isoformat())
    )
    chatroom_id = c.lastrowid

    c.executemany("""
        INSERT INTO chat_participants (chatroom_id, user_email)
        VALUES (?, ?)
    """, [
        (chatroom_id, user1),
        (chatroom_id, user2)
    ])

    conn.commit()
    conn.close()
    return chatroom_id



def user_can_access_chat(chatroom_id, user_email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Public chat
    c.execute("""
        SELECT 1 FROM chatrooms
        WHERE id = ?
        AND id NOT IN (SELECT chatroom_id FROM chat_participants)
    """, (chatroom_id,))
    if c.fetchone():
        conn.close()
        return True

    # Private chat
    c.execute("""
        SELECT 1 FROM chat_participants
        WHERE chatroom_id = ? AND user_email = ?
    """, (chatroom_id, user_email))

    allowed = c.fetchone() is not None
    conn.close()
    return allowed



def list_user_chats(user_email):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Public chats
    c.execute("""
        SELECT id, name
        FROM chatrooms
        WHERE id NOT IN (
            SELECT chatroom_id FROM chat_participants
        )
    """)
    public_rooms = c.fetchall()

    # Private chats user participates in
    c.execute("""
        SELECT c.id, c.name
        FROM chatrooms c
        JOIN chat_participants cp ON c.id = cp.chatroom_id
        WHERE cp.user_email = ?
    """, (user_email,))
    private_rooms = c.fetchall()

    conn.close()

    rooms = public_rooms + private_rooms
    return [{"id": r[0], "name": r[1]} for r in rooms]




    







