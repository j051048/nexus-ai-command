
import asyncio
import logging
import sys
import os

# 将项目根目录添加到 python 路径
sys.path.append(os.getcwd())

from app.agent.query_transformer import QueryTransformer
from app.agent.state import AgentConfig

logging.basicConfig(level=logging.INFO)

async def test_rewrite():
    # 模拟一个没有 api_key 的 config，应该自动 fallback 到全局 settings
    config = AgentConfig(
        user_id="test_user",
        api_key="", # 显式为空，测试 fallback
        base_url="https://api.apiyi.com/v1",
        mini_model="gpt-4o-mini"
    )
    
    transformer = QueryTransformer(config)
    
    print("Testing query rewrite with fallback...")
    try:
        query = "那个文件存哪了？"
        messages = [
            {"role": "user", "content": "帮我找一下去年的年度总结报告。"},
            {"role": "assistant", "content": "好的，年度总结报告已经存入知识库了。"}
        ]
        
        rewritten = await transformer.rewrite_query(query, messages=messages)
        print(f"Original: {query}")
        print(f"Rewritten: {rewritten}")
        
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_rewrite())
