/**
 * AI 培训中心
 * 课程浏览、在线学习、测验与进度追踪
 */

import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import {
  GraduationCap,
  TrendingUp,
  Package,
  BookOpen,
  CheckCircle2,
  XCircle,
  ArrowLeft,
  Play,
  Trophy,
  Clock,
  Star,
  ChevronRight,
  BarChart3,
  Loader2,
  Award,
} from 'lucide-react';
import { toast } from 'sonner';

// 难度配置
const DIFFICULTY_CONFIG: Record<string, { label: string; color: string }> = {
  beginner: { label: '入门', color: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
  intermediate: { label: '进阶', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
  advanced: { label: '高级', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' },
};

// 图标映射
const ICON_MAP: Record<string, React.ElementType> = {
  'graduation-cap': GraduationCap,
  'trending-up': TrendingUp,
  'package': Package,
  'book-open': BookOpen,
};

interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  answer: number;
  explanation: string;
}

interface Module {
  id: string;
  title: string;
  content: string;
  quiz: QuizQuestion[];
}

interface Course {
  id: string;
  title: string;
  description: string;
  category: string;
  duration: string;
  difficulty: string;
  cover_icon: string;
  modules: Module[];
}

interface ModuleProgress {
  completed: boolean;
  score: number | null;
}

// 内置课程数据
const COURSES: Course[] = [
  {
    id: 'onboarding',
    title: '新员工入职指南',
    description: '了解公司基本流程、系统使用方法',
    category: '入职培训',
    duration: '2小时',
    difficulty: 'beginner',
    cover_icon: 'graduation-cap',
    modules: [
      {
        id: 'm1',
        title: '系统登录与个人设置',
        content: '## 系统登录与个人设置\n\n### 1. 首次登录\n- 使用管理员提供的邮箱和初始密码登录系统\n- 首次登录后请立即修改密码\n- 建议开启两步验证以保障账户安全\n\n### 2. 个人资料设置\n- 上传头像、填写部门和联系方式\n- 设置通知偏好（邮件/企业微信/钉钉）\n\n### 3. 工作台定制\n- 根据岗位需要配置常用功能快捷入口\n- 设置日程提醒和待办事项通知',
        quiz: [
          { id: 'q1', question: '首次登录后应该做的第一件事是什么？', options: ['浏览系统功能', '修改初始密码', '设置头像', '查看公告'], answer: 1, explanation: '为保障账户安全，首次登录后应立即修改密码。' },
          { id: 'q2', question: '以下哪种方式可以增强账户安全性？', options: ['使用简单密码', '共享账号', '开启两步验证', '关闭通知'], answer: 2, explanation: '开启两步验证可以有效防止账号被盗用。' },
        ],
      },
      {
        id: 'm2',
        title: '审批流程使用',
        content: '## 审批流程使用\n\n### 1. 发起审批\n- 在 OA 中心选择对应的审批类型\n- 填写审批表单，附上必要的附件\n- 系统会根据规则自动匹配审批链\n\n### 2. 审批处理\n- 收到审批通知后及时处理\n- 可以同意、拒绝或转交他人\n- AI 助手会提供审批建议参考\n\n### 3. 审批查询\n- 在「我的审批」中查看所有审批记录\n- 支持按状态、类型、时间筛选',
        quiz: [
          { id: 'q1', question: '系统如何确定审批流转路径？', options: ['手动指定', '随机分配', '根据规则自动匹配', '由AI决定'], answer: 2, explanation: '系统根据预设的审批规则自动匹配对应的审批链。' },
        ],
      },
      {
        id: 'm3',
        title: '文档与知识库',
        content: '## 文档与知识库\n\n### 1. 文档管理\n- 支持上传 PDF、Word、Excel 等常见格式\n- 文件自动归类到对应的项目或部门\n- 支持版本管理和协作编辑\n\n### 2. 知识库检索\n- 使用 AI 语义搜索快速定位相关文档\n- 支持自然语言提问，系统自动摘取答案\n\n### 3. 知识沉淀\n- 项目结项后自动生成知识摘要\n- 团队可以共建部门知识库',
        quiz: [
          { id: 'q1', question: '知识库的搜索方式是什么？', options: ['仅支持关键词搜索', 'AI 语义搜索', '仅支持文件名搜索', '不支持搜索'], answer: 1, explanation: '系统使用 AI 语义搜索技术，支持自然语言提问。' },
        ],
      },
      {
        id: 'm4',
        title: 'AI 助手使用技巧',
        content: '## AI 助手使用技巧\n\n### 1. 对话式交互\n- 用自然语言描述需求，AI 会自动理解并执行\n- 例如：「帮我查一下本月销售数据」「总结这份报告」\n\n### 2. 智能工具调用\n- AI 可以自动调用系统功能完成任务\n- 包括：创建项目、发起审批、查询数据等\n\n### 3. 提问技巧\n- 问题越具体，回答越精准\n- 可以提供上下文信息辅助 AI 理解\n- 多轮对话中 AI 会记住上下文',
        quiz: [
          { id: 'q1', question: '如何让 AI 助手给出更精准的回答？', options: ['使用简短的问题', '提出具体的问题并提供上下文', '重复提问', '使用英文提问'], answer: 1, explanation: '问题越具体、上下文越充分，AI 回答越精准。' },
        ],
      },
    ],
  },
  {
    id: 'sales_basics',
    title: '销售基础培训',
    description: '掌握销售技巧和客户管理方法',
    category: '销售培训',
    duration: '3小时',
    difficulty: 'intermediate',
    cover_icon: 'trending-up',
    modules: [
      {
        id: 'm1',
        title: '客户画像与分析',
        content: '## 客户画像与分析\n\n### 1. 客户分级\n- A级客户：年营收 > 1000万，决策周期短\n- B级客户：年营收 500-1000万，有明确需求\n- C级客户：年营收 < 500万，需培育\n\n### 2. 需求挖掘\n- 使用 SPIN 提问法了解客户痛点\n- Situation（现状） -> Problem（问题） -> Implication（影响） -> Need-payoff（需求）\n\n### 3. AI 辅助分析\n- 系统会自动分析客户行为数据\n- 推荐最佳跟进策略和时机',
        quiz: [
          { id: 'q1', question: 'SPIN 中的 I 代表什么？', options: ['Information', 'Implication', 'Implementation', 'Integration'], answer: 1, explanation: 'I 代表 Implication（影响），用于让客户意识到问题的严重性。' },
        ],
      },
      {
        id: 'm2',
        title: '销售谈判技巧',
        content: '## 销售谈判技巧\n\n### 1. 谈判准备\n- 了解客户预算范围和决策流程\n- 准备多套方案以应对不同情况\n- 明确己方的底线和让步空间\n\n### 2. 常见谈判策略\n- 锚定效应：先报合理高价，再适当让步\n- 互惠原则：提供额外价值换取承诺\n- 稀缺性：合理利用限时优惠\n\n### 3. 成交信号识别\n- 客户开始询问细节和交付时间\n- 主动讨论付款方式\n- 要求提供参考案例',
        quiz: [
          { id: 'q1', question: '客户开始询问交付细节通常意味着什么？', options: ['对产品不满意', '表示成交信号', '想要压价', '纯属好奇'], answer: 1, explanation: '客户主动询问交付细节和付款方式通常是积极的成交信号。' },
        ],
      },
      {
        id: 'm3',
        title: 'CRM 系统使用',
        content: '## CRM 系统使用\n\n### 1. 客户录入\n- 新客户需完整填写基本信息和联系方式\n- 设置跟进计划和提醒\n\n### 2. 跟进记录\n- 每次沟通后及时记录跟进内容\n- 系统支持通话录音自动转写和摘要\n\n### 3. 数据分析\n- 查看个人销售漏斗和转化率\n- AI 自动分析丢单原因和改进建议',
        quiz: [
          { id: 'q1', question: '跟进记录的最佳时机是什么？', options: ['每周统一录入', '每次沟通后及时记录', '月底补录', '领导要求时'], answer: 1, explanation: '每次沟通后及时记录可以确保信息准确，避免遗忘重要细节。' },
        ],
      },
    ],
  },
  {
    id: 'product_knowledge',
    title: '产品知识培训',
    description: '深入了解公司产品功能和竞争优势',
    category: '产品培训',
    duration: '2.5小时',
    difficulty: 'intermediate',
    cover_icon: 'package',
    modules: [
      {
        id: 'm1',
        title: '产品架构总览',
        content: '## 产品架构总览\n\n### 1. 核心模块\n- AI 智能助手：对话式交互、自然语言处理\n- 办公自动化：审批流、文档管理、日程\n- 销售管理：CRM、销售漏斗、业绩追踪\n- 数据分析：BI 报表、智能预警\n\n### 2. 技术优势\n- 基于大模型的语义理解能力\n- 本地化部署支持数据安全\n- 开放 API 支持第三方集成',
        quiz: [
          { id: 'q1', question: '产品的技术优势不包括以下哪项？', options: ['语义理解', '本地化部署', '开放 API', '硬件销售'], answer: 3, explanation: '产品的技术优势包括语义理解、本地化部署和开放 API，不涉及硬件销售。' },
        ],
      },
      {
        id: 'm2',
        title: '竞品分析',
        content: '## 竞品分析\n\n### 1. 主要竞品\n- 飞书：注重协作，但 AI 能力较弱\n- 钉钉：用户基数大，但定制化不足\n- 企业微信：社交生态强，但功能较分散\n\n### 2. 差异化优势\n- AI 原生：从底层设计就围绕 AI 构建\n- 行业深度：针对中小企业痛点定制\n- 价格竞争力：灵活的按需付费模式',
        quiz: [
          { id: 'q1', question: '我们产品相比竞品的核心差异化优势是什么？', options: ['用户数量多', 'AI 原生设计', '价格最低', '功能最全'], answer: 1, explanation: 'AI 原生设计是核心差异化优势，从底层围绕 AI 构建整个产品。' },
        ],
      },
    ],
  },
];

// 简易 Markdown 渲染器
function SimpleMarkdown({ content }: { content: string }) {
  const lines = content.split('\n');
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      {lines.map((line, i) => {
        if (line.startsWith('## ')) {
          return <h2 key={i} className="text-lg font-bold mt-4 mb-2">{line.slice(3)}</h2>;
        }
        if (line.startsWith('### ')) {
          return <h3 key={i} className="text-base font-semibold mt-3 mb-1">{line.slice(4)}</h3>;
        }
        if (line.startsWith('- ')) {
          return (
            <div key={i} className="flex gap-2 ml-4 my-0.5">
              <span className="text-primary mt-1 shrink-0">&#8226;</span>
              <span className="text-sm text-muted-foreground">{line.slice(2)}</span>
            </div>
          );
        }
        if (line.trim() === '') {
          return <div key={i} className="h-2" />;
        }
        return <p key={i} className="text-sm text-muted-foreground">{line}</p>;
      })}
    </div>
  );
}

export function TrainingCenter() {
  // State
  const [progress, setProgress] = useState<Record<string, Record<string, ModuleProgress>>>({});
  const [activeCourse, setActiveCourse] = useState<Course | null>(null);
  const [activeModule, setActiveModule] = useState<Module | null>(null);
  const [quizMode, setQuizMode] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, number>>({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [quizResults, setQuizResults] = useState<{ score: number; correct: number; total: number; results: Array<{ id: string; is_correct: boolean; explanation: string }> } | null>(null);

  // 计算课程进度
  const getCourseProgress = (courseId: string, moduleCount: number) => {
    const courseProgress = progress[courseId] || {};
    const completed = Object.values(courseProgress).filter((m) => m.completed).length;
    return moduleCount > 0 ? Math.round((completed / moduleCount) * 100) : 0;
  };

  const getModuleCompleted = (courseId: string, moduleId: string) => {
    return progress[courseId]?.[moduleId]?.completed || false;
  };

  const getModuleScore = (courseId: string, moduleId: string) => {
    return progress[courseId]?.[moduleId]?.score ?? null;
  };

  // 总体统计
  const stats = useMemo(() => {
    let totalModules = 0;
    let completedModules = 0;
    let totalScore = 0;
    let scoredModules = 0;

    COURSES.forEach((course) => {
      totalModules += course.modules.length;
      const cp = progress[course.id] || {};
      Object.values(cp).forEach((m) => {
        if (m.completed) completedModules++;
        if (m.score !== null) {
          totalScore += m.score;
          scoredModules++;
        }
      });
    });

    return {
      totalCourses: COURSES.length,
      totalModules,
      completedModules,
      overallProgress: totalModules > 0 ? Math.round((completedModules / totalModules) * 100) : 0,
      avgScore: scoredModules > 0 ? Math.round(totalScore / scoredModules) : 0,
    };
  }, [progress]);

  // 进入课程
  const enterCourse = (course: Course) => {
    setActiveCourse(course);
    setActiveModule(null);
    setQuizMode(false);
    setQuizSubmitted(false);
    setQuizResults(null);
  };

  // 进入模块
  const enterModule = (mod: Module) => {
    setActiveModule(mod);
    setQuizMode(false);
    setQuizSubmitted(false);
    setQuizResults(null);
    setQuizAnswers({});
  };

  // 开始测验
  const startQuiz = () => {
    setQuizMode(true);
    setQuizSubmitted(false);
    setQuizResults(null);
    setQuizAnswers({});
  };

  // 提交测验
  const submitQuiz = () => {
    if (!activeCourse || !activeModule) return;

    const quiz = activeModule.quiz;
    let correct = 0;
    const results = quiz.map((q) => {
      const isCorrect = quizAnswers[q.id] === q.answer;
      if (isCorrect) correct++;
      return { id: q.id, is_correct: isCorrect, explanation: q.explanation };
    });

    const score = quiz.length > 0 ? Math.round((correct / quiz.length) * 100) : 0;

    setQuizResults({ score, correct, total: quiz.length, results });
    setQuizSubmitted(true);

    // 保存进度
    setProgress((prev) => ({
      ...prev,
      [activeCourse.id]: {
        ...(prev[activeCourse.id] || {}),
        [activeModule.id]: { completed: true, score },
      },
    }));

    if (score >= 60) {
      toast.success(`测验通过! 得分: ${score}分`);
    } else {
      toast.error(`未通过，得分: ${score}分，需要60分以上`);
    }
  };

  // 返回按钮
  const goBack = () => {
    if (quizMode) {
      setQuizMode(false);
      setQuizSubmitted(false);
      setQuizResults(null);
    } else if (activeModule) {
      setActiveModule(null);
    } else {
      setActiveCourse(null);
    }
  };

  // 渲染课程列表
  const renderCourseList = () => (
    <div className="space-y-6">
      {/* 统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900">
              <BookOpen className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.totalCourses}</p>
              <p className="text-xs text-muted-foreground">课程总数</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900">
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.completedModules}/{stats.totalModules}</p>
              <p className="text-xs text-muted-foreground">已完成模块</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900">
              <BarChart3 className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.overallProgress}%</p>
              <p className="text-xs text-muted-foreground">总体进度</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-orange-100 dark:bg-orange-900">
              <Trophy className="h-5 w-5 text-orange-600 dark:text-orange-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.avgScore || '--'}</p>
              <p className="text-xs text-muted-foreground">平均成绩</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 课程卡片网格 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {COURSES.map((course) => {
          const IconComp = ICON_MAP[course.cover_icon] || BookOpen;
          const prog = getCourseProgress(course.id, course.modules.length);
          const diff = DIFFICULTY_CONFIG[course.difficulty] || DIFFICULTY_CONFIG.beginner;
          const completedCount = Object.values(progress[course.id] || {}).filter((m) => m.completed).length;

          return (
            <Card
              key={course.id}
              className="cursor-pointer hover:shadow-lg transition-all group"
              onClick={() => enterCourse(course)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="p-3 rounded-xl bg-primary/10 group-hover:bg-primary/20 transition-colors">
                    <IconComp className="h-6 w-6 text-primary" />
                  </div>
                  <Badge className={cn('text-[10px]', diff.color)}>{diff.label}</Badge>
                </div>
                <CardTitle className="text-base mt-3">{course.title}</CardTitle>
                <CardDescription className="text-xs">{course.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {course.duration}
                  </span>
                  <span className="flex items-center gap-1">
                    <BookOpen className="h-3 w-3" />
                    {course.modules.length} 模块
                  </span>
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    {completedCount} 完成
                  </span>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">学习进度</span>
                    <span className="font-medium">{prog}%</span>
                  </div>
                  <Progress value={prog} className="h-1.5" />
                </div>

                <Button variant="ghost" size="sm" className="w-full text-xs justify-between group-hover:bg-primary/5">
                  {prog === 100 ? '复习课程' : prog > 0 ? '继续学习' : '开始学习'}
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );

  // 渲染课程详情（模块列表）
  const renderCourseDetail = () => {
    if (!activeCourse) return null;
    const IconComp = ICON_MAP[activeCourse.cover_icon] || BookOpen;

    return (
      <div className="space-y-6">
        {/* 课程头部 */}
        <Card>
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-primary/10 shrink-0">
                <IconComp className="h-8 w-8 text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-xl font-bold">{activeCourse.title}</h2>
                <p className="text-sm text-muted-foreground mt-1">{activeCourse.description}</p>
                <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" />
                    {activeCourse.duration}
                  </span>
                  <Badge className={cn('text-xs', DIFFICULTY_CONFIG[activeCourse.difficulty]?.color)}>
                    {DIFFICULTY_CONFIG[activeCourse.difficulty]?.label}
                  </Badge>
                </div>
                <div className="mt-3">
                  <Progress value={getCourseProgress(activeCourse.id, activeCourse.modules.length)} className="h-2" />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 模块列表 */}
        <div className="space-y-3">
          {activeCourse.modules.map((mod, idx) => {
            const completed = getModuleCompleted(activeCourse.id, mod.id);
            const score = getModuleScore(activeCourse.id, mod.id);

            return (
              <Card
                key={mod.id}
                className={cn(
                  'cursor-pointer hover:shadow-md transition-all',
                  completed && 'border-green-200 dark:border-green-800'
                )}
                onClick={() => enterModule(mod)}
              >
                <CardContent className="p-4 flex items-center gap-4">
                  <div className={cn(
                    'w-10 h-10 rounded-full flex items-center justify-center shrink-0 text-sm font-bold',
                    completed
                      ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                      : 'bg-muted text-muted-foreground'
                  )}>
                    {completed ? <CheckCircle2 className="h-5 w-5" /> : idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm">{mod.title}</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {mod.quiz.length} 道测验题
                      {score !== null && (
                        <span className={cn('ml-2', score >= 60 ? 'text-green-600' : 'text-red-500')}>
                          得分: {score}
                        </span>
                      )}
                    </p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    );
  };

  // 渲染模块内容
  const renderModuleContent = () => {
    if (!activeCourse || !activeModule) return null;

    if (quizMode) {
      return renderQuiz();
    }

    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{activeModule.title}</CardTitle>
            <CardDescription>
              {activeCourse.title} - 模块 {activeCourse.modules.findIndex((m) => m.id === activeModule.id) + 1}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="max-h-[60vh]">
              <SimpleMarkdown content={activeModule.content} />
            </ScrollArea>
          </CardContent>
        </Card>

        {activeModule.quiz.length > 0 && (
          <div className="flex justify-center">
            <Button onClick={startQuiz} size="lg" className="gap-2">
              <Play className="h-4 w-4" />
              开始测验 ({activeModule.quiz.length} 题)
            </Button>
          </div>
        )}
      </div>
    );
  };

  // 渲染测验
  const renderQuiz = () => {
    if (!activeCourse || !activeModule) return null;
    const quiz = activeModule.quiz;

    return (
      <div className="space-y-6">
        {/* 测验结果 */}
        {quizSubmitted && quizResults && (
          <Card className={cn(
            'border-2',
            quizResults.score >= 60 ? 'border-green-300 dark:border-green-700' : 'border-red-300 dark:border-red-700'
          )}>
            <CardContent className="p-6 text-center space-y-3">
              <div className={cn(
                'w-16 h-16 rounded-full mx-auto flex items-center justify-center',
                quizResults.score >= 60
                  ? 'bg-green-100 dark:bg-green-900'
                  : 'bg-red-100 dark:bg-red-900'
              )}>
                {quizResults.score >= 60 ? (
                  <Trophy className="h-8 w-8 text-green-600 dark:text-green-400" />
                ) : (
                  <XCircle className="h-8 w-8 text-red-500" />
                )}
              </div>
              <h3 className="text-xl font-bold">
                {quizResults.score >= 60 ? '恭喜通过!' : '继续加油!'}
              </h3>
              <p className="text-3xl font-bold text-primary">{quizResults.score}分</p>
              <p className="text-sm text-muted-foreground">
                共 {quizResults.total} 题，答对 {quizResults.correct} 题
              </p>
            </CardContent>
          </Card>
        )}

        {/* 题目列表 */}
        {quiz.map((q, qIdx) => {
          const result = quizResults?.results.find((r) => r.id === q.id);

          return (
            <Card key={q.id} className={cn(
              quizSubmitted && result && (result.is_correct ? 'border-green-200 dark:border-green-800' : 'border-red-200 dark:border-red-800')
            )}>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
                    {qIdx + 1}
                  </span>
                  {q.question}
                  {quizSubmitted && result && (
                    result.is_correct
                      ? <CheckCircle2 className="h-4 w-4 text-green-500 ml-auto shrink-0" />
                      : <XCircle className="h-4 w-4 text-red-500 ml-auto shrink-0" />
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <RadioGroup
                  value={quizAnswers[q.id]?.toString()}
                  onValueChange={(val) => {
                    if (!quizSubmitted) {
                      setQuizAnswers((prev) => ({ ...prev, [q.id]: parseInt(val) }));
                    }
                  }}
                  disabled={quizSubmitted}
                  className="space-y-2"
                >
                  {q.options.map((opt, optIdx) => (
                    <div key={optIdx} className={cn(
                      'flex items-center gap-3 p-2.5 rounded-lg border transition-colors',
                      !quizSubmitted && quizAnswers[q.id] === optIdx && 'border-primary bg-primary/5',
                      quizSubmitted && optIdx === q.answer && 'border-green-500 bg-green-50 dark:bg-green-950',
                      quizSubmitted && quizAnswers[q.id] === optIdx && optIdx !== q.answer && 'border-red-500 bg-red-50 dark:bg-red-950',
                    )}>
                      <RadioGroupItem value={optIdx.toString()} id={`${q.id}-${optIdx}`} />
                      <Label htmlFor={`${q.id}-${optIdx}`} className="text-sm cursor-pointer flex-1">
                        {opt}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>

                {quizSubmitted && result && (
                  <div className={cn(
                    'mt-3 p-3 rounded-lg text-sm',
                    result.is_correct ? 'bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300' : 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300'
                  )}>
                    {result.explanation}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}

        {!quizSubmitted && (
          <div className="flex justify-center">
            <Button
              onClick={submitQuiz}
              size="lg"
              className="gap-2"
              disabled={Object.keys(quizAnswers).length < quiz.length}
            >
              <Award className="h-4 w-4" />
              提交答案 ({Object.keys(quizAnswers).length}/{quiz.length})
            </Button>
          </div>
        )}

        {quizSubmitted && (
          <div className="flex justify-center gap-3">
            <Button variant="outline" onClick={goBack}>
              返回模块
            </Button>
            {quizResults && quizResults.score < 60 && (
              <Button onClick={startQuiz}>
                重新测验
              </Button>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* 页面标题 */}
      <div className="flex items-center gap-3">
        {(activeCourse || activeModule) && (
          <Button variant="ghost" size="icon" onClick={goBack}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
        )}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <GraduationCap className="h-6 w-6 text-primary" />
            培训中心
          </h1>
          <p className="text-muted-foreground mt-0.5 text-sm">
            {activeCourse
              ? activeModule
                ? `${activeCourse.title} / ${activeModule.title}`
                : activeCourse.title
              : '在线学习，提升技能'}
          </p>
        </div>
      </div>

      {/* 内容区域 */}
      {!activeCourse && renderCourseList()}
      {activeCourse && !activeModule && renderCourseDetail()}
      {activeCourse && activeModule && renderModuleContent()}
    </div>
  );
}

export default TrainingCenter;
