"""
AI Service - LLM Integration with proper error handling

P2 Fixes Applied:
- Replaced bare except with proper exception handling
- Added structured logging
- Added timeout configuration
- Improved error messages
"""

import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_TIMEOUT = 120.0
MAX_RETRIES = 2


class AIService:
    @staticmethod
    async def call_llm(
        prompt: str, system_prompt: str = "You are a helpful enterprise AI assistant."
    ) -> str:
        """
        Call LLM using raw HTTP calls (httpx) for maximum compatibility with proxy providers.

        P2 Fix: Added proper error handling, timeout, and retry logic.
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            logger.warning("AI Service called without API key configured")
            return "AI Analysis: (API Key missing) Standard fallback active."

        # Normalize Base URL
        base_url = (
            settings.AI_BASE_URL
            if settings.AI_BASE_URL
            else "https://api.openai.com/v1"
        )
        base_url = base_url.rstrip("/")
        url = f"{base_url}/chat/completions"

        # #25: 在 LLM API 调用中传播 trace_id
        from app.core.trace_context import get_request_id, get_trace_id

        trace_id = get_trace_id()
        request_id = get_request_id()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if trace_id:
            headers["X-Trace-ID"] = trace_id
        if request_id:
            headers["X-Request-ID"] = request_id

        payload = {
            "model": (
                getattr(settings, "AI_STRONG_MODEL", "") or settings.AI_DEFAULT_MODEL
                if hasattr(settings, "AI_DEFAULT_MODEL")
                else "gpt-4o"
            ),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code != 200:
                        logger.warning(
                            f"AI Service error response: {response.status_code}"
                        )
                        return (
                            f"AI Error ({response.status_code}): {response.text[:200]}"
                        )

                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"AI Service timeout (attempt {attempt + 1}/{MAX_RETRIES + 1})"
                )
                if attempt < MAX_RETRIES:
                    continue
            except httpx.RequestError as e:
                last_error = e
                logger.error(f"AI Service HTTP error: {e}")
                break
            except (KeyError, IndexError) as e:
                logger.error(f"AI Service response parsing error: {e}")
                return "AI Analysis Error: Invalid response format"
            except Exception as e:
                logger.error(f"AI Service unexpected error: {e}")
                return f"AI Analysis Error: {str(e)}"

        return f"AI Analysis Error: {str(last_error)}"

    @staticmethod
    async def analyze_approval(
        request_type: str, description: str, amount: float
    ) -> dict:
        """
        Analyze approvals using LLM.

        P2 Fix: Improved JSON parsing with proper error handling.
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
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            return json.loads(clean_json)
        except json.JSONDecodeError as e:
            logger.warning(f"AI response JSON parsing failed: {e}")
            return {
                "decision": "manual_review_required",
                "reasoning": f"AI Parsing failed: {ai_response[:50]}",
            }
        except Exception as e:
            logger.error(f"Unexpected error parsing AI response: {e}")
            return {
                "decision": "manual_review_required",
                "reasoning": "System error during analysis",
            }
