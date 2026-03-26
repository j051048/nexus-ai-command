"""
TurboQuant Phase 1 & 2 集成测试
"""

import asyncio
import numpy as np
from app.services.turboquant import TurboQuant
from app.services.vector_service import VectorService


async def test_phase1_vector_compression():
    """测试 Phase 1: 向量压缩"""
    print("\n=== Phase 1: 向量压缩测试 ===")

    # 模拟 1536 维 embedding
    embedding = np.random.randn(1536).tolist()

    # 量化
    quantized = VectorService.quantize_embedding(embedding)
    print(f"原始大小: {len(embedding) * 4} 字节")

    # 反量化
    recovered = VectorService.dequantize_embedding(quantized)

    # 计算误差
    mse = np.mean((np.array(embedding) - np.array(recovered)) ** 2)
    print(f"MSE 误差: {mse:.6f}")
    print(f"压缩比: {TurboQuant(1536).compression_ratio():.1f}x")


async def test_phase2_memory_compression():
    """测试 Phase 2: 记忆压缩"""
    print("\n=== Phase 2: 记忆压缩测试 ===")

    from app.agent.memory import compress_old_messages

    # 模拟消息历史
    messages = [
        {"role": "user", "content": f"消息 {i}", "embedding": np.random.randn(1536).tolist()}
        for i in range(20)
    ]

    print(f"原始消息数: {len(messages)}")

    # 压缩（保留最近 10 条）
    compressed = await compress_old_messages(messages, preserve_recent=10)

    quantized_count = sum(1 for m in compressed if "embedding_quantized" in m)
    print(f"量化消息数: {quantized_count}")
    print(f"预期内存节省: ~{quantized_count * 1536 * 4 * 0.83 / 1024:.1f} KB")


async def main():
    print("开始 TurboQuant 集成测试...")
    await test_phase1_vector_compression()
    await test_phase2_memory_compression()
    print("\n✅ 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
