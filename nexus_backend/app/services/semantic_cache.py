import logging
from typing import Optional, Dict, Any
from app.core.database import supabase
from app.core.config import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class SemanticCacheService:
    """
    P2 Optimization (Area 9/6): Semantic Caching for AI responses.
    Reduces LLM API calls and latency for repetitive or highly similar queries.
    """
    
    def __init__(self):
        self.threshold = settings.SEMANTIC_CACHE_THRESHOLD if hasattr(settings, 'SEMANTIC_CACHE_THRESHOLD') else 0.95
        # Initialize OpenAI client for embeddings
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.AI_BASE_URL.split("/chat/completions")[0].rstrip("/") if settings.AI_BASE_URL else None
        )

    async def get_cache(self, query: str, user_id: str) -> Optional[str]:
        """
        Check if a similar query exists in the cache.
        Returns the cached response if similarity > threshold.
        """
        if not supabase or not settings.OPENAI_API_KEY:
            return None

        try:
            # 1. Get embedding for the new query
            response = await self.openai_client.embeddings.create(
                input=query, 
                model="text-embedding-3-small"
            )
            query_embedding = response.data[0].embedding

            # 2. Match in Supabase via RPC
            res = await supabase.rpc("match_semantic_cache", {
                "p_query_embedding": query_embedding,
                "p_match_threshold": self.threshold,
                "p_user_id": user_id
            }).execute()

            if res.data and len(res.data) > 0:
                match = res.data[0]
                logger.info(f"Semantic Cache Hit: query='{query[:30]}...', similarity={match['similarity']:.4f}")
                
                # Update hit count (Async, don't wait)
                import asyncio
                asyncio.create_task(self._update_hit_count(match['id']))
                
                return match['response_text']
            
            return None
        except Exception as e:
            logger.warning(f"Semantic cache lookup failed: {e}")
            return None

    async def set_cache(self, query: str, response_text: str, user_id: str):
        """
        Store a new query-response pair in the semantic cache.
        """
        if not supabase or not settings.OPENAI_API_KEY or not response_text:
            return

        try:
            # 1. Get embedding
            response = await self.openai_client.embeddings.create(
                input=query, 
                model="text-embedding-3-small"
            )
            embedding = response.data[0].embedding

            # 2. Get org_id for multi-tenancy
            u_res = await supabase.table("users").select("organization_id").eq("id", user_id).maybe_single().execute()
            org_id = u_res.data.get("organization_id") if u_res.data else None

            # 3. Insert into cache
            await supabase.table("semantic_cache").insert({
                "query_text": query,
                "response_text": response_text,
                "embedding": embedding,
                "user_id": user_id,
                "org_id": org_id
            }).execute()
            
        except Exception as e:
            logger.warning(f"Failed to set semantic cache: {e}")

    async def _update_hit_count(self, cache_id: int):
        """Internal helper to increment hit counter"""
        try:
            await supabase.table("semantic_cache")\
                .update({"hit_count": 5, "last_hit_at": "now()"}) \
                .eq("id", cache_id).execute()
        except Exception:
             pass

semantic_cache_service = SemanticCacheService()
