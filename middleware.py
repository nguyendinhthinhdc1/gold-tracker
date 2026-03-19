import os
import sqlite3
from dotenv import load_dotenv
from database import get_all_users

load_dotenv()

# Comma-separated admin IDs from .env, e.g. ADMIN_IDS=123456789,987654321
ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

def is_banned(chat_id: int) -> bool:
    conn = sqlite3.connect("gold.db")
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0] == 1)

# Decorator dùng cho mọi handler
def check_banned(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if is_banned(update.effective_chat.id):
            await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này.")
            return
        return await func(update, context)
    return wrapper

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Lệnh này chỉ dành cho admin.")
            return
        return await func(update, context)
    return wrapper