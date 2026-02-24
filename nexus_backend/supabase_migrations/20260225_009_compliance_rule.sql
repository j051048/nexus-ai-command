-- Compliance Rule Engine & Check Log Tables

-- ============================================================
-- 1. compliance_rule — 合规规则库
-- ============================================================
CREATE TABLE IF NOT EXISTS compliance_rule (
  id bigserial PRIMARY KEY,
  tenant_id uuid REFERENCES organizations(id),
  rule_code varchar(100) NOT NULL,
  rule_name varchar(200),
  category varchar(50) NOT NULL, -- advertising_law/metrology_law/bidding_law/medical_device/industry_standard
  severity varchar(20) DEFAULT 'warning', -- error/warning/info
  check_type varchar(20) DEFAULT 'keyword', -- regex/keyword/llm
  pattern text,
  description text,
  replacement_suggestion text,
  is_active boolean DEFAULT true,
  create_time timestamptz DEFAULT now(),
  UNIQUE(tenant_id, rule_code)
);

-- RLS
ALTER TABLE compliance_rule ENABLE ROW LEVEL SECURITY;
CREATE POLICY "compliance_rule_tenant_isolation" ON compliance_rule
  USING (
    tenant_id IS NULL
    OR tenant_id = current_setting('app.current_org_id', true)::uuid
  );

-- Indexes
CREATE INDEX idx_compliance_rule_tenant ON compliance_rule(tenant_id);
CREATE INDEX idx_compliance_rule_category ON compliance_rule(category, is_active);
CREATE INDEX idx_compliance_rule_severity ON compliance_rule(severity, is_active);

-- ============================================================
-- 2. compliance_check_log — 合规校验记录
-- ============================================================
CREATE TABLE IF NOT EXISTS compliance_check_log (
  id bigserial PRIMARY KEY,
  tenant_id uuid,
  user_id uuid,
  content_type varchar(50),
  content_hash varchar(64),
  total_issues int DEFAULT 0,
  error_count int DEFAULT 0,
  warning_count int DEFAULT 0,
  check_result jsonb,
  created_at timestamptz DEFAULT now()
);

-- RLS
ALTER TABLE compliance_check_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "compliance_check_log_tenant_isolation" ON compliance_check_log
  USING (tenant_id = current_setting('app.current_org_id', true)::uuid);

-- Indexes
CREATE INDEX idx_compliance_check_log_tenant ON compliance_check_log(tenant_id, created_at DESC);
CREATE INDEX idx_compliance_check_log_user ON compliance_check_log(user_id, created_at DESC);

-- ============================================================
-- 3. Seed — 科学仪器行业合规规则 (13+ rules)
-- ============================================================
INSERT INTO compliance_rule (tenant_id, rule_code, rule_name, category, severity, check_type, pattern, description, replacement_suggestion)
VALUES
  -- 广告法: 绝对化用语
  (NULL, 'ADV_ABS_001', '禁止使用"最先进"', 'advertising_law', 'error', 'regex',
   '最先进',
   '《广告法》第九条禁止使用"最先进"等绝对化用语',
   '建议改为"先进""业内领先"等相对性描述'),

  (NULL, 'ADV_ABS_002', '禁止使用"最好"', 'advertising_law', 'error', 'regex',
   '最好',
   '《广告法》第九条禁止使用"最好"等绝对化用语',
   '建议改为"优秀""卓越"等相对性描述'),

  (NULL, 'ADV_ABS_003', '禁止使用"第一"', 'advertising_law', 'error', 'regex',
   '第一|No\\.?\\s*1',
   '《广告法》第九条禁止使用"第一""No.1"等排序性绝对化用语',
   '建议删除或改为"知名""广受认可"等表述'),

  (NULL, 'ADV_ABS_004', '禁止使用"唯一/独家"', 'advertising_law', 'error', 'regex',
   '唯一|独一无二|独家|仅此一家',
   '《广告法》第九条禁止使用"唯一""独家"等排他性绝对化用语',
   '建议改为"特有""差异化"等描述'),

  (NULL, 'ADV_ABS_005', '禁止使用"国家级/世界级"', 'advertising_law', 'error', 'regex',
   '国家级|世界级|全球领先|世界领先',
   '《广告法》第九条禁止使用"国家级""世界级"等绝对化用语',
   '建议改为"业内知名""通过XX认证"等描述'),

  (NULL, 'ADV_PROMISE_001', '禁止虚假保证承诺', 'advertising_law', 'error', 'regex',
   '100%准确|零误差|绝对精准|永不出错|万无一失|保证达标',
   '《广告法》第四条禁止含有虚假或引人误解的内容，不得有保证性承诺',
   '建议改为"致力于""力求""在标准范围内"等描述'),

  -- 计量法: 精度声明需引用证书
  (NULL, 'MET_CERT_001', '精度声明需计量证书', 'metrology_law', 'warning', 'regex',
   '(精度|准确度|测量不确定度).{0,20}[0-9]',
   '《计量法》要求涉及精度、准确度的声明须有对应计量检定/校准证书支撑',
   '建议补充计量检定证书编号或校准报告引用，例如"精度 ±0.1%（依据XX校准证书）"'),

  (NULL, 'MET_CERT_002', '非法定计量单位', 'metrology_law', 'warning', 'regex',
   '(?<![A-Za-z])(ppm|ppb|PPM|PPB)(?![A-Za-z])',
   '《计量法》要求使用国家法定计量单位，ppm/ppb为非法定单位',
   '建议改为 mg/L、μg/L 等法定计量单位，或括号内附注法定单位'),

  -- 招投标法: 标书必备章节
  (NULL, 'BID_SEC_001', '标书缺少必备章节', 'bidding_law', 'error', 'keyword',
   '投标保证金,法定代表人授权委托书,投标函,技术偏离表,商务偏离表',
   '《招标投标法实施条例》要求投标文件应包含投标保证金、授权委托书、投标函、偏离表等必要章节，缺失可导致废标',
   '请逐项核查上述必备章节是否齐全，缺失任一项可能导致废标'),

  (NULL, 'BID_EXCL_001', '排他性技术参数', 'bidding_law', 'error', 'regex',
   '必须为.{2,10}品牌|仅限.{2,10}型号|指定.{2,10}厂家',
   '《招标投标法》第二十条禁止以不合理条件限制或排斥潜在投标人',
   '建议使用通用技术指标描述，删除品牌/型号限定'),

  -- 医疗器械: 注册证号要求
  (NULL, 'MED_REG_001', '医疗器械宣传缺少注册证号', 'medical_device', 'error', 'llm',
   NULL,
   '《医疗器械监督管理条例》要求医疗器械广告须标明注册证编号，宣传内容不得超出注册证核准范围',
   '请补充医疗器械注册证编号（格式：X械注准XXXXXXXXXX），并确认宣传内容与注册证一致'),

  (NULL, 'MED_SCOPE_001', '超适用范围描述', 'medical_device', 'warning', 'regex',
   '适用于所有|通用型医疗|可替代.*医疗器械|万能检测',
   '《医疗器械监督管理条例》禁止超出注册证核准适用范围进行宣传',
   '建议严格按照注册证核准的适用范围描述产品用途'),

  -- 行业标准: 科学仪器特有
  (NULL, 'IND_STD_001', '缺少执行标准号', 'industry_standard', 'info', 'llm',
   NULL,
   '科学仪器产品技术文档宜标注执行标准（GB/T、JB/T、JJG/JJF等）',
   '建议在产品参数表中补充适用的国家标准、行业标准或计量检定规程编号')
ON CONFLICT DO NOTHING;
