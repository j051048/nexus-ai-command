# 行业模板库

## 模板分类

### 1. 制造业模板
- 生产订单审批流程
- 设备维护工单流程
- 质量检验流程
- 供应商管理流程

### 2. 零售业模板
- 促销活动审批流程
- 库存调拨流程
- 会员积分管理流程
- 退换货处理流程

### 3. 金融业模板
- 贷款审批流程
- 风险评估流程
- 合规审查流程
- 客户尽职调查流程

## 模板数据结构

```sql
-- 添加行业分类字段
ALTER TABLE workflow_templates 
ADD COLUMN industry VARCHAR(50), -- manufacturing, retail, finance, etc.
ADD COLUMN tags TEXT[]; -- 标签数组

-- 创建行业模板索引
CREATE INDEX idx_workflow_templates_industry ON workflow_templates(industry);
```

## 模板安装流程

1. 用户选择行业模板
2. 系统复制模板到用户组织
3. 用户可自定义修改
4. 激活使用

详细模板定义见 `industry_templates/`
