import asyncio
from openai import AsyncOpenAI
import os

async def main():
    api_key = "sk-t56vUMNcMqZFMVAWshYt4yxHcaV2uLpLjUbwlPxxy51z0wxJ"
    base_url = "https://poloai.top/v1"
    
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    print(f"Testing real embedding call to {base_url}...")
    
    try:
        response = await client.embeddings.create(
            input="Hello world",
            model="text-embedding-3-large",
            dimensions=1536
        )
        print("SUCCESS! Got embedding.")
        print(f"Dim: {len(response.data[0].embedding)}")
    except Exception as e:
        print(f"FAILED with dimensions=1536: {type(e).__name__}: {e}")
        
        try:
            print("Retrying without dimensions parameter...")
            response = await client.embeddings.create(
                input="Hello world",
                model="text-embedding-3-large"
            )
            print("SUCCESS without dimensions!")
        except Exception as e2:
            print(f"FAILED again: {e2}")

if __name__ == "__main__":
    asyncio.run(main())
