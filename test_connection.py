import asyncio
import httpx

async def test_connect(url):
    print(f"Testing connection to {url}...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            print(f"SUCCESS: {url} -> {resp.status_code}")
    except Exception as e:
        print(f"FAILED: {url} -> {type(e).__name__}: {e}")

async def main():
    urls = [
        "https://www.google.com",
        "https://api.apiyi.com/v1",
        "https://poloai.top/v1",
    ]
    for url in urls:
        await test_connect(url)

if __name__ == "__main__":
    asyncio.run(main())
