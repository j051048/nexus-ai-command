# Project Nexus Backend Deployment Guide

本指南将帮助你部署 Project Nexus 的全套后端服务（Supabase 数据库 + Zeabur 核心 API）。

## 1. Supabase 数据库部署

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard) 并创建一个新项目。
2. 进入项目的 **SQL Editor**。
3. 复制并运行 `nexus_backend/supabase/migrations/20240126000000_initial_schema.sql` 中的内容。
   - 这将创建所有表、枚举、RLS策略和触发器。
4. (可选) 运行 `nexus_backend/supabase/migrations/20240126999999_seed_data.sql` 填充模拟数据。
5. 在 **Project Settings -> API** 中获取：
   - Project URL
   - service_role secret (注意：用于后端服务，不要暴露给前端)

## 2. Zeabur 后端部署

1. 登录 [Zeabur Dashboard](https://zeabur.com)。
2. 创建新项目。
3. **部署服务**：
   - 方式 A (推荐)：将本代码库推送到 GitHub，在 Zeabur 中选择 Repo 部署。
   - 方式 B (本地)：在 Zeabur 仪表盘选择“Deploy Service” -> "Code Source"，上传 `nexus_backend` 文件夹。
4. **环境变量配置**：
   在 Zeabur 服务设置中添加环境变量：

   ```
   SUPABASE_URL=你的Supabase项目URL
   SUPABASE_SERVICE_KEY=你的Supabase_Service_Role_Key
   # MILVUS_HOST=... (如果部署了Milvus，否则默认使用Mock模式)
   ```

5. 等待构建完成，你将获得一个 `https://xxx.zeabur.app` 的访问地址。

## 3. 验证与测试

服务启动后，访问以下接口进行测试：

- **API 文档**: `https://<你的域名>/docs`
- **老板仪表盘**: `GET /api/dashboard/boss`
- **触发绩效计算**: `POST /api/performance/calculate`

  ```json
  {
    "user_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12",
    "event_type": "call_finished",
    "data": {"duration": 300, "ai_quality_score": 85}
  }
  ```

## 4. 前端集成建议

前端 Agent 可直接调用上述 API：

- 需要查询数据时，优先使用 Supabase Client 直接查库 (需配置 RLS)。
- 需要执行复杂逻辑 (打分、审批、写金蝶) 时，调用 Zeabur 的 API。

## 5. 本地开发

```bash
cd nexus_backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
