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

# The goal is to aggressively test business logic, RLS, auth failures, missing fields, big data
dirty_strings = [
    "A" * 50000,           # Huge string
    "; DROP TABLE users; --", # SQLi
    "<script>alert(1)</script>", # XSS
    "\x00\x01\x02",        # Null bytes and control chars
    "null",                # String "null"
    "{\"broken\": json",   # Broken JSON string
    "中文生僻字龘ꖎ",         # Unicode boundary
    "",                    # Empty string
    "00000000-0000-0000-0000-000000000000", # Empty UUID (might bypass format but fail FK/RLS)
    "99999999-9999-9999-9999-999999999999", # Non-existent UUID
]

dirty_numbers = [
    -9999999999999999,
    0,
    9999999999999999,
    1.5e-10,
    float('inf'),
    float('nan')
]

dirty_booleans = [True, False, None]

errors_collected = set()
status_codes_count = {}

def record_result(status_code, context, response_text=""):
    status_codes_count[status_code] = status_codes_count.get(status_code, 0) + 1
    if status_code >= 500:
        errors_collected.add(f"[{status_code}] {context} - {response_text[:150]}")

async def fetch_tools(client):
    try:
        r = await client.get("/api/mcp/tools")
        record_result(r.status_code, "GET /api/mcp/tools", r.text)
        if r.status_code == 200:
            return r.json().get("data", {}).get("tools", [])
    except Exception as e:
        errors_collected.add(f"Exception GET tools: {e}")
    return []

async def invoke_tool_chaos(client, tool):
    name = tool["name"]
    schema = tool.get("inputSchema", {}).get("properties", {})
    required = tool.get("inputSchema", {}).get("required", [])

    # Test 1: Missing all required fields
    try:
        r = await client.post(f"/api/mcp/tools/{name}/execute", json={"arguments": {}})
        record_result(r.status_code, f"Tool {name} (Missing Args)", r.text)
    except Exception as e:
        errors_collected.add(f"Exception Tool {name} (Missing Args): {e}")

    # Test 2: Fuzzing fields
    args = {}
    for k, v in schema.items():
        t = v.get("type", "string")
        if t == "string":
            args[k] = random.choice(dirty_strings)
        elif t in ["number", "integer"]:
            args[k] = random.choice(dirty_numbers)
        elif t == "boolean":
            args[k] = random.choice(dirty_booleans)
        elif t == "array":
            args[k] = [random.choice(dirty_strings), random.choice(dirty_numbers)]
        elif t == "object":
            args[k] = {"fuzzed": random.choice(dirty_strings)}
        else:
            args[k] = None

    try:
        # Increase timeout internally for client specifically on execute to see if it triggers internal timeout 
        r = await client.post(f"/api/mcp/tools/{name}/execute", json={"arguments": args}, timeout=70.0)
        record_result(r.status_code, f"Tool {name} (Fuzzed)", r.text)
    except httpx.ReadTimeout:
        errors_collected.add(f"Timeout (HTTP Client Level) - Tool {name}")
    except Exception as e:
        errors_collected.add(f"Exception Tool {name} (Fuzzed): {e}")

async def test_chat_edge_cases(client):
    print("      -> Testing Chat Edge Cases")
    try:
        # Missing parameters
        r1 = await client.post("/api/chat", json={})
        record_result(r1.status_code, "Chat (Empty JSON)", r1.text)
    except Exception as e:
        errors_collected.add(f"Exception Chat Empty JSON: {e}")

    
    # Huge context string
    payload = {
        "messages": [{"role": "user", "content": "A" * 200000}], 
        "model": "gpt-4o"
    }
    try:
        r2 = await client.post("/api/chat", json=payload)
        record_result(r2.status_code, "Chat (Huge Payload)", r2.text)
    except Exception as e:
        errors_collected.add(f"Exception Chat Huge Payload: {e}")

    # Invalid Model
    payload_invalid_model = {
        "messages": [{"role": "user", "content": "Hello"}], 
        "model": "non-existent-model-12345"
    }
    try:
        r3 = await client.post("/api/chat", json=payload_invalid_model)
        record_result(r3.status_code, "Chat (Invalid Model)", r3.text)
    except Exception as e:
        errors_collected.add(f"Exception Chat Invalid Model: {e}")

