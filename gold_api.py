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
    """Lấy giá XAU/USD. Thử goldprice.org trước, fallback sang frankfurter."""

    # --- Source 1: goldprice.org ---
    url1 = "https://data-asg.goldprice.org/dbXRates/USD"
    headers1 = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://goldprice.org/",
        "Origin": "https://goldprice.org",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url1, headers=headers1, timeout=10)
            if resp.status_code == 200 and resp.text.strip():
                data = resp.json()
                item = data["items"][0]
                return {
                    "price_usd": round(item["xauPrice"], 2),
                    "change_pct": round(item["pcXau"], 2)
                }
            print(f"goldprice.org trả về status={resp.status_code}, body rỗng. Thử fallback...")
    except Exception as e:
        print(f"Lỗi goldprice.org: {e}. Thử fallback...")

    # --- Source 2: Frankfurter (tỷ giá EUR base, XAU/USD tính ngược) ---
    # Frankfurter không hỗ trợ XAU trực tiếp → dùng metals-api miễn phí (open)
    # Fallback: metals-live.p.rapidapi.com hoặc fawazahmed0/currency-api (GitHub)
    url2 = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/xau.json"
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url2, timeout=10)
            if resp.status_code == 200 and resp.text.strip():
                data = resp.json()
                # data["xau"]["usd"] = số USD cho 1 XAU
                price = data.get("xau", {}).get("usd")
                if price:
                    return {
                        "price_usd": round(float(price), 2),
                        "change_pct": 0.0   # fallback không có % thay đổi
                    }
    except Exception as e:
        print(f"Lỗi fallback XAU/USD API: {e}")

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
