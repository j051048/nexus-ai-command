"""成本监控"""

class CostTracker:
    async def track_llm_call(self, model: str, tokens: int):
        cost = tokens * 0.00001  # 示例价格
        print(f"LLM调用: {model}, {tokens} tokens, ${cost:.4f}")

cost_tracker = CostTracker()
