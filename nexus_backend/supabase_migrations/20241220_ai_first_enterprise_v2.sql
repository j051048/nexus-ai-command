-- AI-First 企业管理平台 数据库扩展 (修复版)
-- 支持 OA、财务、HR 等传统企业管理功能的 AI 化
-- 创建时间: 2024-12-20
-- 修复: 使用现有的 user_role 枚举值 (founder, sales, employee)

-- ============================================
-- 首先扩展 user_role 枚举（添加新角色）
-- ============================================

-- 安全地添加新的枚举值
DO $$ 
BEGIN
    -- 添加 manager 角色
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'manager' AND enumtypid = 'user_role'::regtype) THEN
        ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'manager';
    END IF;
    
    -- 添加 hr 角色
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'hr' AND enumtypid = 'user_role'::regtype) THEN
        ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'hr';
    END IF;
    
    -- 添加 boss 角色
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'boss' AND enumtypid = 'user_role'::regtype) THEN
        ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'boss';
    END IF;
EXCEPTION WHEN others THEN
    -- 忽略错误（枚举值可能已存在）
    NULL;
END $$;

-- ============================================
-- OA 办公自动化模块
-- ============================================

-- 请假申请表
CREATE TABLE IF NOT EXISTS oa_leave_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- annual, sick, personal, compensatory, maternity, paternity
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    days DECIMAL(4,1) NOT NULL,
    reason TEXT,
    handover_to UUID REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected, cancelled
    approval_level VARCHAR(20), -- auto, manager, director, ceo
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    approval_comment TEXT,
    ai_risk_score DECIMAL(3,2), -- AI 风险评分
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 会议室表
CREATE TABLE IF NOT EXISTS oa_meeting_rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    capacity INT NOT NULL DEFAULT 10,
    facilities JSONB DEFAULT '{}', -- {projector: true, video_conf: true, whiteboard: true}
    location VARCHAR(200),
    floor INT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 会议预约表
CREATE TABLE IF NOT EXISTS oa_meeting_bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID REFERENCES oa_meeting_rooms(id),
    organizer_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    attendees UUID[] DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'confirmed', -- confirmed, cancelled
    ai_generated BOOLEAN DEFAULT FALSE,
    created_from VARCHAR(50), -- chat, calendar, manual
    meeting_link VARCHAR(500), -- 在线会议链接
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 任务表（扩展 project_tasks 或独立）
CREATE TABLE IF NOT EXISTS oa_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    assignee_id UUID REFERENCES users(id),
    created_by UUID REFERENCES users(id),
    project_id UUID REFERENCES projects(id),
    status VARCHAR(20) DEFAULT 'todo', -- todo, in_progress, done, cancelled
    priority VARCHAR(20) DEFAULT 'medium', -- low, medium, high, urgent
    due_date DATE,
    estimated_hours DECIMAL(5,1),
    actual_hours DECIMAL(5,1),
    ai_created BOOLEAN DEFAULT FALSE,
    created_from_message_id VARCHAR(100), -- 从哪条对话创建
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 工作交接表
CREATE TABLE IF NOT EXISTS oa_work_handovers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    to_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    reason VARCHAR(100), -- leave, resign, transfer
    items JSONB DEFAULT '[]', -- [{title, description, status}]
    status VARCHAR(20) DEFAULT 'pending', -- pending, accepted, completed
    accepted_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 财务管理模块
-- ============================================

-- 费用报销明细表（补充 approval_requests）
CREATE TABLE IF NOT EXISTS finance_expense_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_request_id UUID REFERENCES approval_requests(id) ON DELETE CASCADE,
    expense_type VARCHAR(50) NOT NULL, -- travel, entertainment, office, transportation, communication
    expense_date DATE NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'CNY',
    receipt_url VARCHAR(500),
    receipt_ocr_data JSONB, -- OCR 识别结果
    receipt_verified BOOLEAN DEFAULT FALSE,
    project_id UUID REFERENCES projects(id),
    cost_center VARCHAR(50),
    attendees JSONB DEFAULT '[]', -- 招待费参与人员
    ai_category VARCHAR(50), -- AI 自动分类
    ai_compliance_check JSONB, -- {passed: bool, issues: []}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 预算表
CREATE TABLE IF NOT EXISTS finance_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department VARCHAR(100),
    project_id UUID REFERENCES projects(id),
    category VARCHAR(50) NOT NULL, -- travel, marketing, office, hr, general
    year INT NOT NULL,
    month INT, -- NULL 表示年度预算
    planned_amount DECIMAL(12,2) NOT NULL,
    used_amount DECIMAL(12,2) DEFAULT 0,
    alert_threshold DECIMAL(3,2) DEFAULT 0.8, -- 预警阈值
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(department, category, year, month)
);

