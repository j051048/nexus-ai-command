# 培训中心内容框架

## 课程分类

### 1. 产品使用培训
- 基础操作指南
- AI 对话技巧
- 高级功能使用

### 2. 行业最佳实践
- 制造业数字化转型
- 零售业客户管理
- 金融业合规管理

### 3. 安全意识培训
- 数据安全基础
- GDPR 合规要求
- 密码安全管理

## 测验题库结构

```sql
-- 添加到新的迁移文件
CREATE TABLE quiz_questions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_id UUID REFERENCES training_courses(id),
  question_text TEXT NOT NULL,
  question_type VARCHAR(20) NOT NULL, -- single_choice, multiple_choice, true_false
  options JSONB, -- [{text: "选项A", is_correct: true}, ...]
  explanation TEXT,
  difficulty VARCHAR(20), -- easy, medium, hard
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_quiz_attempts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id),
  quiz_id UUID REFERENCES quiz_questions(id),
  selected_answer JSONB,
  is_correct BOOLEAN,
  attempted_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 示例课程内容

见 `training_courses_seed.sql`
