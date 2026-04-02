-- 一键修复脚本：将 j051048@gmail.com 关联到"厦门中合众科技有限公司"
-- 在 Supabase SQL Editor 中运行此脚本

DO $$
DECLARE
  target_org_id UUID;
  target_user_id UUID;
BEGIN
  -- 查找组织
  SELECT id INTO target_org_id
  FROM organizations
  WHERE name = '厦门中合众科技有限公司'
  LIMIT 1;

  -- 如果组织不存在，创建它
  IF target_org_id IS NULL THEN
    INSERT INTO organizations (name, slug, created_at, updated_at)
    VALUES (
      '厦门中合众科技有限公司',
      'xiamen-zhonghezong-' || floor(random() * 1000000)::text,
      NOW(),
      NOW()
    )
    RETURNING id INTO target_org_id;
    RAISE NOTICE '已创建组织: %', target_org_id;
  ELSE
    RAISE NOTICE '找到现有组织: %', target_org_id;
  END IF;

  -- 查找用户
  SELECT id INTO target_user_id
  FROM users
  WHERE email = 'j051048@gmail.com'
  LIMIT 1;

  IF target_user_id IS NULL THEN
    RAISE EXCEPTION '未找到用户 j051048@gmail.com';
  END IF;

  -- 更新用户的 organization_id
  UPDATE users
  SET organization_id = target_org_id,
      updated_at = NOW()
  WHERE id = target_user_id;

  RAISE NOTICE '已将用户 % 关联到组织 %', target_user_id, target_org_id;
END $$;
