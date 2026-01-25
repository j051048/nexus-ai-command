import { z } from 'zod';

export const salesLeadSchema = z.object({
    id: z.string().uuid(),
    name: z.string(),
    company: z.string().nullable().default('Unknown'),
    title: z.string().nullable().default('Unknown'),
    score: z.number().int().default(0),
    stage: z.enum(['new', 'contacted', 'qualified', 'proposal', 'negotiation', 'won', 'lost']).default('new'),
    ai_suggestion: z.string().nullable().default('AI 推荐跟进'),
    win_probability: z.number().int().min(0).max(100).default(0),
    last_contact: z.string().nullable().optional(),
    created_at: z.string().optional(),
    updated_at: z.string().optional(),
});

export type SalesLeadSafe = z.infer<typeof salesLeadSchema>;

export const approvalRequestSchema = z.object({
    id: z.string().uuid(),
    submitted_by: z.string().uuid(),
    type: z.string(),
    amount: z.number().nonnegative(),
    description: z.string().nullable().default('无描述'),
    status: z.enum(['pending', 'approved', 'rejected']).default('pending'),
    created_at: z.string(),
    submitted_at: z.string().optional(),
    submitter_name: z.string().optional().default('未知用户'),
    ai_reason: z.string().nullable().optional(),
    rejection_reason: z.string().nullable().optional(),
});

export type ApprovalRequestSafe = z.infer<typeof approvalRequestSchema>;
