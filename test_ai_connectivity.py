import asyncio
import httpx
import json

async def test_proxy():
    print("Testing connection to AI Proxy: https://proxy.flydao.top/v1/chat/completions")
    
    url = "https://proxy.flydao.top/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-invalid-key-for-test",
        "Origin": "https://nexus-ai-command.zeabur.app"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "ping"}],
        "stream": False
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 401:
                print("SUCCESS: Connection established (401 Unauthorized is expected without valid key).")
                print("这意味着网络是通的，只是需要配置正确的 API Key。")
            elif response.status_code == 200:
                print("SUCCESS: Connection established and request succeeded!")
            else:
                print("WARNING: Unexpected status code.")

    except Exception as e:
        print(f"ERROR: Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(test_proxy())
