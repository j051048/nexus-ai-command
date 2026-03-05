import asyncio
import json
import logging
import random
import time

import httpx

API_KEY = "sk-uWHkOjr0tku4Hc0rB7zYerY-Z0C_3ZfFClpg4la4lWPFmfVvCbBE68dp6XCFf6em"
BASE_URL = "https://aizhz.zeabur.app"

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def get_dirty_strings():
    return [
        "A" * 10000, 
        "; DROP TABLE users; --", 
        "<script>alert(1)</script>", 
        "\\x00", 
        "null", 
        "{\"broken\": json",
        "中文生僻字龘ꖎ",
        ""
    ]

errors_500 = []
rate_limits = 0

async def test_health(client):
    try:
        r = await client.get("/health")
        if r.status_code >= 500:
            errors_500.append(f"Health 500: {r.text[:100]}")
    except Exception as e:
        errors_500.append(f"Health exception: {e}")

async def test_get_tools(client):
    try:
        r = await client.get("/api/mcp/tools")
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            global rate_limits
            rate_limits += 1
            return None
        else:
            errors_500.append(f"Get tools failed {r.status_code}: {r.text[:100]}")
            return None
    except Exception as e:
        errors_500.append(f"Get tools exception: {e}")
        return None

async def invoke_tool(client, tool):
    global rate_limits
    name = tool["name"]
    schema = tool.get("inputSchema", {}).get("properties", {})
    
    args = {}
    for k, v in schema.items():
        t = v.get("type", "string")
        if t == "string":
            args[k] = random.choice(get_dirty_strings())
        elif t in ["number", "integer"]:
            args[k] = random.choice([-999999, 0, 999999999999, 1.5e-10])
        elif t == "boolean":
            args[k] = random.choice([True, False, None])
        else:
            args[k] = None

    payload = {"arguments": args}
    try:
        r = await client.post(f"/api/mcp/tools/{name}/execute", json=payload)
        
        if r.status_code >= 500:
            trace_id = r.headers.get("X-Trace-ID", "unknown")
            errors_500.append(f"Tool {name} 500 Error [{trace_id}]: {r.text[:150]}")
        elif r.status_code == 429:
            rate_limits += 1
    except Exception as e:
        errors_500.append(f"Tool {name} exception: {e}")

async def fuzz_tools(client, tools_data):
    if not tools_data or "data" not in tools_data or "tools" not in tools_data["data"]:
        return
    
    tools_list = tools_data["data"]["tools"]
    # Randomize and pick 30
    random.shuffle(tools_list)
    tasks = [invoke_tool(client, t) for t in tools_list[:30]]
    
    await asyncio.gather(*tasks, return_exceptions=True)

async def test_chat_sse(client):
    global rate_limits
    payload = {
        "messages": [{"role": "user", "content": "Chaos Test!"}],
        "model": "gpt-4o"
    }
    try:
        async with client.stream("POST", "/api/chat", json=payload) as response:
            if response.status_code >= 500:
                trace_id = response.headers.get("X-Trace-ID", "unknown")
                errors_500.append(f"Chat SSE 500 Error [{trace_id}]: STATUS {response.status_code} {response.read()[:50]}")
                return
            elif response.status_code == 429:
                rate_limits += 1
                return
                
            async for chunk in response.aiter_text():
                pass
    except Exception as e:
        errors_500.append(f"Chat SSE Exception: {str(e)}")

async def run_chaos():
    t0 = time.time()
    print("🚀 Starting API Chaos Test (Fuzzing & Stress)...")
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, limits=limits, timeout=12.0) as client:
        print("[*] Testing Health endpoint...")
        await test_health(client)

        print("[*] Fetching MCP Tools...")
        tools = await test_get_tools(client)
        if not tools:
            print("Failed to get tools list. Assuming backend is unreachable or returning errors.")

        print(f"[*] Fuzzing Tools (Injecting massive dirty data & Concurrent bursts)...")
        # Run 2 bursts of 30 concurrency to test Connection Pools & RLS
        if tools:
            await asyncio.gather(
                fuzz_tools(client, tools),
                fuzz_tools(client, tools),
                fuzz_tools(client, tools)
            )

        print("[*] Testing Chat SSE Streaming...")
        await test_chat_sse(client)
        
    duration = time.time() - t0
    
    print("\n" + "="*40)
    print("📈 Chaos Test Results")
    print("="*40)
    print(f"Time Taken  : {duration:.2f} s")
    print(f"Rate Limits (429) hit : {rate_limits}")
    if not errors_500:
        print("✅ No Server Errors (5xx) detected. System is resilient!")
    else:
        print(f"❌ Found {len(set(errors_500))} unique Server Errors:")
        for err in set(errors_500):
            print(f"  - {err}")

if __name__ == "__main__":
    asyncio.run(run_chaos())
