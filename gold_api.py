import httpx
from datetime import datetime, timedelta, timezone
from api_key_manager import get_valid_key

GMT7 = timezone(timedelta(hours=7))

_cache = {}  # {"SJC": {"data": ..., "time": datetime}, ...}
CACHE_TTL = timedelta(minutes=5)


def _fmt(value: float) -> str:
    """Format số thành chuỗi có dấu chấm ngăn cách hàng nghìn."""
    return f"{int(value):,}".replace(",", ".")


# ============================================================
# SJC
# ============================================================
async def get_sjc_price() -> dict:
    """Lấy giá vàng SJC từ VNAppMob."""
    if "SJC" in _cache and datetime.now() - _cache["SJC"]["time"] < CACHE_TTL:
        return _cache["SJC"]["data"]

    token = await get_valid_key()
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
                item = results[0]
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


# ============================================================
# DOJI
# ============================================================
async def get_doji_price() -> dict:
    """Lấy giá vàng DOJI từ VNAppMob."""
    if "DOJI" in _cache and datetime.now() - _cache["DOJI"]["time"] < CACHE_TTL:
        return _cache["DOJI"]["data"]

    token = await get_valid_key()
    if not token:
        return {}
    url = "https://api.vnappmob.com/api/v2/gold/doji"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10)
            data = resp.json()
            results = data.get("results", [])
            if results:
                item = results[0]
                result = {
                    "buy_hcm": float(item.get("buy_hcm", 0)),
                    "sell_hcm": float(item.get("sell_hcm", 0)),
                    "buy_hn": float(item.get("buy_hn", 0)),
                    "sell_hn": float(item.get("sell_hn", 0)),
                    "all": results[:5]
                }
                _cache["DOJI"] = {"data": result, "time": datetime.now()}
                return result
    except Exception as e:
        print(f"Lỗi DOJI API: {e}")
    return {}


# ============================================================
# PNJ
# ============================================================
async def get_pnj_price() -> dict:
    """Lấy giá vàng PNJ từ VNAppMob."""
    if "PNJ" in _cache and datetime.now() - _cache["PNJ"]["time"] < CACHE_TTL:
        return _cache["PNJ"]["data"]

    token = await get_valid_key()
    if not token:
        return {}
    url = "https://api.vnappmob.com/api/v2/gold/pnj"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10)
            data = resp.json()
            results = data.get("results", [])
            if results:
                item = results[0]
                result = {
                    "buy_hcm": float(item.get("buy_hcm", 0)),
                    "sell_hcm": float(item.get("sell_hcm", 0)),
                    "buy_hn": float(item.get("buy_hn", 0)),
                    "sell_hn": float(item.get("sell_hn", 0)),
                    "all": results[:5]
                }
                _cache["PNJ"] = {"data": result, "time": datetime.now()}
                return result
    except Exception as e:
        print(f"Lỗi PNJ API: {e}")
    return {}


# ============================================================
# XAU/USD
# ============================================================
async def get_xauusd_price() -> dict:
    """Lấy giá XAU/USD. Thử goldprice.org trước, fallback sang fawazahmed0."""

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

    # --- Source 2: fawazahmed0/currency-api (GitHub CDN) ---
    url2 = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/xau.json"
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url2, timeout=10)
            if resp.status_code == 200 and resp.text.strip():
                data = resp.json()
                price = data.get("xau", {}).get("usd")
                if price:
                    return {
                        "price_usd": round(float(price), 2),
                        "change_pct": 0.0
                    }
    except Exception as e:
        print(f"Lỗi fallback XAU/USD API: {e}")

    return {}


# ============================================================
# Formatters
# ============================================================
def format_sjc_message(results: list) -> str:
    lines = [f"🇻🇳 *Giá Vàng SJC* — {datetime.now(GMT7).strftime('%H:%M %d/%m/%Y')}"]
    
    types_mapping = [
        ("Vàng SJC 1L, 10L, 1KG", "buy_1l", "sell_1l"),
        ("Vàng SJC 5 chỉ", "buy_5c", "sell_5c"),
        ("Vàng SJC 1 chỉ, 2 chỉ, 5 phân", "buy_1c", "sell_1c"),
        ("Nhẫn SJC 99,99 1 chỉ, 2 chỉ, 5 chỉ", "buy_nhan1c", "sell_nhan1c"),
        ("Vàng nữ trang 99,99%", "buy_nutrang_9999", "sell_nutrang_9999"),
        ("Vàng nữ trang 99%", "buy_nutrang_99", "sell_nutrang_99"),
        ("Vàng nữ trang 75%", "buy_nutrang_75", "sell_nutrang_75"),
    ]

    for item in results:
        name = item.get("name", "SJC")
        lines.append(f"\n🏢 *{name}*")
        
        for type_name, key_buy, key_sell in types_mapping:
            if key_buy in item and key_sell in item:
                val_buy = item.get(key_buy, "0")
                val_sell = item.get(key_sell, "0")
                if val_buy and val_sell:
                    try:
                        buy  = _fmt(float(val_buy))
                        sell = _fmt(float(val_sell))
                        if buy != "0" and sell != "0":
                            lines.append(f"  • {type_name}\n    🟢 Mua: {buy} VNĐ | 🔴 Bán: {sell} VNĐ")
                    except ValueError:
                        pass

    return "\n".join(lines)


def format_doji_message(data: dict) -> str:
    ts = datetime.now(GMT7).strftime('%H:%M %d/%m/%Y')
    buy_hcm  = _fmt(data.get("buy_hcm", 0))
    sell_hcm = _fmt(data.get("sell_hcm", 0))
    buy_hn   = _fmt(data.get("buy_hn", 0))
    sell_hn  = _fmt(data.get("sell_hn", 0))
    return (
        f"💎 *Giá Vàng DOJI* — {ts}\n"
        f"• TP.HCM  🟢 Mua: {buy_hcm} VNĐ | 🔴 Bán: {sell_hcm} VNĐ\n"
        f"• Hà Nội  🟢 Mua: {buy_hn} VNĐ | 🔴 Bán: {sell_hn} VNĐ"
    )


def format_pnj_message(data: dict) -> str:
    ts = datetime.now(GMT7).strftime('%H:%M %d/%m/%Y')
    buy_hcm  = _fmt(data.get("buy_hcm", 0))
    sell_hcm = _fmt(data.get("sell_hcm", 0))
    buy_hn   = _fmt(data.get("buy_hn", 0))
    sell_hn  = _fmt(data.get("sell_hn", 0))
    return (
        f"💍 *Giá Vàng PNJ* — {ts}\n"
        f"• TP.HCM  🟢 Mua: {buy_hcm} VNĐ | 🔴 Bán: {sell_hcm} VNĐ\n"
        f"• Hà Nội  🟢 Mua: {buy_hn} VNĐ | 🔴 Bán: {sell_hn} VNĐ"
    )


def format_xauusd_message(data: dict) -> str:
    price = data.get("price_usd", "N/A")
    change = data.get("change_pct", 0)
    arrow = "📈" if change >= 0 else "📉"
    return (
        f"🌍 *Giá Vàng Thế Giới (XAU/USD)*\n"
        f"  💰 Giá: *${price:,.2f}/oz*\n"
        f"  {arrow} Thay đổi 24h: *{change:+.2f}%*\n"
        f"  🕐 {datetime.now(GMT7).strftime('%H:%M %d/%m/%Y')}"
    )
