import asyncio
import httpx

async def test_supabase():
    url = "https://hztpazmuejgbtixihcgj.supabase.co/rest/v1/conversation_memories?select=*"
    headers = {
        "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh6dHBhem11ZWpnYnRpeGloY2dqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTMzMjU4OSwiZXhwIjoyMDg0OTA4NTg5fQ.bnHYt14D7Ee9XrzAAwYtY5C4-FFREpcQ4mvEuon5vco",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh6dHBhem11ZWpnYnRpeGloY2dqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTMzMjU4OSwiZXhwIjoyMDg0OTA4NTg5fQ.bnHYt14D7Ee9XrzAAwYtY5C4-FFREpcQ4mvEuon5vco"
    }
    
    print(f"Testing Supabase REST API...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers)
            print(f"Status: {resp.status_code}")
            print(f"Data: {resp.text[:200]}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_supabase())
