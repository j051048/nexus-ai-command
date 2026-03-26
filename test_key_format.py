import asyncio
import httpx

async def try_auth(name, key):
    url = "https://poloai.top/v1/embeddings"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = {"input": "test", "model": "text-embedding-3-large"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers=headers, json=data)
        print(f"[{name}] Key: {key[:10]}... Status: {resp.status_code} Body: {resp.text[:100]}")

async def main():
    key_with_sk = "sk-t56vUMNcMqZFMVAWshYt4yxHcaV2uLpLjUbwlPxxy51z0wxJ"
    key_no_sk = "t56vUMNcMqZFMVAWshYt4yxHcaV2uLpLjUbwlPxxy51z0wxJ"
    
    await try_auth("FORMAT WITH SK", key_with_sk)
    await try_auth("FORMAT NO SK", key_no_sk)

if __name__ == "__main__":
    asyncio.run(main())
