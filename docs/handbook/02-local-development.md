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
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

## 格式与 CI 一致性

后端只使用 **Black 24.10.0** 格式化（88 列、Python 3.11 目标语法），
Ruff 0.8.6 负责静态检查，不再同时运行 `ruff format`。
版本由 `requirements-dev.txt` 和提交钩子固定；`pyproject.toml` 会拒绝其他
Black 版本，避免本地格式通过、CI 却要求重新排版。

在 `nexus_backend` 目录使用已安装开发依赖的环境运行：

```powershell
.\.venv\Scripts\python.exe -m black app/
.\.venv\Scripts\python.exe -m black --check app/
.\.venv\Scripts\python.exe -m ruff check app/
.\.venv\Scripts\python.exe -m pytest tests/unit/ tests/security/ --no-cov
```

已安装 `uv` 时，也可隔离运行固定版本，不修改其他项目的 Python 环境：

```powershell
uv tool run --python 3.11 --from black==24.10.0 black --check app/
uv tool run --python 3.11 --from ruff==0.8.6 ruff check app/
```

## 调试原则

- 先记录失败请求的 `trace_id`，再关联 API、Agent run、工具调用和数据库审计。
- 不通过关闭 RLS、硬编码管理员角色或吞掉异常来“修复”本地问题。
- 外部服务不可用时使用已有 cassette/fixture，禁止单测访问生产网络。
