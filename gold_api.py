import httpx
from datetime import datetime
from api_key_manager import get_valid_key
from datetime import datetime, timedelta

_cache = {}  # {"SJC": {"data": ..., "time": datetime}, ...}
CACHE_TTL = timedelta(minutes=5)


async def get_sjc_price() -> dict:
    """Lấy giá vàng SJC từ VNAppMob."""
    # Trả về cache nếu còn mới
    if "SJC" in _cache and datetime.now() - _cache["SJC"]["time"] < CACHE_TTL:
        return _cache["SJC"]["data"]
    
    token = await get_valid_key()           # ← Tự động gia hạn nếu cần
    if not token:
        return {}
    url = "https://api.vnappmob.com/api/v2/gold/sjc"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10)
            data = resp.json()
            results = data.get("results", [])
            if results:
                item = results[0]  # Lấy loại vàng đầu tiên (SJC 1L)
                result = {
                    "buy": float(item.get("buy_1l", 0)),
                    "sell": float(item.get("sell_1l", 0)),
                    "name": item.get("name", "SJC"),
                    "all": results[:5]
                }
                _cache["SJC"] = {"data": result, "time": datetime.now()}
                return result
    except Exception as e:
        print(f"Lỗi SJC API: {e}")
    return {}

async def get_xauusd_price() -> dict:
    """Lấy giá XAU/USD từ GoldPrice.org (không cần API key)."""
    url = "https://data-asg.goldprice.org/dbXRates/USD"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10)
            data = resp.json()
            item = data["items"][0]
            return {
                "price_usd": round(item["xauPrice"], 2),
                "change_pct": round(item["pcXau"], 2)
            }
    except Exception as e:
        print(f"Lỗi XAU/USD API: {e}")
    return {}

def format_sjc_message(results: list) -> str:
    lines = [f"🇻🇳 *Giá Vàng SJC* — {datetime.now().strftime('%H:%M %d/%m/%Y')}\n"]
    for item in results:
        name = item.get("name", "SJC")
        buy  = f"{int(float(item.get('buy_1l', 0))):,}".replace(",", ".")
        sell = f"{int(float(item.get('sell_1l', 0))):,}".replace(",", ".")
        lines.append(f"• {name}\n  🟢 Mua: {buy} VNĐ | 🔴 Bán: {sell} VNĐ")
    return "\n".join(lines)

def format_xauusd_message(data: dict) -> str:
    price = data.get("price_usd", "N/A")
    change = data.get("change_pct", 0)
    arrow = "📈" if change >= 0 else "📉"
    return (
        f"🌍 *Giá Vàng Thế Giới (XAU/USD)*\n"
        f"  💰 Giá: *${price:,.2f}/oz*\n"
        f"  {arrow} Thay đổi 24h: *{change:+.2f}%*\n"
        f"  🕐 {datetime.now().strftime('%H:%M %d/%m/%Y')}"
    )
