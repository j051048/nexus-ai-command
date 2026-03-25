
import asyncio
import sys
import os
import traceback
from pathlib import Path

# Fix paths
PROJECT_ROOT = Path(__file__).parents[1]
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(PROJECT_ROOT / "nexus_backend"))
sys.path.append(str(PROJECT_ROOT / "test_memory_bench" / "src"))

async def main():
    try:
        from test_memory_bench.nexus_bench_locomo import async_main
        await async_main()
    except Exception:
        print("\n" + "!"*40)
        print("CRITICAL EXCEPTION CAPTURED:")
        traceback.print_exc()
        print("!"*40 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
