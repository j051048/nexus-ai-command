import asyncio
import httpx
import json

API_KEY = "sk-uWHkOjr0tku4Hc0rB7zYerY-Z0C_3ZfFClpg4la4lWPFmfVvCbBE68dp6XCFf6em"
BASE_URL = "https://aizhz.zeabur.app"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

async def run_normal_tests():
    print("🟢 Starting Normal Operations Test on Production...")
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, timeout=60.0) as client:
        # 1. Health Check
        print("\n1. Testing Health Endpoint...")
        try:
            r = await client.get("/health")
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text}")
        except Exception as e:
            print(f"Health Check Failed: {e}")

        # 2. Get Tools List
        print("\n2. Fetching MCP Tools List...")
        tools = []
        try:
            r = await client.get("/api/mcp/tools")
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                tools = data.get("data", {}).get("tools", [])
                print(f"Successfully retrieved {len(tools)} tools.")
            else:
                print(f"Response: {r.text[:200]}")
        except Exception as e:
            print(f"Fetch Tools Failed: {e}")

        # 3. Normal Tool Execution
        print("\n3. Testing Harmless Tool Executions...")
        test_tools = []
        for t in tools:
            name = t["name"]
            # Pick a few harmless read-only tools
            if name in ["query_company_info", "list_departments", "get_follow_ups"]:
                test_tools.append(t)
                
        if not test_tools and tools:
            # Fallback to the first query tool we find
            for t in tools:
                if "query" in t["name"] or "get" in t["name"] or "list" in t["name"]:
                    test_tools.append(t)
                    break

        for t in test_tools[:2]:  # Test max 2 
            name = t["name"]
            schema = t.get("inputSchema", {}).get("properties", {})
            required = t.get("inputSchema", {}).get("required", [])
            args = {}
            for k in required:
                t_type = schema.get(k, {}).get("type")
                if t_type == "string":
                    args[k] = "test" if k != "company_name" else "字节跳动"
                elif t_type in ["integer", "number"]:
                    args[k] = 10
            
            print(f"  -> Executing '{name}' with args: {args}")
            try:
                r = await client.post(f"/api/mcp/tools/{name}/execute", json={"arguments": args})
                print(f"     Status: {r.status_code}")
                try:
                    res_json = r.json()
                    success = res_json.get('success')
                    print(f"     Success flag: {success}")
                    if not success:
                        print(f"     Error object: {res_json.get('error')}")
                except:
                    print(f"     Response text: {r.text[:200]}")
            except Exception as e:
                print(f"     Tool execution failed: {e}")

        # 4. Chat Endpoint Test
        print("\n4. Testing Standard Chat API (LLM interaction / SSE)...")
        try:
            payload = {
                "messages": [{"role": "user", "content": "你好，请简单回复一句'服务正常'。不要包含其他内容。"}],
                "model": "gpt-4o-mini"
            }
            async with client.stream("POST", "/api/chat", json=payload) as response:
                print(f"Status: {response.status_code}")
                response_text = ""
                chunks_received = 0
                async for chunk in response.aiter_text():
                    chunks_received += 1
                    response_text += chunk
                print(f"Stream chunks received: {chunks_received}")
                print(f"Response Preview: {response_text[:400]}")
        except Exception as e:
            print(f"Chat failed: {e}")

if __name__ == '__main__':
    asyncio.run(run_normal_tests())