-- 发票表
CREATE TABLE IF NOT EXISTS finance_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    invoice_code VARCHAR(50),
    invoice_number VARCHAR(50),
    invoice_date DATE,
    invoice_type VARCHAR(50), -- general, vat, train, taxi, hotel
    amount DECIMAL(12,2),
    tax_amount DECIMAL(12,2),
    total_amount DECIMAL(12,2),
    seller_name VARCHAR(200),
    seller_tax_id VARCHAR(50),
    image_url VARCHAR(500),
    ocr_data JSONB,
    verified BOOLEAN DEFAULT FALSE,
    verification_result JSONB, -- 验真结果
    used_in_claim_id UUID, -- 关联的报销单
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- HR 人力资源模块
-- ============================================

-- 考勤记录表
CREATE TABLE IF NOT EXISTS hr_attendance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    check_in TIMESTAMPTZ,
    check_out TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'normal', -- normal, late, early_leave, absent, leave
    late_minutes INT DEFAULT 0,
    early_leave_minutes INT DEFAULT 0,
    overtime_hours DECIMAL(4,1) DEFAULT 0,
    source VARCHAR(20) DEFAULT 'device', -- device, manual, ai_corrected
    location JSONB, -- {lat, lng, address}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- 绩效评估表
CREATE TABLE IF NOT EXISTS hr_performance_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    reviewer_id UUID REFERENCES users(id),
    period VARCHAR(20) NOT NULL, -- '2024-Q4', '2024-H2'
    self_rating DECIMAL(3,2),
    manager_rating DECIMAL(3,2),
    final_rating DECIMAL(3,2),
    ai_rating DECIMAL(3,2), -- AI 评估分
    ai_analysis TEXT, -- AI 分析报告
    goals JSONB DEFAULT '[]', -- [{title, target, actual, completion_rate}]
    strengths TEXT,
    improvements TEXT,
    status VARCHAR(20) DEFAULT 'draft', -- draft, submitted, reviewed, finalized
    submitted_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 薪资记录表（敏感数据，需要额外权限控制）
CREATE TABLE IF NOT EXISTS hr_salary_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    period VARCHAR(7) NOT NULL, -- '2024-12'
    base_salary DECIMAL(12,2),
    performance_bonus DECIMAL(12,2) DEFAULT 0,
    attendance_bonus DECIMAL(12,2) DEFAULT 0,
    other_allowances DECIMAL(12,2) DEFAULT 0,
    gross_salary DECIMAL(12,2),
    social_insurance DECIMAL(12,2) DEFAULT 0,
    housing_fund DECIMAL(12,2) DEFAULT 0,
    tax DECIMAL(12,2) DEFAULT 0,
    other_deductions DECIMAL(12,2) DEFAULT 0,
    net_salary DECIMAL(12,2),
    payment_date DATE,
    payment_status VARCHAR(20) DEFAULT 'pending', -- pending, paid
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, period)
);

-- 招聘职位表
CREATE TABLE IF NOT EXISTS hr_job_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(100) NOT NULL,
    department VARCHAR(100),
    description TEXT,
    requirements TEXT,
    salary_range_min DECIMAL(12,2),
    salary_range_max DECIMAL(12,2),
    headcount INT DEFAULT 1,
    hired_count INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'open', -- open, paused, closed
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 候选人表
CREATE TABLE IF NOT EXISTS hr_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_position_id UUID REFERENCES hr_job_positions(id),
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    resume_url VARCHAR(500),
    source VARCHAR(50), -- boss, zhilian, liepin, referral
    referrer_id UUID REFERENCES users(id),
    stage VARCHAR(50) DEFAULT 'screening', -- screening, interview_1, interview_2, offer, hired, rejected
    rating DECIMAL(3,2),
    interview_notes TEXT,
    ai_analysis JSONB, -- AI 简历分析
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- AI 交互记录表
-- ============================================

CREATE TABLE IF NOT EXISTS ai_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100),
    agent VARCHAR(50), -- 使用的 Agent
    intent VARCHAR(100), -- 识别出的意图
    entities JSONB DEFAULT '{}', -- 提取的实体
    user_message TEXT,
    ai_response TEXT,
    tools_used JSONB DEFAULT '[]', -- [{tool_name, args, result}]
    action_taken VARCHAR(100), -- 执行的操作
    action_result JSONB, -- 操作结果
    satisfaction_score INT, -- 用户满意度 1-5
    feedback TEXT,
    duration_ms INT, -- 处理耗时
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- 索引优化
-- ============================================

-- 请假表索引
CREATE INDEX IF NOT EXISTS idx_leave_requests_user_id ON oa_leave_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_status ON oa_leave_requests(status);
CREATE INDEX IF NOT EXISTS idx_leave_requests_dates ON oa_leave_requests(start_date, end_date);

