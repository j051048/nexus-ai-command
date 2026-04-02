/**
 * Zod schemas 单元测试
 *
 * 覆盖：salesLeadSchema / approvalRequestSchema 的正常解析、默认值、边界值、无效输入
 */
import { describe, it, expect } from 'vitest';
import { salesLeadSchema, approvalRequestSchema } from '@/lib/schemas';

describe('salesLeadSchema', () => {
  const validLead = {
    id: '550e8400-e29b-41d4-a716-446655440000',
    name: '张三',
    company: 'Acme Corp',
    title: 'CTO',
    score: 85,
    stage: 'qualified' as const,
    ai_suggestion: '建议跟进',
    win_probability: 70,
  };

  it('解析完整有效数据', () => {
    const result = salesLeadSchema.safeParse(validLead);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.name).toBe('张三');
      expect(result.data.stage).toBe('qualified');
    }
  });

  it('缺失可选字段时填充默认值', () => {
    const minimal = { id: '550e8400-e29b-41d4-a716-446655440000', name: '李四' };
    const result = salesLeadSchema.safeParse(minimal);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.company).toBe('Unknown');
      expect(result.data.score).toBe(0);
      expect(result.data.stage).toBe('new');
      expect(result.data.win_probability).toBe(0);
      expect(result.data.ai_suggestion).toBe('AI 推荐跟进');
    }
  });

  it('无效 UUID 拒绝', () => {
    const result = salesLeadSchema.safeParse({ ...validLead, id: 'not-uuid' });
    expect(result.success).toBe(false);
  });

  it('win_probability 超出 0-100 范围拒绝', () => {
    expect(salesLeadSchema.safeParse({ ...validLead, win_probability: -1 }).success).toBe(false);
    expect(salesLeadSchema.safeParse({ ...validLead, win_probability: 101 }).success).toBe(false);
  });

  it('无效 stage 枚举拒绝', () => {
    const result = salesLeadSchema.safeParse({ ...validLead, stage: 'invalid_stage' });
    expect(result.success).toBe(false);
  });

  it('company 为 null 时接受', () => {
    const result = salesLeadSchema.safeParse({ ...validLead, company: null });
    expect(result.success).toBe(true);
  });

  it('score 必须为整数', () => {
    const result = salesLeadSchema.safeParse({ ...validLead, score: 85.5 });
    expect(result.success).toBe(false);
  });
});

describe('approvalRequestSchema', () => {
  const validApproval = {
    id: '550e8400-e29b-41d4-a716-446655440000',
    submitted_by: '550e8400-e29b-41d4-a716-446655440001',
    type: 'expense',
    amount: 5000,
    description: '差旅报销',
    status: 'pending' as const,
    created_at: '2026-01-01T00:00:00Z',
  };

  it('解析完整有效数据', () => {
    const result = approvalRequestSchema.safeParse(validApproval);
    expect(result.success).toBe(true);
  });

  it('默认值填充', () => {
    const result = approvalRequestSchema.safeParse(validApproval);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.submitter_name).toBe('未知用户');
      expect(result.data.submitted_via).toBe('direct');
    }
  });

  it('amount 不能为负数', () => {
    const result = approvalRequestSchema.safeParse({ ...validApproval, amount: -100 });
    expect(result.success).toBe(false);
  });

  it('无效 status 枚举拒绝', () => {
    const result = approvalRequestSchema.safeParse({ ...validApproval, status: 'cancelled' });
    expect(result.success).toBe(false);
  });

  it('submitted_via 枚举验证', () => {
    expect(approvalRequestSchema.safeParse({ ...validApproval, submitted_via: 'ai_assistant' }).success).toBe(true);
    expect(approvalRequestSchema.safeParse({ ...validApproval, submitted_via: 'api' }).success).toBe(true);
    expect(approvalRequestSchema.safeParse({ ...validApproval, submitted_via: 'unknown' }).success).toBe(false);
  });

  it('on_behalf_of 可为 null', () => {
    const result = approvalRequestSchema.safeParse({ ...validApproval, on_behalf_of: null });
    expect(result.success).toBe(true);
  });

  it('description 为 null 时允许通过（nullable）', () => {
    const result = approvalRequestSchema.safeParse({ ...validApproval, description: null });
    expect(result.success).toBe(true);
    if (result.success) {
      // .nullable() 允许 null，.default() 仅对 undefined 生效
      expect(result.data.description).toBeNull();
    }
  });

  it('description 为 undefined 时默认为 "无描述"', () => {
    const { description, ...withoutDesc } = validApproval;
    const result = approvalRequestSchema.safeParse(withoutDesc);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.description).toBe('无描述');
    }
  });
});
