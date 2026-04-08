
import asyncio
import logging
import sys
import os
from datetime import UTC, datetime

# Mock AIService to avoid real LLM calls for testing the storage logic
class MockAIService:
    @staticmethod
    async def call_llm(prompt, system_prompt):
        # We'll control this in the test
        return ""

# Patching before imports
sys.path.append(os.path.join(os.getcwd(), "nexus_backend"))

from app.services.conversation_memory.graph_extraction import _store_triples, _find_existing_triple, _find_conflicting_triple
from app.core.database import supabase

logger = logging.getLogger(__name__)

async def test_temporal_evolution():
    logger.info(f"Supabase URL: {supabase._url}")
    """测试三元组的时间演变：张三从 Google 换到 Apple"""
    org_id = "a373de03-df15-4b67-81a9-813e12b7fa35"
    user_id = "a9c077eb-f99b-480c-9fd1-68a79dc13ebb"
    
    # 1. 初始状态：Alice 在 Google
    rel1 = {
        "source": "Alice",
        "source_type": "person",
        "relationship": "works_at",
        "destination": "Google",
        "destination_type": "organization"
    }
    
    logger.info("Step 1: Inserting initial relation 'Alice -> works_at -> Google'")
    saved1 = await _store_triples([rel1], org_id, user_id, "Source context 1", supabase)
    if not saved1:
        logger.error("Failed to save initial relation")
        return
    
    # 2. 状态变更：Alice 现在在 Apple
    rel2 = {
        "source": "Alice",
        "source_type": "person",
        "relationship": "works_at",
        "destination": "Apple",
        "destination_type": "organization"
    }
    
    logger.info("Step 2: Inserting updated relation 'Alice -> works_at -> Apple'")
    saved2 = await _store_triples([rel2], org_id, user_id, "Source context 2", supabase)
    
    # 3. 验证结果
    # 应该有两条记录，一条 valid_to 已设置（历史），一条 valid_to 为空（当前）
    result = await supabase.table("knowledge_graph_triples") \
        .select("*") \
        .eq("organization_id", org_id) \
        .eq("source_entity", "Alice") \
        .eq("relationship", "works_at") \
        .execute()
    
    data = result.data
    logger.info(f"Verification: Found {len(data)} records for '张三-在-...'")
    
    for row in data:
        logger.info(f"Record: ID={row['id']}, Destination={row['destination_entity']}, "
                    f"ValidFrom={row['valid_from']}, ValidTo={row['valid_to']}")
        
    google_rec = next((r for r in data if r['destination_entity'] == "Google"), None)
    apple_rec = next((r for r in data if r['destination_entity'] == "Apple"), None)
    
    if google_rec and google_rec['valid_to']:
        logger.info("✅ Success: Google record soft-expired via valid_to")
    else:
        logger.error("❌ Failure: Google record valid_to is not set")
        
    if apple_rec and apple_rec['valid_to'] is None:
        logger.info("✅ Success: Apple record is currently active")
    else:
        logger.error("❌ Failure: Apple record should be active (valid_to is null)")

if __name__ == "__main__":
    asyncio.run(test_temporal_evolution())
