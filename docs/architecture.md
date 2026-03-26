# Nexus AI Command 架构文档

## 系统架构
- 前端: React + Vite + TailwindCSS
- 后端: FastAPI + LangGraph Agent
- 数据库: Supabase (PostgreSQL)
- 缓存: Redis

## Agent 架构
Router → Plan → Execute → Reflect → Critic → Respond

## 数据流
用户请求 → API → Agent → 工具执行 → 数据库 → 响应
