# 本地开发

## 环境

- Node.js 20+，使用 `npm ci` 保持 lockfile 一致。
- Python 3.11，后端依赖来自 `nexus_backend/requirements-dev.txt`。
- 测试可使用占位 Supabase/LLM 配置；真实集成测试必须使用隔离项目。

## 启动

```powershell
npm ci
Copy-Item .env.example .env
npm run dev

cd nexus_backend
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements-dev.txt
Copy-Item .env.example .env
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

## 调试原则

- 先记录失败请求的 `trace_id`，再关联 API、Agent run、工具调用和数据库审计。
- 不通过关闭 RLS、硬编码管理员角色或吞掉异常来“修复”本地问题。
- 外部服务不可用时使用已有 cassette/fixture，禁止单测访问生产网络。
