import json
import base64
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

KEY_FILE         = Path("key.json")
REQUEST_KEY_URL  = os.getenv("REQUEST_KEY_URL", "https://api.vnappmob.com/api/request_api_key?scope=gold")
BUFFER_SECONDS   = 86400  # Gia hạn trước 1 ngày khi gần hết hạn

# Lock để tránh race condition khi nhiều coroutine cùng gọi
_refresh_lock = asyncio.Lock()


# ─────────────────────────────────────────────
# Giải mã JWT (không cần thư viện ngoài)
# ─────────────────────────────────────────────
def _decode_jwt_exp(token: str) -> int:
    """
    Giải mã phần payload của JWT để lấy trường 'exp' (Unix timestamp).
    Không cần verify signature vì chỉ cần đọc thời gian hết hạn.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return 0
        # Thêm padding Base64 nếu thiếu
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return int(payload.get("exp", 0))
    except Exception as e:
        logger.warning(f"Không giải mã được JWT: {e}")
        return 0


def _is_token_valid(token: str) -> bool:
    """Trả về True nếu token còn hạn (tính thêm buffer 1 ngày)."""
    exp = _decode_jwt_exp(token)
    if exp == 0:
        return False
    now = int(datetime.now(timezone.utc).timestamp())
    remaining = exp - now
    expires_at = datetime.fromtimestamp(exp).strftime("%H:%M %d/%m/%Y")
    logger.info(f"API key hết hạn lúc: {expires_at} | Còn {remaining // 3600} giờ")
    return remaining > BUFFER_SECONDS


# ─────────────────────────────────────────────
# Đọc / Ghi key từ file
# ─────────────────────────────────────────────
def _load_key_from_file() -> str | None:
    """Đọc API key đã lưu. Trả về None nếu file không tồn tại."""
    if not KEY_FILE.exists():
        return None
    try:
        data = json.loads(KEY_FILE.read_text(encoding="utf-8"))
        return data.get("api_key")
    except Exception as e:
        logger.warning(f"Lỗi đọc {KEY_FILE}: {e}")
        return None


def _save_key_to_file(token: str):
    """Lưu API key và thông tin hết hạn ra file."""
    exp = _decode_jwt_exp(token)
    expires_at = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S") if exp else "unknown"
    KEY_FILE.write_text(
        json.dumps({
            "api_key":    token,
            "expires_at": expires_at,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    logger.info(f"💾 Đã lưu API key mới → hết hạn lúc {expires_at}")


# ─────────────────────────────────────────────
# Request key mới từ VNAppMob
# ─────────────────────────────────────────────
async def _request_new_key(retries: int = 3) -> str | None:
    """Gọi API để lấy key mới. Tự động thử lại nếu thất bại."""
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(REQUEST_KEY_URL)
                resp.raise_for_status()
                data = resp.json()
                token = data.get("results")
                if token:
                    logger.info(f"✅ Lấy API key mới thành công (lần {attempt})")
                    return token
                logger.warning(f"Response không có 'results': {data}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code} khi lấy API key (lần {attempt})")
        except Exception as e:
            logger.error(f"Lỗi khi lấy API key (lần {attempt}): {e}")
        if attempt < retries:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s
    return None


# ─────────────────────────────────────────────
# Hàm chính — Dùng ở mọi nơi trong dự án
# ─────────────────────────────────────────────
async def get_valid_key() -> str | None:
    """
    Trả về API key còn hạn.
    Tự động request key mới nếu:
      - Chưa có key
      - Key sắp hết hạn (< 1 ngày)
      - Key đã hết hạn
    Thread-safe với asyncio.Lock.
    """
    async with _refresh_lock:
        # 1. Thử đọc key đã lưu
        token = _load_key_from_file()

        # 2. Kiểm tra hạn — nếu còn hạn thì dùng luôn
        if token and _is_token_valid(token):
            return token

        # 3. Key hết hạn hoặc chưa có → request mới
        reason = "chưa có key" if not token else "key hết/sắp hết hạn"
        logger.info(f"🔄 Đang lấy API key mới ({reason})...")
        new_token = await _request_new_key()

        if new_token:
            _save_key_to_file(new_token)
            return new_token

        # 4. Không lấy được key mới — dùng key cũ tạm thời nếu còn
        if token:
            logger.warning("⚠️ Không lấy được key mới, dùng tạm key cũ.")
            return token

        logger.error("❌ Hoàn toàn không có API key hợp lệ.")
        return None


# ─────────────────────────────────────────────
# Tiện ích: xem trạng thái key hiện tại
# ─────────────────────────────────────────────
def get_key_status() -> dict:
    """Trả về thông tin trạng thái key để hiển thị trong bot."""
    token = _load_key_from_file()
    if not token:
        return {"status": "❌ Chưa có key", "expires_at": None, "valid": False}
    exp = _decode_jwt_exp(token)
    now = int(datetime.now(timezone.utc).timestamp())
    remaining_h = max(0, (exp - now) // 3600)
    expires_at  = datetime.fromtimestamp(exp).strftime("%H:%M %d/%m/%Y") if exp else "?"
    valid       = _is_token_valid(token)
    return {
        "status":     "✅ Còn hạn" if valid else "🔴 Hết hạn",
        "expires_at": expires_at,
        "remaining":  f"{remaining_h} giờ",
        "valid":      valid,
    }