async def test_approvals_chaos(client):
    print("      -> Testing Approvals")
    endpoints = ["/api/approval/process", "/api/system/approvals/process"]
    for ep in endpoints:
        try:
            r1 = await client.post(ep, json={})
            record_result(r1.status_code, f"Approval {ep} (Empty JSON)", r1.text)
        except Exception as e:
            errors_collected.add(f"Exception Approval Empty JSON: {e}")
        
        # Test UUID validation / RLS mismatch
        try:
            r2 = await client.post(ep, json={
                "approval_id": "00000000-0000-0000-0000-000000000000",
                "action": "approve",
                "comments": "; DROP TABLE;"
            })
            record_result(r2.status_code, f"Approval {ep} (Fake UUID)", r2.text)
        except Exception as e:
            errors_collected.add(f"Exception Approval Fake UUID: {e}")

async def test_documents_chaos(client):
    print("      -> Testing Documents")
    # Invalid multipart
    try:
        r1 = await client.post("/api/documents/upload", json={"foo": "bar"}) # Calling multipart endpoint with JSON
        record_result(r1.status_code, "Docs (JSON instead of Multipart)", r1.text)
    except Exception as e:
        errors_collected.add(f"Exception Docs Multipart: {e}")


async def run_business_chaos():
    t0 = time.time()
    print("🚀 Starting Advanced Business Logic & RLS Chaos Test...")
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    
    # Increase base timeout to 75.0 to give the server's 60s timeout a chance to respond cleanly!
    async with httpx.AsyncClient(base_url=BASE_URL, headers=HEADERS, limits=limits, timeout=75.0) as client:
        try:
            print("[*] Checking Health...")
            r = await client.get("/health")
            print(f"    Health Status: {r.status_code}")
            
            print("[*] Fetching Tools...")
            tools = await fetch_tools(client)
            print(f"    Found {len(tools)} tools.")
            
            print("[*] Fuzzing Tools (Missing parameters, Bounds, UUIDs injection, Invalid Types)...")
            if tools:
                total_tools = len(tools)
                # Attack in smaller chunks to avoid client connection exhaustion locally
                for i in range(0, total_tools, 10):
                    batch = tools[i:i+10]
                    print(f"      -> Fuzzing tools {i} to {i+len(batch)}...")
                    tasks = [invoke_tool_chaos(client, t) for t in batch]
                    await asyncio.gather(*tasks)

            print("[*] Fuzzing Chat Endpoint (Huge payload, Missing args, Invalid model)...")
            await test_chat_edge_cases(client)
            
            print("[*] Fuzzing Approvals Endpoint (RLS checks, UUID formats)...")
            await test_approvals_chaos(client)

            print("[*] Fuzzing Documents Endpoint (Content-Type mismatch)...")
            await test_documents_chaos(client)
        except httpx.ReadTimeout:
            print("\n❌ CRITICAL: The entire test suite was aborted due to a global ReadTimeout.")
            errors_collected.add("Global HTTPX ReadTimeout")
        except Exception as e:
            print(f"\n❌ CRITICAL: Unexpected Global Error: {e}")
            errors_collected.add(f"Global Error: {e}")
        
    duration = time.time() - t0
    
    print("\n" + "="*50)
    print("📈 Advanced Chaos Test Results")
    print("="*50)
    print(f"Time Taken       : {duration:.2f} s")
    print("Status Codes Hit :")
    for code, count in sorted(status_codes_count.items()):
         print(f"   HTTP {code} : {count} times")
         
    if not errors_collected:
        print("\n✅ PERFECT! No unexpected 500 errors or exceptions detected!")
    else:
        print(f"\n❌ Found {len(errors_collected)} Server Errors / Exceptions:")
        for err in sorted(list(errors_collected)):
            print(f"  -> {err}")
            
if __name__ == "__main__":
    asyncio.run(run_business_chaos())
