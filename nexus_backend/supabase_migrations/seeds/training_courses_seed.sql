-- 培训课程种子数据
INSERT INTO training_courses (id, title, description, category, duration_minutes, difficulty) VALUES
('550e8400-e29b-41d4-a716-446655440001', 'Nexus AI 快速入门', '15分钟掌握核心功能', 'product', 15, 'easy'),
('550e8400-e29b-41d4-a716-446655440002', '制造业数字化转型实战', '从传统到智能的转型路径', 'industry', 45, 'medium'),
('550e8400-e29b-41d4-a716-446655440003', '数据安全与隐私保护', 'GDPR合规要点解析', 'security', 30, 'medium');

-- 测验题库示例
INSERT INTO quiz_questions (course_id, question_text, question_type, options, explanation, difficulty) VALUES
(
  '550e8400-e29b-41d4-a716-446655440001',
  'Nexus AI 的核心交互方式是什么？',
  'single_choice',
  '[
    {"text": "传统表单填写", "is_correct": false},
    {"text": "AI 对话交互", "is_correct": true},
    {"text": "命令行操作", "is_correct": false},
    {"text": "拖拽式界面", "is_correct": false}
  ]'::jsonb,
  'Nexus AI 采用 AI-First 设计理念，核心交互方式是自然语言对话。',
  'easy'
);
