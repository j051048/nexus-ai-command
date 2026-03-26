import asyncio
import httpx
from openai import AsyncOpenAI

async def test_pair(name, base_url, api_key):
    print(f"\n--- Testing {name} ---")
    print(f"URL: {base_url}")
    print(f"Key: {api_key[:12]}...")
    
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15)
    try:
        # We'll use a cheap model to test token validity
        response = await client.embeddings.create(
            input="test",
            model="text-embedding-3-large"
        )
        print(f"RESULT: SUCCESS! Valid for embeddings.")
        return True
    except Exception as e:
        print(f"RESULT: FAILED: {e}")
        return False

async def main():
    pairs = [
        ("Primary Pair", "https://api.apiyi.com/v1", "sk-VLZtlXUzE19XFwkt97Ac6dEeF2C6422c8b37342f91729323"),
        ("Fallback Pair", "https://poloai.top/v1", "sk-t56vUMNcMqZFMVAWshYt4yxHcaV2uLpLjUbwlPxxy51z0wxJ"),
        ("Cross 1 (Primary Key on Fallback URL)", "https://poloai.top/v1", "sk-VLZtlXUzE19XFwkt97Ac6dEeF2C6422c8b37342f91729323"),
        ("Cross 2 (Fallback Key on Primary URL)", "https://api.apiyi.com/v1", "sk-t56vUMNcMqZFMVAWshYt4yxHcaV2uLpLjUbwlPxxy51z0wxJ"),
    ]
    
    for name, url, key in pairs:
        await test_pair(name, url, key)

if __name__ == "__main__":
    asyncio.run(main())
