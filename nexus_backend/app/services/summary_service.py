"""
Conversation Summary Service
Compresses long conversation history into concise summaries to manage context window.
"""
import logging
import httpx
from typing import List, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)

class SummaryService:
    """Compresses conversation history into summaries when context grows too long."""
    
    @staticmethod
    async def summarize_messages(messages: List[Dict], config: Dict = None) -> str:
        """
        Summarize a list of messages into a concise summary.
        
        Args:
            messages: List of message dicts with role/content
            config: AI config (api_key, base_url, model)
        Returns:
            Summary string
        """
        api_key = (config or {}).get("api_key") or settings.OPENAI_API_KEY
        base_url = (config or {}).get("base_url") or settings.AI_BASE_URL or "https://api.openai.com/v1"
        model = (config or {}).get("model") or getattr(settings, 'AI_DEFAULT_MODEL', 'gpt-4o')
        
        if not api_key:
            # Fallback: simple extraction of key points
            return SummaryService._simple_summary(messages)
        
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        
        # Build summary prompt
        conversation_text = ""
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content and isinstance(content, str):
                conversation_text += f"[{role}]: {content[:500]}\n"
        
        summary_prompt = f"""请用中文将以下对话压缩为简洁的摘要（不超过200字），保留关键信息、决策和待办事项：

{conversation_text}

摘要："""
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "你是一个对话摘要助手，擅长提取关键信息。"},
                            {"role": "user", "content": summary_prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 300
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content'].strip()
                else:
                    logger.warning(f"Summary API error: {response.status_code}")
                    return SummaryService._simple_summary(messages)
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return SummaryService._simple_summary(messages)
    
    @staticmethod
    def _simple_summary(messages: List[Dict]) -> str:
        """Fallback: extract last few user messages as summary."""
        user_msgs = [m.get("content", "")[:100] for m in messages if m.get("role") == "user" and m.get("content")]
        if not user_msgs:
            return "（无可用的对话历史摘要）"
        recent = user_msgs[-3:]
        return "用户之前讨论了：" + "；".join(recent)

summary_service = SummaryService()
