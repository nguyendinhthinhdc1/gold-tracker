import asyncio
from gold_api import get_sjc_price, format_sjc_message

async def main():
    data = await get_sjc_price()
    if data:
        print(format_sjc_message(data["all"]))
    else:
        print("No data received.")

if __name__ == "__main__":
    asyncio.run(main())
