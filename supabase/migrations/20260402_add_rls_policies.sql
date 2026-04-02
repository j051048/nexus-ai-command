-- P0 Security Fix: 添加 RLS 策略确保多租户数据隔离
-- 执行时间: 2026-04-02
-- 影响: 所有租户数据安全隔离

-- 1. 启用 RLS (Row Level Security)
ALTER TABLE sales_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;

-- 2. 销售线索表 RLS 策略
CREATE POLICY "租户隔离-查询" ON sales_leads
  FOR SELECT USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-插入" ON sales_leads
  FOR INSERT WITH CHECK (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-更新" ON sales_leads
  FOR UPDATE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-删除" ON sales_leads
  FOR DELETE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- 3. 客户表 RLS 策略
CREATE POLICY "租户隔离-查询" ON customers
  FOR SELECT USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-插入" ON customers
  FOR INSERT WITH CHECK (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-更新" ON customers
  FOR UPDATE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-删除" ON customers
  FOR DELETE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- 4. 合同表 RLS 策略
CREATE POLICY "租户隔离-查询" ON contracts
  FOR SELECT USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-插入" ON contracts
  FOR INSERT WITH CHECK (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-更新" ON contracts
  FOR UPDATE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-删除" ON contracts
  FOR DELETE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- 5. 工单表 RLS 策略
CREATE POLICY "租户隔离-查询" ON work_orders
  FOR SELECT USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-插入" ON work_orders
  FOR INSERT WITH CHECK (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-更新" ON work_orders
  FOR UPDATE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-删除" ON work_orders
  FOR DELETE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- 6. 项目表 RLS 策略
CREATE POLICY "租户隔离-查询" ON projects
  FOR SELECT USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-插入" ON projects
  FOR INSERT WITH CHECK (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-更新" ON projects
  FOR UPDATE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-删除" ON projects
  FOR DELETE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- 7. 审批请求表 RLS 策略
CREATE POLICY "租户隔离-查询" ON approval_requests
  FOR SELECT USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-插入" ON approval_requests
  FOR INSERT WITH CHECK (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-更新" ON approval_requests
  FOR UPDATE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

CREATE POLICY "租户隔离-删除" ON approval_requests
  FOR DELETE USING (
    organization_id = (
      SELECT organization_id FROM users WHERE id = auth.uid()
    )
  );

-- 8. 验证 RLS 策略已生效
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'sales_leads', 'customers', 'contracts', 'work_orders',
    'projects', 'approval_requests', 'assets', 'certificates',
    'inventory'
  );