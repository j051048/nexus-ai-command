import json
import httpx
from typing import Optional, Dict
from app.core.config import settings

class AIService:
    @staticmethod
    async def call_llm(prompt: str, system_prompt: str = "You are a helpful enterprise AI assistant.") -> str:
        """
        Call LLM using raw HTTP calls (httpx) for maximum compatibility with proxy providers.
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            return "AI Analysis: (API Key missing) Standard fallback active."

        # Normalize Base URL
        base_url = settings.AI_BASE_URL if settings.AI_BASE_URL else "https://api.openai.com/v1"
        base_url = base_url.rstrip("/")
        url = f"{base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gemini-3-pro-preview", 
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=30.0)
                if response.status_code != 200:
                    return f"AI Error ({response.status_code}): {response.text[:200]}"
                
                data = response.json()
                return data['choices'][0]['message']['content']
        except Exception as e:
            print(f"AI Service HTTP Error: {e}")
            return f"AI Analysis Error: {str(e)}"

    @staticmethod
    async def analyze_approval(request_type: str, description: str, amount: float) -> Dict:
        """
        Analyze approvals using LLM.
        """
        system_prompt = """
        You are the 'Project Nexus' Enterprise Architect. 
        Analyze employee expenditure and leave requests.
        Return ONLY a JSON string with keys: "decision", "reasoning".
        """
        
        user_prompt = f"Type: {request_type}\nDesc: {description}\nAmt: {amount}"
        ai_response = await AIService.call_llm(user_prompt, system_prompt)
        
        try:
            clean_json = ai_response.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            return json.loads(clean_json)
        except:
            return {
                "decision": "manual_review_required",
                "reasoning": f"AI Parsing failed: {ai_response[:50]}"
            }
