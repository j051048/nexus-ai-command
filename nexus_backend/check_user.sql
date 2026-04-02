-- 查询 j051048@gmail.com 用户信息
SELECT id, email, organization_id, name, role
FROM users
WHERE email = 'j051048@gmail.com';

-- 查询所有组织
SELECT id, name, slug, created_at
FROM organizations
ORDER BY created_at;

-- 查询"厦门中合众科技有限公司"
SELECT id, name, slug
FROM organizations
WHERE name LIKE '%厦门中合众%' OR name LIKE '%中合众%';
