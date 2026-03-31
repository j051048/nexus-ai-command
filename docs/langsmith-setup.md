# LangSmith 集成指南

## 1. 环境变量配置

在 `.env` 文件添加：

```bash
# LangSmith Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=nexus-ai-command
```

## 2. 获取 API Key

1. 访问 https://smith.langchain.com/
2. 注册/登录账号
3. 进入 Settings → API Keys
4. 创建新的 API Key
5. 复制到 `.env` 文件

## 3. 验证集成

启动后端后，所有 LangGraph 执行会自动上报到 LangSmith。

访问 https://smith.langchain.com/projects 查看执行轨迹。

## 4. 预期收益

- 可视化 Agent 执行流程
- 重现任何一次执行
- 性能瓶颈分析
- Token 消耗统计

**实施完成 ✅**
