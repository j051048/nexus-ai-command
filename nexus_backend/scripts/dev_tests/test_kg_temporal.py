import asyncio
import os
import sys
from datetime import datetime, timedelta
from uuid import uuid4

# Setup path
sys.path.append(os.getcwd())

from app.core.database import supabase
from app.services.conversation_memory.graph_extraction import (
    _store_triples,
    query_entity_at_time,
    query_entity_relations,
)


async def test_temporal_validity():
    print("Testing Knowledge Graph Temporal Validity...")

    environment = os.getenv("ENV", "development").lower()
    if environment in {"production", "prod"} and os.getenv("ALLOW_KG_DEV_WRITE") != "1":
        raise RuntimeError("Knowledge graph dev writes are disabled in production")

    org_id = os.getenv("TEST_ORG_ID")
    if not org_id:
        raise RuntimeError("Set TEST_ORG_ID explicitly before running this write test")

    print(f"Using Org ID: {org_id}")

    entity_name = f"TestSubject_{uuid4().hex[:8]}"

    # 1. Store initial fact: Subject works at Company A
    print(f"\n1. Storing initial fact: {entity_name} works at Company A")
    rel_a = [
        {
            "source": entity_name,
            "source_type": "person",
            "relationship": "在",
            "destination": "Company_A",
            "destination_type": "organization",
        }
    ]

    await _store_triples(rel_a, org_id, None, "Initial hire", supabase)

    # Get the timestamp of the first record
    first_res = await query_entity_relations(
        org_id, entity_name, db=supabase, include_historical=True
    )
    if not first_res:
        print("Error: Failed to store first triple")
        return

    t1_valid_from = first_res[0]["valid_from"]
    print(f"Stored first triple. Valid from: {t1_valid_from}")

    # 2. Simulate time passing and store updated fact: Subject works at Company B
    print("\n2. Storing conflicting fact: Subject works at Company B")
    await asyncio.sleep(1)  # Ensure timestamp difference

    rel_b = [
        {
            "source": entity_name,
            "source_type": "person",
            "relationship": "在",
            "destination": "Company_B",
            "destination_type": "organization",
        }
    ]

    await _store_triples(rel_b, org_id, None, "Job change", supabase)

    # 3. Verify current state (should be Company B)
    print("\n3. Verifying current state...")
    current = await query_entity_relations(
        org_id, entity_name, db=supabase, include_historical=False
    )
    print(f"Current relations count: {len(current)}")
    for r in current:
        print(
            f"  {r['source_entity']} -{r['relationship']}-> {r['destination_entity']} (valid_to: {r['valid_to']})"
        )

    # 4. Verify historical state (should see both A and B, A should have valid_to set)
    print("\n4. Verifying historical state...")
    all_history = await query_entity_relations(
        org_id, entity_name, db=supabase, include_historical=True
    )
    print(f"All history count: {len(all_history)}")
    for r in all_history:
        status = "HISTORICAL" if r.get("valid_to") else "CURRENT"
        print(
            f"  [{status}] {r['source_entity']} -{r['relationship']}-> {r['destination_entity']} [From: {r['valid_from']} To: {r['valid_to']}]"
        )

    # 5. Test Point-in-time Query
    dt1 = datetime.fromisoformat(t1_valid_from.replace("Z", "+00:00"))
    target_dt = dt1 + timedelta(milliseconds=500)
    target_iso = target_dt.isoformat()

    print(f"\n5. Testing Point-in-time Query at {target_iso} (Should be Company A)")
    at_time = await query_entity_at_time(org_id, entity_name, target_iso, db=supabase)
    print(f"Results at {target_iso}: {len(at_time)}")
    for r in at_time:
        print(
            f"  {r['source_entity']} -{r['relationship']}-> {r['destination_entity']}"
        )


if __name__ == "__main__":
    asyncio.run(test_temporal_validity())
