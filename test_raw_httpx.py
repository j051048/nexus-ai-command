import asyncio
import httpx
import json

async def test_raw_httpx(url, key):
    print(f"\n--- Raw HTTPX Test ---")
    print(f"Target: {url}")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    data = {
        "input": "test request",
        "model": "text-embedding-3-large"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            print("Sending POST request...")
            resp = await client.post(f"{url}/embeddings", headers=headers, json=data)
            print(f"Status: {resp.status_code}")
            print(f"Body: {resp.text[:200]}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

async def main():
    # Only test the one that gave 404 earlier
    await test_raw_httpx("https://poloai.top/v1", "sk-t56vUMNcMqZFMVAWshYt4yxHcaV2uLpLjUbwlPxxy51z0wxJ")
    # Also test the primary key on the working URL
    await test_raw_httpx("https://poloai.top/v1", "sk-VLZtlXUzE19XFwkt97Ac6dEeF2C6422c8b37342f91729323")

if __name__ == "__main__":
    asyncio.run(main())
