"""
AI 培训助手服务

提供:
- 预置培训课程管理
- 用户学习进度追踪
- 测验问答系统
- 成绩统计
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class TrainingService:
    """AI 培训助手服务"""

    # 预置培训课程
    COURSES: list[dict[str, Any]] = [
        {
            "id": "onboarding",
            "title": "新员工入职指南",
            "description": "了解公司基本流程、系统使用方法",
            "category": "入职培训",
            "duration": "2小时",
            "difficulty": "beginner",
            "cover_icon": "graduation-cap",
            "modules": [
                {
                    "id": "m1",
                    "title": "系统登录与个人设置",
                    "content": (
                        "## 系统登录与个人设置\n\n"
                        "### 1. 首次登录\n"
                        "- 使用管理员提供的邮箱和初始密码登录系统\n"
                        "- 首次登录后请立即修改密码\n"
                        "- 建议开启两步验证以保障账户安全\n\n"
                        "### 2. 个人资料设置\n"
                        "- 上传头像、填写部门和联系方式\n"
                        "- 设置通知偏好（邮件/企业微信/钉钉）\n\n"
                        "### 3. 工作台定制\n"
                        "- 根据岗位需要配置常用功能快捷入口\n"
                        "- 设置日程提醒和待办事项通知"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "首次登录后应该做的第一件事是什么？",
                            "options": [
                                "浏览系统功能",
                                "修改初始密码",
                                "设置头像",
                                "查看公告",
                            ],
                            "answer": 1,
                            "explanation": "为保障账户安全，首次登录后应立即修改密码。",
                        },
                        {
                            "id": "q2",
                            "question": "以下哪种方式可以增强账户安全性？",
                            "options": [
                                "使用简单密码",
                                "共享账号",
                                "开启两步验证",
                                "关闭通知",
                            ],
                            "answer": 2,
                            "explanation": "开启两步验证可以有效防止账号被盗用。",
                        },
                    ],
                },
                {
                    "id": "m2",
                    "title": "审批流程使用",
                    "content": (
                        "## 审批流程使用\n\n"
                        "### 1. 发起审批\n"
                        "- 在 OA 中心选择对应的审批类型\n"
                        "- 填写审批表单，附上必要的附件\n"
                        "- 系统会根据规则自动匹配审批链\n\n"
                        "### 2. 审批处理\n"
                        "- 收到审批通知后及时处理\n"
                        "- 可以同意、拒绝或转交他人\n"
                        "- AI 助手会提供审批建议参考\n\n"
                        "### 3. 审批查询\n"
                        "- 在「我的审批」中查看所有审批记录\n"
                        "- 支持按状态、类型、时间筛选"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "系统如何确定审批流转路径？",
                            "options": [
                                "手动指定",
                                "随机分配",
                                "根据规则自动匹配",
                                "由AI决定",
                            ],
                            "answer": 2,
                            "explanation": "系统根据预设的审批规则自动匹配对应的审批链。",
                        },
                    ],
                },
                {
                    "id": "m3",
                    "title": "文档与知识库",
                    "content": (
                        "## 文档与知识库\n\n"
                        "### 1. 文档管理\n"
                        "- 支持上传 PDF、Word、Excel 等常见格式\n"
                        "- 文件自动归类到对应的项目或部门\n"
                        "- 支持版本管理和协作编辑\n\n"
                        "### 2. 知识库检索\n"
                        "- 使用 AI 语义搜索快速定位相关文档\n"
                        "- 支持自然语言提问，系统自动摘取答案\n\n"
                        "### 3. 知识沉淀\n"
                        "- 项目结项后自动生成知识摘要\n"
                        "- 团队可以共建部门知识库"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "知识库的搜索方式是什么？",
                            "options": [
                                "仅支持关键词搜索",
                                "AI 语义搜索",
                                "仅支持文件名搜索",
                                "不支持搜索",
                            ],
                            "answer": 1,
                            "explanation": "系统使用 AI 语义搜索技术，支持自然语言提问。",
                        },
                    ],
                },
                {
                    "id": "m4",
                    "title": "AI 助手使用技巧",
                    "content": (
                        "## AI 助手使用技巧\n\n"
                        "### 1. 对话式交互\n"
                        "- 用自然语言描述需求，AI 会自动理解并执行\n"
                        "- 例如：「帮我查一下本月销售数据」「总结这份报告」\n\n"
                        "### 2. 智能工具调用\n"
                        "- AI 可以自动调用系统功能完成任务\n"
                        "- 包括：创建项目、发起审批、查询数据等\n\n"
                        "### 3. 提问技巧\n"
                        "- 问题越具体，回答越精准\n"
                        "- 可以提供上下文信息辅助 AI 理解\n"
                        "- 多轮对话中 AI 会记住上下文"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "如何让 AI 助手给出更精准的回答？",
                            "options": [
                                "使用简短的问题",
                                "提出具体的问题并提供上下文",
                                "重复提问",
                                "使用英文提问",
                            ],
                            "answer": 1,
                            "explanation": "问题越具体、上下文越充分，AI 回答越精准。",
                        },
                    ],
                },
            ],
        },
        {
            "id": "sales_basics",
            "title": "销售基础培训",
            "description": "掌握销售技巧和客户管理方法",
            "category": "销售培训",
            "duration": "3小时",
            "difficulty": "intermediate",
            "cover_icon": "trending-up",
            "modules": [
                {
                    "id": "m1",
                    "title": "客户画像与分析",
                    "content": (
                        "## 客户画像与分析\n\n"
                        "### 1. 客户分级\n"
                        "- A级客户：年营收 > 1000万，决策周期短\n"
                        "- B级客户：年营收 500-1000万，有明确需求\n"
                        "- C级客户：年营收 < 500万，需培育\n\n"
                        "### 2. 需求挖掘\n"
                        "- 使用 SPIN 提问法了解客户痛点\n"
                        "- Situation（现状）→ Problem（问题）→ Implication（影响）→ Need-payoff（需求）\n\n"
                        "### 3. AI 辅助分析\n"
                        "- 系统会自动分析客户行为数据\n"
                        "- 推荐最佳跟进策略和时机"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "SPIN 中的 I 代表什么？",
                            "options": [
                                "Information",
                                "Implication",
                                "Implementation",
                                "Integration",
                            ],
                            "answer": 1,
                            "explanation": "I 代表 Implication（影响），用于让客户意识到问题的严重性。",
                        },
                    ],
                },
                {
                    "id": "m2",
                    "title": "销售谈判技巧",
                    "content": (
                        "## 销售谈判技巧\n\n"
                        "### 1. 谈判准备\n"
                        "- 了解客户预算范围和决策流程\n"
                        "- 准备多套方案以应对不同情况\n"
                        "- 明确己方的底线和让步空间\n\n"
                        "### 2. 常见谈判策略\n"
                        "- 锚定效应：先报合理高价，再适当让步\n"
                        "- 互惠原则：提供额外价值换取承诺\n"
                        "- 稀缺性：合理利用限时优惠\n\n"
                        "### 3. 成交信号识别\n"
                        "- 客户开始询问细节和交付时间\n"
                        "- 主动讨论付款方式\n"
                        "- 要求提供参考案例"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "客户开始询问交付细节通常意味着什么？",
                            "options": [
                                "对产品不满意",
                                "表示成交信号",
                                "想要压价",
                                "纯属好奇",
                            ],
                            "answer": 1,
                            "explanation": "客户主动询问交付细节和付款方式通常是积极的成交信号。",
                        },
                    ],
                },
                {
                    "id": "m3",
                    "title": "CRM 系统使用",
                    "content": (
                        "## CRM 系统使用\n\n"
                        "### 1. 客户录入\n"
                        "- 新客户需完整填写基本信息和联系方式\n"
                        "- 设置跟进计划和提醒\n\n"
                        "### 2. 跟进记录\n"
                        "- 每次沟通后及时记录跟进内容\n"
                        "- 系统支持通话录音自动转写和摘要\n\n"
                        "### 3. 数据分析\n"
                        "- 查看个人销售漏斗和转化率\n"
                        "- AI 自动分析丢单原因和改进建议"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "跟进记录的最佳时机是什么？",
                            "options": [
                                "每周统一录入",
                                "每次沟通后及时记录",
                                "月底补录",
                                "领导要求时",
                            ],
                            "answer": 1,
                            "explanation": "每次沟通后及时记录可以确保信息准确，避免遗忘重要细节。",
                        },
                    ],
                },
            ],
        },
        {
            "id": "product_knowledge",
            "title": "产品知识培训",
            "description": "深入了解公司产品功能和竞争优势",
            "category": "产品培训",
            "duration": "2.5小时",
            "difficulty": "intermediate",
            "cover_icon": "package",
            "modules": [
                {
                    "id": "m1",
                    "title": "产品架构总览",
                    "content": (
                        "## 产品架构总览\n\n"
                        "### 1. 核心模块\n"
                        "- AI 智能助手：对话式交互、自然语言处理\n"
                        "- 办公自动化：审批流、文档管理、日程\n"
                        "- 销售管理：CRM、销售漏斗、业绩追踪\n"
                        "- 数据分析：BI 报表、智能预警\n\n"
                        "### 2. 技术优势\n"
                        "- 基于大模型的语义理解能力\n"
                        "- 本地化部署支持数据安全\n"
                        "- 开放 API 支持第三方集成"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "产品的技术优势不包括以下哪项？",
                            "options": [
                                "语义理解",
                                "本地化部署",
                                "开放 API",
                                "硬件销售",
                            ],
                            "answer": 3,
                            "explanation": "产品的技术优势包括语义理解、本地化部署和开放 API，不涉及硬件销售。",
                        },
                    ],
                },
                {
                    "id": "m2",
                    "title": "竞品分析",
                    "content": (
                        "## 竞品分析\n\n"
                        "### 1. 主要竞品\n"
                        "- 飞书：注重协作，但 AI 能力较弱\n"
                        "- 钉钉：用户基数大，但定制化不足\n"
                        "- 企业微信：社交生态强，但功能较分散\n\n"
                        "### 2. 差异化优势\n"
                        "- AI 原生：从底层设计就围绕 AI 构建\n"
                        "- 行业深度：针对中小企业痛点定制\n"
                        "- 价格竞争力：灵活的按需付费模式"
                    ),
                    "quiz": [
                        {
                            "id": "q1",
                            "question": "我们产品相比竞品的核心差异化优势是什么？",
                            "options": [
                                "用户数量多",
                                "AI 原生设计",
                                "价格最低",
                                "功能最全",
                            ],
                            "answer": 1,
                            "explanation": "AI 原生设计是核心差异化优势，从底层围绕 AI 构建整个产品。",
                        },
                    ],
                },
            ],
        },
    ]

    # 课程ID映射 (缓存)
    _course_map: dict[str, dict] = {}
    _module_map: dict[str, dict[str, dict]] = {}

    def __init__(self):
        for course in self.COURSES:
            self._course_map[course["id"]] = course
            self._module_map[course["id"]] = {}
            for module in course.get("modules", []):
                self._module_map[course["id"]][module["id"]] = module

    async def list_courses(self) -> list[dict]:
        """列出所有课程（不含详细模块内容）"""
        result = []
        for course in self.COURSES:
            result.append(
                {
                    "id": course["id"],
                    "title": course["title"],
                    "description": course.get("description", ""),
                    "category": course.get("category", ""),
                    "duration": course.get("duration", ""),
                    "difficulty": course.get("difficulty", "beginner"),
                    "cover_icon": course.get("cover_icon", "book-open"),
                    "module_count": len(course.get("modules", [])),
                    "modules": [
                        {"id": m["id"], "title": m["title"]}
                        for m in course.get("modules", [])
                    ],
                }
            )
        return result

    async def get_course(self, course_id: str) -> dict | None:
        """获取课程完整详情"""
        return self._course_map.get(course_id)

    async def get_user_progress(
        self,
        user_id: str,
        course_id: str | None = None,
        db: Any = None,
    ) -> dict:
        """获取用户学习进度"""
        progress: dict[str, Any] = {"courses": {}}

        if db:
            try:
                query = db.table("training_progress").select("*").eq("user_id", user_id)
                if course_id:
                    query = query.eq("course_id", course_id)
                result = query.execute()

                if result.data:
                    for row in result.data:
                        cid = row["course_id"]
                        mid = row["module_id"]
                        if cid not in progress["courses"]:
                            progress["courses"][cid] = {
                                "modules": {},
                                "total_score": 0,
                                "completed_count": 0,
                            }
                        progress["courses"][cid]["modules"][mid] = {
                            "completed": row.get("completed", False),
                            "score": row.get("score"),
                            "completed_at": row.get("completed_at"),
                        }
                        if row.get("completed"):
                            progress["courses"][cid]["completed_count"] += 1
                        if row.get("score") is not None:
                            progress["courses"][cid]["total_score"] += row["score"]
            except Exception as e:
                logger.warning(f"Failed to fetch training progress: {e}")

        # 计算每个课程的完成率
        for cid, course_data in progress["courses"].items():
            course = self._course_map.get(cid)
            if course:
                total_modules = len(course.get("modules", []))
                completed_count = course_data["completed_count"]
                course_data["completion_rate"] = (
                    round(completed_count / total_modules * 100)
                    if total_modules > 0
                    else 0
                )
                course_data["total_modules"] = total_modules

        return progress

    async def update_progress(
        self,
        user_id: str,
        course_id: str,
        module_id: str,
        completed: bool = True,
        score: float | None = None,
        db: Any = None,
    ) -> dict:
        """更新用户学习进度"""
        data: dict[str, Any] = {
            "user_id": user_id,
            "course_id": course_id,
            "module_id": module_id,
            "completed": completed,
        }
        if score is not None:
            data["score"] = score
        if completed:
            data["completed_at"] = datetime.utcnow().isoformat()

        if db:
            try:
                db.table("training_progress").upsert(
                    data, on_conflict="user_id,course_id,module_id"
                ).execute()
                logger.info(
                    f"Progress updated: user={user_id}, course={course_id}, module={module_id}"
                )
            except Exception as e:
                logger.error(f"Failed to update training progress: {e}")
                raise

        return data

    async def get_quiz_questions(self, course_id: str, module_id: str) -> list[dict]:
        """获取测验题目（不含答案）"""
        module = self._module_map.get(course_id, {}).get(module_id)
        if not module:
            return []

        questions = []
        for q in module.get("quiz", []):
            questions.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "options": q["options"],
                }
            )
        return questions

    async def submit_quiz(
        self,
        user_id: str,
        course_id: str,
        module_id: str,
        answers: dict[str, int],
        db: Any = None,
    ) -> dict:
        """提交测验答案并计算成绩"""
        module = self._module_map.get(course_id, {}).get(module_id)
        if not module:
            raise ValueError(f"模块不存在: {course_id}/{module_id}")

        quiz = module.get("quiz", [])
        if not quiz:
            raise ValueError("该模块没有测验题目")

        total = len(quiz)
        correct = 0
        results = []

        for q in quiz:
            user_answer = answers.get(q["id"])
            is_correct = user_answer == q["answer"]
            if is_correct:
                correct += 1
            results.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "user_answer": user_answer,
                    "correct_answer": q["answer"],
                    "is_correct": is_correct,
                    "explanation": q.get("explanation", ""),
                }
            )

        score = round(correct / total * 100) if total > 0 else 0

        # 更新进度
        await self.update_progress(
            user_id=user_id,
            course_id=course_id,
            module_id=module_id,
            completed=True,
            score=score,
            db=db,
        )

        return {
            "score": score,
            "correct": correct,
            "total": total,
            "passed": score >= 60,
            "results": results,
        }


training_service = TrainingService()
