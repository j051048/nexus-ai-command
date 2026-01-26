import json
import httpx
from typing import Optional, Dict
from app.core.config import settings

class AIService:
    @staticmethod
    async def call_llm(prompt: str, system_prompt: str = "You are a helpful enterprise AI assistant.") -> str:
        """
        Call OpenAI-compatible LLM
        """
        if not settings.OPENAI_API_KEY:
            # Fallback or Mock for local development without key
            return "AI Analysis: (API Key missing) Request looks standard. Proceed with caution."

        url = f"{settings.AI_BASE_URL}/chat/completions" if settings.AI_BASE_URL else "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
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
                response.raise_for_status()
                data = response.json()
                return data['choices'][0]['message']['content']
        except Exception as e:
            print(f"AI Service Error: {e}")
            return f"AI Analysis Error: {str(e)}"

    @staticmethod
    async def analyze_approval(request_type: str, description: str, amount: float) -> Dict:
        """
        Specific logic for analyzing approvals using LLM
        """
        system_prompt = """
        You are the 'Project Nexus' Enterprise Architect. 
        Your task is to analyze employee expenditure and leave requests.
        
        Decision categories:
        - auto_approved: If the request is small, reasonable, and follows standard company efficiency policies.
        - manual_review_required: If the amount is unusually large, the reason is vague, or there is a potential risk.
        - rejected: Only if the request clearly violates common sense or company policy (e.g., negative amounts, offensive content).
        
        Return your answer ONLY as a JSON string with two keys:
        - "decision": "auto_approved" | "manual_review_required" | "rejected"
        - "reasoning": A 1-sentence explanation of your choice in Chinese.
        """
        
        user_prompt = f"Request Type: {request_type}\nDescription: {description}\nAmount: {amount}"
        
        ai_response = await AIService.call_llm(user_prompt, system_prompt)
        
        try:
            # Attempt to strip markdown if LLM includes them
            clean_json = ai_response.strip().replace('```json', '').replace('```', '')
            return json.loads(clean_json)
        except:
            # Fallback logic if AI fails to return valid JSON
            return {
                "decision": "manual_review_required",
                "reasoning": f"AI Analysis (Fallback): {ai_response[:100]}..."
            }
