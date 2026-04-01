# P0-1: 前端直连数据库封堵重构计划

## 任务目标

将所有前端 `supabase.from()` 直连调用改为通过后端API

## 实施步骤

### 第一步: 搜索所有直连调用

```bash
# 搜索命令
grep -r "supabase.from(" src/ --include="*.tsx" --include="*.ts"
```

### 第二步: 为每个表创建后端API

需要创建的API端点示例:

- GET /api/contracts - 查询合同
- POST /api/contracts - 创建合同
- GET /api/employees - 查询员工
- POST /api/leave-requests - 创建请假

### 第三步: 替换前端调用

**修改前:**

```typescript
const { data } = await supabase.from('contracts').select('*');
```

**修改后:**

```typescript
const { data } = await httpClient.get('/api/contracts');
```

### 第四步: 删除前端Supabase权限

修改 `.env` 移除前端的 `SUPABASE_ANON_KEY`

## 预计工作量

- 搜索文件: 0.5小时
- 创建API: 4-6小时
- 替换调用: 2-3小时
- 测试验证: 2小时

## 预计总计时长: 1-2天

## 注意事项

1. 保留RLS策略作为双重保护
2. 后端API需要完整的权限校验
3. 逐个表迁移,避免一次性改动过大

重构计划已创建,建议分批实施。
