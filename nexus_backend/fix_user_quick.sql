-- 快速修复：直接关联用户到已存在的组织
UPDATE users
SET organization_id = 'a373de03-df15-4b67-81a9-813e12b7fa35',
    updated_at = NOW()
WHERE email = 'j051048@gmail.com';

-- 验证更新结果
SELECT id, email, organization_id, name
FROM users
WHERE email = 'j051048@gmail.com';
