import asyncio
from openai import AsyncOpenAI

async def do_embed(client, i):
    print(f"[{i}] Starting embedding...")
    try:
        response = await client.embeddings.create(
            input=f"Test message {i}",
            model="text-embedding-3-large",
            dimensions=1536
        )
        print(f"[{i}] SUCCESS!")
    except Exception as e:
        print(f"[{i}] FAILED: {type(e).__name__}: {e}")

async def main():
    api_key = "sk-t56vUMNcMqZFMVAWshYt4yxHcaV2uLpLjUbwlPxxy51z0wxJ"
    base_url = "https://poloai.top/v1"
    
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30)
    print(f"Testing 5 concurrent embedding calls to {base_url}...")
    
    tasks = [do_embed(client, i) for i in range(5)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
