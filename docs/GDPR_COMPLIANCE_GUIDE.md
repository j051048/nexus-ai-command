# GDPR 合规实施指南

## 数据主体权利实现

### 1. Right to Erasure (删除权)

**数据库迁移**：
```sql
-- 添加到新的迁移文件
CREATE OR REPLACE FUNCTION delete_user_data(user_id_param UUID)
RETURNS void AS $$
BEGIN
  -- 删除用户所有数据
  DELETE FROM conversation_memories WHERE user_id = user_id_param;
  DELETE FROM chat_sessions WHERE user_id = user_id_param;
  DELETE FROM approvals WHERE user_id = user_id_param;
  DELETE FROM customers WHERE user_id = user_id_param;
  -- 添加其他表...
  
  -- 匿名化用户记录
  UPDATE users 
  SET email = 'deleted_' || id || '@deleted.local',
      name = 'Deleted User',
      deleted_at = NOW()
  WHERE id = user_id_param;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 2. Right to Portability (数据可携权)

**API 端点**：`/api/gdpr/export-data`

### 3. 隐私设置页面

**前端组件**：`src/pages/PrivacySettings.tsx`

详细实施见代码文件。
