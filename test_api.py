import asyncio
import httpx
from api_key_manager import get_valid_key

async def main():
    token = await get_valid_key()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as c:
        sjc = await c.get("https://api.vnappmob.com/api/v2/gold/sjc", headers=headers)
        doji = await c.get("https://api.vnappmob.com/api/v2/gold/doji", headers=headers)
        pnj = await c.get("https://api.vnappmob.com/api/v2/gold/pnj", headers=headers)
        print("SJC:", sjc.json())
        print("DOJI:", doji.json())
        print("PNJ:", pnj.json())

if __name__ == "__main__":
    asyncio.run(main())
