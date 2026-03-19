import os
import sqlite3
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

DB_FILE = os.getenv("DB_FILE", "gold.db")

# Admin IDs loaded from .env (comma-separated)
_raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set(
    int(x.strip()) for x in _raw_admin_ids.split(",") if x.strip().isdigit()
)

def is_user_banned(chat_id: int) -> bool:
    """Return True if the given chat_id is banned."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0])

def check_banned(func):
    """Decorator: block banned users from using a command."""
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        chat_id = update.effective_user.id
        if is_user_banned(chat_id):
            await update.message.reply_text("⛔ Bạn đã bị cấm sử dụng bot này.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def admin_only(func):
    """Decorator: restrict a command to admin users only."""
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        chat_id = update.effective_user.id
        if chat_id not in ADMIN_IDS:
            await update.message.reply_text("🚫 Lệnh này chỉ dành cho admin.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Bảng lịch sử giá vàng
    c.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,          -- 'SJC' hoặc 'XAU_USD'
            buy_price REAL,
            sell_price REAL,
            timestamp TEXT
        )
    """)
    # Bảng cảnh báo ngưỡng của từng user
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            source TEXT,          -- 'SJC' hoặc 'XAU_USD'
            alert_type TEXT,      -- 'above' hoặc 'below'
            threshold REAL,
            triggered INTEGER DEFAULT 0
        )
    """)
    # Bảng quản lý người dùng
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            joined_at   TEXT,
            is_banned   INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def save_price(source: str, buy: float, sell: float):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO price_history (source, buy_price, sell_price, timestamp) VALUES (?, ?, ?, ?)",
        (source, buy, sell, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_history(source: str, limit: int = 24):
    """Lấy lịch sử giá theo nguồn, mặc định 24 bản ghi gần nhất."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT buy_price, sell_price, timestamp FROM price_history WHERE source=? ORDER BY id DESC LIMIT ?",
        (source, limit)
    )
    rows = c.fetchall()
    conn.close()
    return rows[::-1]  # Đảo ngược để tăng dần theo thời gian

def add_alert(chat_id: int, source: str, alert_type: str, threshold: float):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO alerts (chat_id, source, alert_type, threshold) VALUES (?, ?, ?, ?)",
        (chat_id, source, alert_type, threshold)
    )
    conn.commit()
    conn.close()

def get_alerts(chat_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, source, alert_type, threshold FROM alerts WHERE chat_id=? AND triggered=0", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_active_alerts():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, chat_id, source, alert_type, threshold FROM alerts WHERE triggered=0")
    rows = c.fetchall()
    conn.close()
    return rows

def mark_alert_triggered(alert_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE alerts SET triggered=1 WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()

def delete_alert(alert_id: int, chat_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM alerts WHERE id=? AND chat_id=?", (alert_id, chat_id))
    conn.commit()
    conn.close()

def register_user(chat_id: int, username: str, full_name: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO users (chat_id, username, full_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (chat_id, username, full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_all_users() -> list:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT chat_id, username, full_name, joined_at FROM users WHERE is_banned=0")
    rows = c.fetchall()
    conn.close()
    return rows

def ban_user(chat_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()
