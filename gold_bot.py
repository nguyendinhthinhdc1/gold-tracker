import asyncio
import io
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

import google.generativeai as genai

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)

from database import (
    init_db, save_price, get_history,
    add_alert, get_alerts, get_all_active_alerts,
    mark_alert_triggered, delete_alert,
    register_user, get_all_users, ban_user,
    check_banned, admin_only
)
from gold_api import (
    get_sjc_price, get_doji_price, get_pnj_price, get_xauusd_price,
    format_sjc_message, format_doji_message, format_pnj_message, format_xauusd_message,
)

from api_key_manager import get_key_status


BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# === ConversationHandler states ===
WAIT_SOURCE, WAIT_TYPE, WAIT_THRESHOLD = range(3)

# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Tự động lưu user vào DB
    register_user(
        chat_id=user.id,
        username=user.username or "",
        full_name=user.full_name or ""
    )
    text = (
        "👋 *Bot Giá Vàng Pro* — Đầy đủ tính năng!\n\n"
        "📌 *Lệnh hỗ trợ:*\n"
        "• /giavang — Giá vàng SJC\n"
        "• /doji — Giá vàng DOJI\n"
        "• /pnj — Giá vàng PNJ\n"
        "• /xauusd — Giá vàng thế giới XAU/USD\n"
        "• /tatca — Xem tất cả: SJC + DOJI + PNJ + XAU/USD\n"
        "• /lichsu — Lịch sử giá (biểu đồ)\n"
        "• /canhbao — Đặt cảnh báo ngưỡng giá\n"
        "• /xemcanhbao — Danh sách cảnh báo đang chờ\n"
        "• /xoacanhbao — Xoá cảnh báo\n"
        "• /batdau — Nhận thông báo tự động mỗi giờ\n"
        "• /dungthongbao — Tắt thông báo tự động\n\n"
        "💬 Hoặc gõ tự nhiên: *'giá vàng hôm nay'*, *'vàng thế giới'*..."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

def save_all_sjc_types(sjc_data):
    if not sjc_data or "all" not in sjc_data or not sjc_data["all"]:
        return
    item = sjc_data["all"][0]
    types_mapping = [
        ("SJC", "buy_1l", "sell_1l"),
        ("SJC_5C", "buy_5c", "sell_5c"),
        ("SJC_1C", "buy_1c", "sell_1c"),
        ("SJC_NHAN1C", "buy_nhan1c", "sell_nhan1c"),
        ("SJC_NUT9999", "buy_nutrang_9999", "sell_nutrang_9999"),
        ("SJC_NUT99", "buy_nutrang_99", "sell_nutrang_99"),
        ("SJC_NUT75", "buy_nutrang_75", "sell_nutrang_75"),
    ]
    for source_key, key_buy, key_sell in types_mapping:
        if key_buy in item and key_sell in item:
            val_buy = item.get(key_buy, "0")
            val_sell = item.get(key_sell, "0")
            if val_buy and val_sell:
                try:
                    buy_f = float(val_buy)
                    sell_f = float(val_sell)
                    if buy_f > 0 and sell_f > 0:
                        save_price(source_key, buy_f, sell_f)
                except ValueError:
                    pass

# ============================================================
# Giá vàng SJC
# ============================================================
async def giavang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await get_sjc_price()
    if not data:
        await update.message.reply_text("❌ Không lấy được giá SJC, thử lại sau.")
        return
    save_all_sjc_types(data)
    await update.message.reply_text(format_sjc_message(data["all"]), parse_mode="Markdown")

# ============================================================
# Giá vàng DOJI
# ============================================================
async def doji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await get_doji_price()
    if not data:
        await update.message.reply_text("❌ Không lấy được giá DOJI, thử lại sau.")
        return
    save_price("DOJI", data["buy_hn"], data["sell_hn"])
    await update.message.reply_text(format_doji_message(data), parse_mode="Markdown")

# ============================================================
# Giá vàng PNJ
# ============================================================
async def pnj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await get_pnj_price()
    if not data:
        await update.message.reply_text("❌ Không lấy được giá PNJ, thử lại sau.")
        return
    save_price("PNJ", data["buy_hn"], data["sell_hn"])
    await update.message.reply_text(format_pnj_message(data), parse_mode="Markdown")

# ============================================================
# Giá vàng thế giới XAU/USD
# ============================================================
async def xauusd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await get_xauusd_price()
    if not data:
        await update.message.reply_text("❌ Không lấy được giá XAU/USD, thử lại sau.")
        return
    save_price("XAU_USD", data["price_usd"], data["price_usd"])
    await update.message.reply_text(format_xauusd_message(data), parse_mode="Markdown")

# ============================================================
# Cả hai loại giá
# ============================================================
async def tatca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sjc_data, doji_data, pnj_data, xau_data = await asyncio.gather(
        get_sjc_price(), get_doji_price(), get_pnj_price(), get_xauusd_price()
    )
    msg = ""
    if sjc_data:
        save_all_sjc_types(sjc_data)
        msg += format_sjc_message(sjc_data["all"]) + "\n\n"
    if doji_data:
        save_price("DOJI", doji_data["buy_hn"], doji_data["sell_hn"])
        msg += format_doji_message(doji_data) + "\n\n"
    if pnj_data:
        save_price("PNJ", pnj_data["buy_hn"], pnj_data["sell_hn"])
        msg += format_pnj_message(pnj_data) + "\n\n"
    if xau_data:
        save_price("XAU_USD", xau_data["price_usd"], xau_data["price_usd"])
        msg += format_xauusd_message(xau_data)
    if not msg:
        await update.message.reply_text("❌ Lỗi khi lấy dữ liệu.")
        return
    await update.message.reply_text(msg, parse_mode="Markdown")

# ============================================================
# Lịch sử giá — Vẽ biểu đồ
# ============================================================
async def lichsu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("SJC 1L", callback_data="history_SJC"),
            InlineKeyboardButton("SJC 5 chỉ", callback_data="history_SJC_5C")
        ],
        [
            InlineKeyboardButton("SJC 1 chỉ", callback_data="history_SJC_1C"),
            InlineKeyboardButton("Nhẫn 99,99", callback_data="history_SJC_NHAN1C")
        ],
        [
            InlineKeyboardButton("Nữ trang 99,99", callback_data="history_SJC_NUT9999"),
            InlineKeyboardButton("Nữ trang 99", callback_data="history_SJC_NUT99")
        ],
        [
            InlineKeyboardButton("Nữ trang 75", callback_data="history_SJC_NUT75"),
            InlineKeyboardButton("DOJI", callback_data="history_DOJI")
        ],
        [
            InlineKeyboardButton("PNJ", callback_data="history_PNJ"),
            InlineKeyboardButton("XAU/USD", callback_data="history_XAU_USD")
        ]
    ]
    await update.message.reply_text(
        "📈 Chọn loại giá vàng để xem lịch sử:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def lichsu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    source = query.data.replace("history_", "")
    rows = get_history(source, limit=24)

    if len(rows) < 2:
        await query.message.reply_text("⚠️ Chưa đủ dữ liệu lịch sử. Hãy dùng bot thêm một thời gian.")
        return

    gmt7 = timezone(timedelta(hours=7))
    times  = [
        datetime.strptime(r[2], "%Y-%m-%d %H:%M:%S")
        .replace(tzinfo=timezone.utc)
        .astimezone(gmt7)
        for r in rows
    ]
    sells  = [r[1] for r in rows]
    buys   = [r[0] for r in rows]

    label = "Triệu VNĐ" if source != "XAU_USD" else "USD/oz"
    titles = {
        "SJC": "SJC 1L (VNĐ)",
        "SJC_5C": "SJC 5 chỉ (VNĐ)",
        "SJC_1C": "SJC 1 chỉ (VNĐ)",
        "SJC_NHAN1C": "Nhẫn SJC 99,99 (VNĐ)",
        "SJC_NUT9999": "Vàng NT 99,99% (VNĐ)",
        "SJC_NUT99": "Vàng NT 99% (VNĐ)",
        "SJC_NUT75": "Vàng NT 75% (VNĐ)",
        "DOJI": "Giá Vàng DOJI (VNĐ)",
        "PNJ": "Giá Vàng PNJ (VNĐ)",
        "XAU_USD": "Giá XAU/USD ($)"
    }
    title = titles.get(source, f"Giá {source}")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(times, sells, label="Bán", color="#e74c3c", linewidth=2, marker="o", markersize=4)
    ax.plot(times, buys,  label="Mua", color="#2ecc71", linewidth=2, marker="o", markersize=4)
    ax.fill_between(times, buys, sells, alpha=0.1, color="gray")
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel(label)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M", tz=gmt7))
    plt.xticks(rotation=30, fontsize=8)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150)
    buf.seek(0)
    plt.close()
    await query.message.reply_photo(photo=buf, caption=f"📊 Lịch sử {title} — {len(rows)} bản ghi gần nhất")