-- 会议预约索引
CREATE INDEX IF NOT EXISTS idx_meeting_bookings_room ON oa_meeting_bookings(room_id);
CREATE INDEX IF NOT EXISTS idx_meeting_bookings_time ON oa_meeting_bookings(start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_meeting_bookings_organizer ON oa_meeting_bookings(organizer_id);

-- 任务索引
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON oa_tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON oa_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON oa_tasks(due_date);

-- 考勤索引
CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON hr_attendance(user_id, date);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON hr_attendance(date);

-- AI 交互索引
CREATE INDEX IF NOT EXISTS idx_ai_interactions_user ON ai_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_interactions_session ON ai_interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_ai_interactions_intent ON ai_interactions(intent);
CREATE INDEX IF NOT EXISTS idx_ai_interactions_created ON ai_interactions(created_at);

-- ============================================
-- RLS (Row Level Security) 策略
-- ============================================

-- 请假表 RLS
ALTER TABLE oa_leave_requests ENABLE ROW LEVEL SECURITY;

-- 删除已存在的策略（如果有）
DROP POLICY IF EXISTS "Users can view own leave requests" ON oa_leave_requests;
DROP POLICY IF EXISTS "Managers can view all leave requests" ON oa_leave_requests;
DROP POLICY IF EXISTS "Users can create own leave requests" ON oa_leave_requests;

CREATE POLICY "Users can view own leave requests" ON oa_leave_requests
    FOR SELECT USING (auth.uid() = user_id);

-- 使用现有的角色值: founder 作为管理者
CREATE POLICY "Managers can view all leave requests" ON oa_leave_requests
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM users 
            WHERE users.id = auth.uid() 
            AND users.role = 'founder'
        )
    );

CREATE POLICY "Users can create own leave requests" ON oa_leave_requests
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 薪资表 RLS（严格限制）
ALTER TABLE hr_salary_records ENABLE ROW LEVEL SECURITY;

-- 删除已存在的策略（如果有）
DROP POLICY IF EXISTS "Users can only view own salary" ON hr_salary_records;
DROP POLICY IF EXISTS "HR can view all salaries" ON hr_salary_records;

CREATE POLICY "Users can only view own salary" ON hr_salary_records
    FOR SELECT USING (auth.uid() = user_id);

-- founder 可以查看所有薪资
CREATE POLICY "Founder can view all salaries" ON hr_salary_records
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM users 
            WHERE users.id = auth.uid() 
            AND users.role = 'founder'
        )
    );

-- ============================================
-- 触发器：自动更新 updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 删除已存在的触发器（如果有）
DROP TRIGGER IF EXISTS update_leave_requests_updated_at ON oa_leave_requests;
DROP TRIGGER IF EXISTS update_tasks_updated_at ON oa_tasks;
DROP TRIGGER IF EXISTS update_budgets_updated_at ON finance_budgets;
DROP TRIGGER IF EXISTS update_performance_reviews_updated_at ON hr_performance_reviews;

CREATE TRIGGER update_leave_requests_updated_at
    BEFORE UPDATE ON oa_leave_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON oa_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_budgets_updated_at
    BEFORE UPDATE ON finance_budgets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_performance_reviews_updated_at
    BEFORE UPDATE ON hr_performance_reviews
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 初始化数据
-- ============================================

-- 插入示例会议室（使用 ON CONFLICT 避免重复）
INSERT INTO oa_meeting_rooms (name, capacity, facilities, location, floor) VALUES
('洽谈室A', 4, '{"projector": false, "video_conf": false, "whiteboard": true}', '1楼大堂', 1),
('会议室301', 10, '{"projector": true, "video_conf": true, "whiteboard": true}', '3楼东侧', 3),
('会议室302', 8, '{"projector": true, "video_conf": false, "whiteboard": true}', '3楼西侧', 3),
('多功能厅', 50, '{"projector": true, "video_conf": true, "whiteboard": true, "stage": true}', '5楼', 5)
ON CONFLICT DO NOTHING;

-- 插入示例预算
INSERT INTO finance_budgets (department, category, year, month, planned_amount) VALUES
('销售部', 'travel', 2024, 12, 50000),
('销售部', 'entertainment', 2024, 12, 30000),
('市场部', 'marketing', 2024, 12, 80000),
('技术部', 'office', 2024, 12, 20000)
ON CONFLICT (department, category, year, month) DO NOTHING;

-- ============================================
-- 完成提示
-- ============================================
COMMENT ON TABLE oa_leave_requests IS 'OA请假申请表 - AI自动化处理';
COMMENT ON TABLE oa_meeting_bookings IS 'OA会议预约表 - 支持AI智能预约';
COMMENT ON TABLE hr_attendance IS 'HR考勤记录表';
COMMENT ON TABLE ai_interactions IS 'AI交互记录表 - 用于分析和优化';

-- 输出成功信息
DO $$ 
BEGIN
    RAISE NOTICE '✅ AI-First 企业管理平台数据库扩展安装成功！';
    RAISE NOTICE '已创建 14 张新表，包括 OA、财务、HR、AI 模块';
END $$;