# ============================================================
# Cảnh báo ngưỡng — ConversationHandler
# ============================================================
async def canhbao_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇻🇳 SJC (VNĐ)", callback_data="alert_src_SJC")],
        [InlineKeyboardButton("🌍 XAU/USD ($)", callback_data="alert_src_XAU_USD")],
    ]
    await update.message.reply_text(
        "🔔 *Đặt cảnh báo giá vàng*\nChọn nguồn giá:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return WAIT_SOURCE

async def canhbao_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["alert_source"] = query.data.replace("alert_src_", "")
    keyboard = [
        [InlineKeyboardButton("📈 Cảnh báo khi GIÁ TĂNG vượt ngưỡng", callback_data="alert_type_above")],
        [InlineKeyboardButton("📉 Cảnh báo khi GIÁ GIẢM dưới ngưỡng", callback_data="alert_type_below")],
    ]
    await query.message.reply_text("Chọn loại cảnh báo:", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAIT_TYPE

async def canhbao_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["alert_type"] = query.data.replace("alert_type_", "")
    source = context.user_data["alert_source"]
    unit = "VNĐ (ví dụ: 95000000)" if source == "SJC" else "USD (ví dụ: 3100)"
    await query.message.reply_text(f"💰 Nhập mức giá ngưỡng ({unit}):")
    return WAIT_THRESHOLD

async def canhbao_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        threshold = float(update.message.text.replace(",", "").replace(".", ""))
        chat_id   = update.effective_chat.id
        source    = context.user_data["alert_source"]
        atype     = context.user_data["alert_type"]
        add_alert(chat_id, source, atype, threshold)
        sign = "tăng vượt" if atype == "above" else "giảm dưới"
        unit = "VNĐ" if source == "SJC" else "USD"
        fmt  = f"{int(threshold):,}".replace(",", ".")
        await update.message.reply_text(
            f"✅ *Đã đặt cảnh báo!*\n"
            f"Sẽ thông báo khi giá *{source}* {sign} *{fmt} {unit}*",
            parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Giá trị không hợp lệ. Hãy nhập số (ví dụ: 95000000)")
    return ConversationHandler.END

async def canhbao_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Đã huỷ đặt cảnh báo.")
    return ConversationHandler.END

async def xem_canhbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_alerts(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("📭 Bạn chưa có cảnh báo nào đang chờ.")
        return
    lines = ["🔔 *Danh sách cảnh báo đang chờ:*\n"]
    for row in rows:
        aid, source, atype, thresh = row
        sign = "vượt trên" if atype == "above" else "dưới"
        unit = "VNĐ" if source == "SJC" else "USD"
        fmt  = f"{int(thresh):,}".replace(",", ".")
        lines.append(f"• ID `{aid}` | {source} {sign} *{fmt} {unit}*")
    lines.append("\nDùng /xoacanhbao <ID> để xoá.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def xoa_canhbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Cú pháp: /xoacanhbao <ID>\nVí dụ: /xoacanhbao 3")
        return
    try:
        alert_id = int(args[0])
        delete_alert(alert_id, update.effective_chat.id)
        await update.message.reply_text(f"🗑️ Đã xoá cảnh báo ID {alert_id}.")
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ.")

# ============================================================
# Thông báo tự động mỗi giờ
# ============================================================
async def gui_thongbao(context: ContextTypes.DEFAULT_TYPE):
    sjc_data, doji_data, pnj_data, xau_data = await asyncio.gather(
        get_sjc_price(), get_doji_price(), get_pnj_price(), get_xauusd_price()
    )
    msg = ""
    if sjc_data:
        save_all_sjc_types(sjc_data)
        msg += format_sjc_message(sjc_data["all"]) + "\n\n"
    if doji_data:
        save_price("DOJI", doji_data["buy_hn"], doji_data["sell_hn"])
        msg += format_doji_message(doji_data) + "\n\n"
    if pnj_data:
        save_price("PNJ", pnj_data["buy_hn"], pnj_data["sell_hn"])
        msg += format_pnj_message(pnj_data) + "\n\n"
    if xau_data:
        save_price("XAU_USD", xau_data["price_usd"], xau_data["price_usd"])
        msg += format_xauusd_message(xau_data)
    if msg:
        await context.bot.send_message(chat_id=context.job.chat_id, text=msg, parse_mode="Markdown")

async def batdau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if context.job_queue.get_jobs_by_name(f"notify_{chat_id}"):
        await update.message.reply_text("✅ Thông báo mỗi giờ đã đang chạy!")
        return
    context.job_queue.run_repeating(
        gui_thongbao, interval=3600, first=10,
        chat_id=chat_id, name=f"notify_{chat_id}"
    )
    await update.message.reply_text("🔔 Đã bật! Bạn sẽ nhận giá vàng *SJC + DOJI + PNJ + XAU/USD* mỗi giờ.", parse_mode="Markdown")

async def dungthongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name(f"notify_{chat_id}")
    if not jobs:
        await update.message.reply_text("ℹ️ Bạn chưa bật thông báo.")
        return
    for job in jobs:
        job.schedule_removal()
    await update.message.reply_text("🔕 Đã tắt thông báo tự động.")

# ============================================================
# Kiểm tra cảnh báo ngưỡng — Chạy mỗi 5 phút
# ============================================================
async def kiem_tra_canh_bao(context: ContextTypes.DEFAULT_TYPE):
    sjc_data, xau_data = await asyncio.gather(get_sjc_price(), get_xauusd_price())
    current = {
        "SJC":     sjc_data.get("sell", 0) if sjc_data else 0,
        "XAU_USD": xau_data.get("price_usd", 0) if xau_data else 0,
    }
    for aid, chat_id, source, atype, threshold in get_all_active_alerts():
        price = current.get(source, 0)
        if price == 0:
            continue
        triggered = (atype == "above" and price >= threshold) or \
                    (atype == "below" and price <= threshold)
        if triggered:
            sign = "vượt trên 📈" if atype == "above" else "giảm dưới 📉"
            unit = "VNĐ" if source == "SJC" else "USD"
            fmt_price = f"{int(price):,}".replace(",", ".")
            fmt_thresh = f"{int(threshold):,}".replace(",", ".")
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🚨 *CẢNH BÁO GIÁ VÀNG!*\n"
                    f"Giá *{source}* đã {sign} ngưỡng *{fmt_thresh} {unit}*\n"
                    f"💰 Giá hiện tại: *{fmt_price} {unit}*"
                ),
                parse_mode="Markdown"
            )
            mark_alert_triggered(aid)

# ============================================================
# Hỏi đáp tự nhiên bằng Google Gemini API
# ============================================================
async def hoi_dap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    # Send 'typing' action to show bot is processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        # Fetch latest prices for context
        sjc_data, doji_data, pnj_data, xau_data = await asyncio.gather(
            get_sjc_price(), get_doji_price(), get_pnj_price(), get_xauusd_price()
        )
        
        context_text = "Bạn là một trợ lý ảo chuyên cung cấp thông tin giá vàng tại Việt Nam và thế giới. Thông tin giá vàng MỚI NHẤT hiện tại:\n\n"
        if sjc_data and "all" in sjc_data:
            context_text += format_sjc_message(sjc_data["all"]) + "\n\n"
        if doji_data:
            context_text += format_doji_message(doji_data) + "\n\n"
        if pnj_data:
            context_text += format_pnj_message(pnj_data) + "\n\n"
        if xau_data:
            context_text += format_xauusd_message(xau_data) + "\n\n"
            
        system_instruction = (
            f"{context_text}"
            "Hãy trả lời câu hỏi của người dùng một cách ngắn gọn, súc tích, tự nhiên, thân thiện và chính xác dựa trên dữ liệu giá vàng ở trên. "
            "Trình bày dưới dạng văn bản thường (plain text), KHÔNG dùng các ký tự định dạng kiểu Markdown như dấu hoa thị (*) hay gạch dưới (_) để in đậm in nghiêng, vì có thể gây lỗi hiển thị Telegram (dùng icon/emoji thoải mái). "
            "Nếu người dùng hỏi thông tin không liên quan đến vàng, giá cả, ngoại tệ hay các chức năng của bạn, hãy từ chối lịch sự và nhắc họ rằng bạn là bot giá vàng."
        )
        
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_instruction)
        response = model.generate_content(user_text)
        
        await update.message.reply_text(response.text)
        
    except Exception as e:
        print(f"Lỗi khi gọi Gemini API: {e}")
        await update.message.reply_text("❌ Đã xảy ra lỗi khi kết nối với hệ thống AI. Vui lòng thử lại sau.")

# ============================================================
# Thông tin API key
# ============================================================
async def thongtin_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = get_key_status()
    msg = (
        f"🔑 *Thông tin API Key*\n\n"
        f"Trạng thái: {status['status']}\n"
        f"Hết hạn lúc: {status['expires_at'] or 'chưa có'}\n"
        f"Còn lại: {status['remaining'] if status['valid'] else '0 giờ'}\n\n"
        f"_Bot sẽ tự động gia hạn khi cần._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ============================================================
# Admin: Xem danh sách user
# ============================================================
@check_banned
async def danh_sach_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    msg = f"👥 *Danh sách user* — Tổng: {len(users)}\n\n"
    for uid, uname, name, joined in users:
        msg += f"• {name} (@{uname}) — ID: `{uid}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ============================================================
# Admin: Ban user
# ============================================================
@admin_only
async def ban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Cú pháp: /ban <ID>")
        return
    try:
        uid = int(context.args[0])
        ban_user(uid)
        await update.message.reply_text(f"⛔ Đã ban user ID `{uid}`.", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ ID không hợp lệ.")  

# ============================================================
# MAIN
# ============================================================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler cho cảnh báo
    conv = ConversationHandler(
        entry_points=[CommandHandler("canhbao", canhbao_start)],
        states={
            WAIT_SOURCE:    [CallbackQueryHandler(canhbao_source, pattern="^alert_src_")],
            WAIT_TYPE:      [CallbackQueryHandler(canhbao_type,   pattern="^alert_type_")],
            WAIT_THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, canhbao_threshold)],
        },
        fallbacks=[CommandHandler("cancel", canhbao_cancel)],
        per_message=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("giavang", giavang))
    app.add_handler(CommandHandler("doji", doji))
    app.add_handler(CommandHandler("pnj", pnj))
    app.add_handler(CommandHandler("xauusd", xauusd))
    app.add_handler(CommandHandler("tatca", tatca))
    app.add_handler(CommandHandler("lichsu", lichsu))
    app.add_handler(CommandHandler("batdau", batdau))
    app.add_handler(CommandHandler("dungthongbao", dungthongbao))
    app.add_handler(CommandHandler("xemcanhbao", xem_canhbao))
    app.add_handler(CommandHandler("xoacanhbao", xoa_canhbao))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(lichsu_callback, pattern="^history_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, hoi_dap))
    app.add_handler(CommandHandler("thongtinkey", thongtin_key))
    app.add_handler(CommandHandler("danhsachuser", danh_sach_user))
    app.add_handler(CommandHandler("ban", ban_user_cmd))

    # Job kiểm tra cảnh báo mỗi 5 phút
    app.job_queue.run_repeating(kiem_tra_canh_bao, interval=300, first=15)

    try:
        import sys
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("🤖 Gold Bot Pro đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
