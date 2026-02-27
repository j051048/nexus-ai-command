"""
Knowledge Base Document Seeding Script (Optimization #35)

Seeds the knowledge_library categories with initial sample documents.
Each of the 6 libraries gets 2-3 real, business-relevant Chinese documents.

Usage:
    cd nexus_backend
    python -m scripts.seed_knowledge_base

Environment:
    Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in .env

Features:
    - Idempotent: checks for existing docs by name before inserting
    - Links documents to knowledge_library via library_id
    - Creates documents with status='ready' (no embedding generation)
    - All content is in Chinese, relevant to B2B sales teams
"""

import asyncio
import hashlib
import logging
import os
import sys

from dotenv import load_dotenv

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed document definitions
# ---------------------------------------------------------------------------
# Each entry maps a library_code to a list of documents.
# library_code must match the codes in knowledge_library table.

SEED_DOCUMENTS: dict[str, list[dict]] = {
    "product_lib": [
        {
            "name": "NexusAI智能销售助手产品说明书.md",
            "doc_type": "product",
            "extracted_data": {
                "doc_type": "product",
                "client_name": None,
                "tags": ["AI助手", "销售工具", "产品介绍"],
                "full_text_context": """# NexusAI 智能销售助手 - 产品说明书

## 一、产品概述

NexusAI 智能销售助手是一款面向 B2B 企业销售团队的 AI 驱动型销售管理平台。平台集成了智能客户管理、AI 辅助沟通、知识库检索、销售预测等核心功能模块，旨在帮助销售团队提升人效、缩短成交周期、提高赢单率。

## 二、核心功能模块

### 2.1 智能客户管理 (CRM)
- 客户360度视图：整合客户基本信息、沟通记录、商机进度、合同历史
- AI 自动标签：根据沟通内容自动生成客户画像标签（行业、规模、需求阶段）
- 客户健康度评分：基于活跃度、商机进展、沟通频率等维度自动评估

### 2.2 AI 对话助手
- 多场景对话：支持客户答疑、产品推荐、竞品对比、合同审查等场景
- 上下文记忆：自动记忆历史对话要点，实现连续对话体验
- 知识库增强（RAG）：对话时自动检索企业知识库，确保回答准确

### 2.3 智能文档管理
- 多格式支持：PDF、Word、Excel、PPT、图片 OCR
- AI 自动分类：上传即自动识别文档类型（合同/标书/产品资料）
- 元数据提取：自动提取客户名称、金额、日期等关键信息
- 向量化索引：文档内容自动切片并生成向量索引，支持语义搜索

### 2.4 招投标管理
- 标书解析引擎：自动解析招标文件的核心条款和技术要求
- 偏离项分析：识别投标响应中的技术偏离和商务偏离
- 否决项预警：自动标注资质门槛、强制性要求等否决项

## 三、技术规格

| 参数 | 规格 |
|------|------|
| 部署方式 | SaaS 云端 / 私有化部署 |
| AI 模型 | GPT-4o / Gemini Pro / 国产大模型可选 |
| 向量数据库 | Supabase pgvector |
| 最大文档大小 | 50MB |
| 支持用户数 | 不限 |
| API 接口 | RESTful API + WebSocket |

## 四、适用行业

- 工业自动化设备
- 医疗器械
- IT 解决方案
- 工程建设
- 检测认证服务""",
            },
        },
        {
            "name": "NexusAI产品定价与套餐方案.md",
            "doc_type": "product",
            "extracted_data": {
                "doc_type": "product",
                "client_name": None,
                "tags": ["定价", "套餐", "商务"],
                "full_text_context": """# NexusAI 产品定价与套餐方案

## 套餐一：基础版（适合初创团队）
- 月费：¥299/用户/月
- 包含功能：基础CRM、AI对话（每日50次）、文档管理（5GB存储）
- 支持用户数：1-10人
- 知识库：1个共享知识库

## 套餐二：专业版（适合成长型企业）
- 月费：¥599/用户/月
- 包含功能：全部CRM功能、AI对话（每日200次）、文档管理（50GB）、招投标分析
- 支持用户数：11-50人
- 知识库：6个分类知识库
- 额外功能：数据看板、销售预测、团队协作

## 套餐三：企业版（适合大型企业）
- 月费：¥999/用户/月（年付8折）
- 包含功能：全部功能无限制、API接入、SSO单点登录
- 支持用户数：不限
- 知识库：无限知识库
- 专属服务：技术对接支持、定制开发、SLA 99.9%

## 增值服务
- 私有化部署：一次性 ¥50,000 + ¥2,000/月维护费
- 定制AI模型训练：¥30,000起
- 数据迁移服务：¥5,000/次

## 商务政策
- 年付优惠：8折
- 3年长约：7折
- 渠道代理价格：联系商务经理""",
            },
        },
    ],
    "regulation_lib": [
        {
            "name": "B2B销售数据合规指南.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": None,
                "tags": ["数据合规", "隐私保护", "法规"],
                "full_text_context": """# B2B 销售数据合规指南

## 一、适用法律法规

### 1.1 《中华人民共和国个人信息保护法》（PIPL）
- 施行日期：2021年11月1日
- 核心要求：收集客户联系人信息须取得明确同意
- 跨境传输：向境外提供个人信息须通过安全评估或标准合同

### 1.2 《中华人民共和国数据安全法》
- 核心要求：建立数据分类分级保护制度
- 重要数据：客户商业秘密、价格信息属于重要数据范畴
- 安全审查：涉及大量客户数据的系统须进行安全评估

### 1.3 《网络安全法》
- 等级保护：CRM系统应至少达到等保二级要求
- 日志留存：网络日志保存不少于六个月
- 安全事件：发现数据泄露须在72小时内报告

## 二、销售数据分类标准

| 数据分类 | 示例 | 保护等级 | 保留期限 |
|----------|------|----------|----------|
| 客户基本信息 | 公司名称、行业、规模 | 一般 | 合同终止后3年 |
| 联系人信息 | 姓名、电话、邮箱 | 敏感 | 合同终止后1年 |
| 商务信息 | 报价、折扣、合同金额 | 机密 | 合同终止后5年 |
| 沟通记录 | 通话录音、邮件内容 | 敏感 | 业务需要期间 |

## 三、销售人员行为准则

1. **信息采集**：仅采集业务必需的客户信息，不得过度收集
2. **信息存储**：客户信息必须录入公司CRM系统，禁止存储在个人设备
3. **信息传输**：传输客户信息须使用公司加密通道（VPN/加密邮件）
4. **信息共享**：内部共享须遵循最小权限原则，跨部门共享须审批
5. **离职交接**：离职时须完成客户数据交接，删除个人设备上的客户信息

## 四、违规处罚

- 轻微违规（首次、非故意）：口头警告 + 合规培训
- 一般违规：书面警告 + 绩效扣分
- 严重违规（数据泄露）：解除劳动合同 + 追究法律责任""",
            },
        },
        {
            "name": "合同管理制度与审批流程.md",
            "doc_type": "contract",
            "extracted_data": {
                "doc_type": "contract",
                "client_name": None,
                "tags": ["合同管理", "审批流程", "内部制度"],
                "full_text_context": """# 合同管理制度与审批流程

## 一、合同分类与审批权限

### 1.1 按金额分级审批

| 合同金额 | 审批层级 | 审批时效 |
|----------|---------|---------|
| ≤ 5万元 | 销售经理 | 1个工作日 |
| 5万-50万元 | 销售总监 + 法务 | 3个工作日 |
| 50万-200万元 | 副总经理 + 法务 + 财务 | 5个工作日 |
| > 200万元 | 总经理 + 董事会审议 | 7个工作日 |

### 1.2 特殊合同类型

- **框架协议**：须法务部全面审查，有效期不超过2年
- **独家代理**：须总经理审批，含业绩对赌条款
- **跨境合同**：须法务 + 外贸合规部双重审查

## 二、合同签订流程

1. 销售人员在CRM系统发起合同审批
2. 系统自动匹配审批链（根据金额和类型）
3. 各级审批人在线审批（支持移动端）
4. 法务审查合同条款（重点关注：付款条件、违约责任、知识产权）
5. 审批通过后系统生成合同编号
6. 双方签章（支持电子签章 / 纸质签章）
7. 合同归档至文档管理系统

## 三、关键条款检查清单

- [ ] 付款方式与比例（预付款≤30%）
- [ ] 交付时间与验收标准
- [ ] 质保期限（≥12个月）
- [ ] 违约金比例（≤合同总额10%）
- [ ] 知识产权归属
- [ ] 保密条款
- [ ] 争议解决方式（仲裁/诉讼）
- [ ] 不可抗力条款""",
            },
        },
    ],
    "case_lib": [
        {
            "name": "成功案例-某大型制造企业数字化转型.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": "某大型制造企业",
                "amount": 1200000,
                "tags": ["成功案例", "制造业", "数字化转型"],
                "full_text_context": """# 成功案例：某大型制造企业销售数字化转型

## 客户背景
- 行业：工业自动化设备制造
- 规模：年营收 5 亿元，销售团队 120 人
- 痛点：销售过程不透明、客户跟进效率低、知识经验难以传承

## 解决方案
### 第一阶段：销售流程数字化（3个月）
- 部署 NexusAI CRM 系统，实现客户信息统一管理
- 建立标准化销售漏斗（线索→商机→报价→合同→回款）
- 配置移动端，实现外勤销售实时更新客户状态

### 第二阶段：AI 赋能销售（2个月）
- 上线 AI 对话助手，辅助销售人员解答技术问题
- 建设企业知识库（产品资料300+份、历史标书50+份）
- 配置智能标书分析，自动识别招标文件的核心要求

### 第三阶段：数据驱动决策（1个月）
- 部署销售看板，实时监控团队业绩
- AI 销售预测模型上线，预测准确率达到 85%
- 自动化周报/月报生成

## 实施成果
| 指标 | 实施前 | 实施后 | 提升 |
|------|--------|--------|------|
| 人均月跟进客户数 | 15个 | 35个 | +133% |
| 平均成交周期 | 90天 | 55天 | -39% |
| 赢单率 | 18% | 28% | +56% |
| 新人上手时间 | 3个月 | 1个月 | -67% |
| 年度销售额 | 5亿 | 6.2亿 | +24% |

## 客户评价
> "NexusAI 帮助我们实现了从经验驱动到数据驱动的转变，特别是 AI 助手大幅缩短了新人培训周期。" —— 销售副总裁 张某某""",
            },
        },
        {
            "name": "成功案例-某检测认证机构招投标提效.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": "某检测认证机构",
                "amount": 480000,
                "tags": ["成功案例", "检测认证", "招投标"],
                "full_text_context": """# 成功案例：某检测认证机构招投标提效

## 客户背景
- 行业：第三方检测认证
- 规模：年投标 200+ 个项目，投标团队 30 人
- 痛点：标书编写周期长（平均7天）、重复工作多、投标质量参差不齐

## 解决方案

### 知识库建设
- 导入历史中标标书 150+ 份，建立标书模板库
- 导入产品技术资料 200+ 份，建立技术参数库
- 导入资质证书、业绩证明等常用附件

### AI 辅助投标
- 招标文件智能解析：上传招标文件后自动提取评分标准、技术要求、资质条件
- 否决项预警：自动标注注册资金、营业年限等硬性门槛
- 投标方案推荐：基于历史中标案例推荐最佳响应策略
- 技术偏离分析：对比招标要求与我方技术参数，自动标注偏离项

### 协作流程优化
- 投标任务自动拆分（技术方案、商务报价、资质文件）
- 多人协作编辑，实时同步
- 投标文件自动排版与格式检查

## 实施成果
| 指标 | 实施前 | 实施后 | 提升 |
|------|--------|--------|------|
| 标书编写周期 | 7天 | 2.5天 | -64% |
| 年度投标量 | 200个 | 350个 | +75% |
| 中标率 | 22% | 31% | +41% |
| 投标人力成本 | 150万/年 | 100万/年 | -33% |

## 客户评价
> "AI 标书分析节省了大量重复劳动，特别是否决项预警功能帮我们避免了多次无效投标。" —— 市场部经理 李某某""",
            },
        },
        {
            "name": "成功案例-某IT集成商全流程管理.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": "某IT系统集成商",
                "amount": 860000,
                "tags": ["成功案例", "IT集成", "全流程管理"],
                "full_text_context": """# 成功案例：某IT系统集成商销售全流程管理

## 客户背景
- 行业：IT 系统集成与服务
- 规模：年营收 2 亿元，销售及售前团队 60 人
- 痛点：项目信息散落在个人电脑、微信、邮件中，缺乏统一管理

## 核心问题
1. 销售离职带走客户资源，公司资产流失
2. 售前技术支持响应慢，依赖个别技术骨干
3. 大量历史方案无法复用，每次从零开始写方案
4. 管理层无法实时掌握项目进展和团队表现

## 解决方案
- **客户资产沉淀**：所有客户沟通记录、方案文档统一沉淀到NexusAI平台
- **AI 售前助手**：基于企业知识库回答产品技术问题，响应时间从2天缩短至10分钟
- **方案智能复用**：上传新需求后自动匹配历史相似方案，一键生成初稿
- **管理驾驶舱**：实时可视化销售漏斗、项目看板、团队KPI

## 实施成果
| 指标 | 实施前 | 实施后 | 提升 |
|------|--------|--------|------|
| 客户资料完整度 | 40% | 95% | +138% |
| 售前响应时间 | 2天 | 2小时 | -96% |
| 方案编写时间 | 5天 | 1.5天 | -70% |
| 季度销售额 | 5000万 | 6500万 | +30% |""",
            },
        },
    ],
    "tender_lib": [
        {
            "name": "投标文件编写规范与模板说明.md",
            "doc_type": "bid",
            "extracted_data": {
                "doc_type": "bid",
                "client_name": None,
                "tags": ["投标规范", "模板", "编写指南"],
                "full_text_context": """# 投标文件编写规范与模板说明

## 一、投标文件总体结构

### 1.1 标准目录
1. 投标函及投标函附录
2. 法定代表人身份证明 / 授权委托书
3. 联合体协议书（如适用）
4. 投标保证金缴纳证明
5. 技术部分
   - 技术方案
   - 实施计划
   - 售后服务方案
   - 培训方案
6. 商务部分
   - 投标报价表
   - 报价明细
7. 资质证明文件
   - 企业资质
   - 业绩证明
   - 财务报告
   - 人员资质

## 二、编写规范

### 2.1 格式要求
- 纸张：A4，纵向排版
- 字体：正文宋体小四，标题黑体三号
- 行距：1.5倍
- 页边距：上下2.54cm，左右3.17cm
- 页码：居中显示，格式"第X页/共Y页"

### 2.2 内容要求
- **逐条响应**：必须对招标文件的每一条技术要求做出明确响应
- **响应格式**：★ 完全满足 / △ 偏离（需说明偏离原因和替代方案）/ × 不满足
- **量化表述**：避免模糊描述，用数据说话
  - 错误：响应速度快 → 正确：平均响应时间≤200ms（P99≤500ms）
- **差异化亮点**：每个技术章节至少突出1个差异化优势

### 2.3 常见扣分项
- 未按要求编制目录
- 缺少投标函原件
- 技术方案与需求不对应
- 缺少关键人员简历
- 报价表格式不符合要求
- 未盖骑缝章

## 三、审核检查清单

投标文件提交前须完成以下检查：
- [ ] 所有必响应条款已响应
- [ ] 技术偏离项已标注并说明
- [ ] 报价计算正确，无大小写不一致
- [ ] 所有资质证书在有效期内
- [ ] 已按要求密封和标记
- [ ] 电子版与纸质版内容一致""",
            },
        },
        {
            "name": "常见招标评分标准解读与应对策略.md",
            "doc_type": "tender",
            "extracted_data": {
                "doc_type": "tender",
                "client_name": None,
                "tags": ["评分标准", "应对策略", "投标技巧"],
                "full_text_context": """# 常见招标评分标准解读与应对策略

## 一、评分方法分类

### 1.1 综合评分法（最常见）
- 技术评分：通常占 40%-60%
- 商务评分：通常占 20%-30%
- 价格评分：通常占 20%-30%
- 特点：综合实力竞争，利于技术领先企业

### 1.2 最低价中标法
- 适用场景：标准化产品采购、通用设备采购
- 策略要点：在满足技术要求前提下，控制成本
- 注意事项：低于成本价可能被认定为恶意竞争

### 1.3 性价比法
- 计算公式：得分 = 技术得分 / 投标报价
- 策略要点：平衡技术方案质量和报价

## 二、技术评分应对策略

### 2.1 方案完整性（10-15分）
- **要点**：确保方案涵盖所有需求点，无遗漏
- **策略**：建立需求-响应矩阵，逐条对应

### 2.2 技术先进性（10-15分）
- **要点**：展示技术架构、核心算法、创新点
- **策略**：引用行业标准、专利技术、性能测试数据

### 2.3 实施方案（10-15分）
- **要点**：项目管理方法、里程碑计划、风险控制
- **策略**：提供甘特图、RACI矩阵，展示专业度

### 2.4 售后服务（5-10分）
- **要点**：响应时间、维护计划、培训方案
- **策略**：承诺具体SLA指标，提供7×24小时服务

## 三、商务评分应对策略

### 3.1 企业资质（5-10分）
- ISO 9001 质量管理体系认证
- CMMI 3级及以上（软件类项目）
- 信息安全等级保护认证

### 3.2 业绩证明（5-15分）
- 选择与本项目规模和行业最相似的案例
- 准备完整的合同、验收报告、客户评价函
- 数量要求：通常需要3-5个近3年同类项目

### 3.3 团队配置（5-10分）
- 项目经理：PMP认证 + 5年以上经验
- 技术骨干：相关领域高级工程师认证
- 提供人员简历、证书复印件

## 四、价格策略

### 4.1 报价原则
- 研究对手报价区间（参考历史中标价）
- 考虑最低限价（通常为预算的 70%-80%）
- 利润空间不低于 15%

### 4.2 常用报价策略
- **略低报价法**：比预估均价低 5%-8%
- **分项优化法**：核心产品保利润，服务项目让利
- **阶梯报价法**：一次性费用低，持续服务费合理""",
            },
        },
    ],
    "training_lib": [
        {
            "name": "新人销售入职培训手册.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": None,
                "tags": ["培训", "新人入职", "销售基础"],
                "full_text_context": """# 新人销售入职培训手册

## 第一周：认知与基础

### Day 1-2：公司与产品认知
- 公司发展历程、企业文化、组织架构
- 核心产品线介绍（功能、优势、适用场景）
- 竞品概况及差异化定位
- 培训考核：产品知识测试（≥80分通过）

### Day 3-4：销售流程与工具
- NexusAI CRM 系统操作培训
- 销售漏斗七阶段详解：
  1. 线索获取 → 2. 初次接触 → 3. 需求确认
  4. 方案呈现 → 5. 商务谈判 → 6. 合同签订 → 7. 交付回款
- 客户信息录入规范
- AI 对话助手使用教程

### Day 5：实战模拟
- 角色扮演：模拟客户首次电话沟通
- 话术练习：开场白、需求挖掘、异议处理
- 师傅带教分配

## 第二周：技能强化

### 需求挖掘技巧（SPIN 法则）
- **S**ituation（背景问题）：了解客户现状
  - 示例："贵公司目前销售团队有多少人？用的什么CRM系统？"
- **P**roblem（难点问题）：发现痛点
  - 示例："目前客户跟进过程中最大的困难是什么？"
- **I**mplication（暗示问题）：放大痛点影响
  - 示例："如果客户跟进不及时，对成交率会有多大影响？"
- **N**eed-payoff（价值问题）：引导解决方案
  - 示例："如果能把客户响应时间缩短50%，对业绩会有怎样的帮助？"

### 异议处理话术模板

| 客户异议 | 应对策略 |
|----------|----------|
| "太贵了" | "理解您的顾虑。我们来算一下ROI：假设每月多成交2单，每单平均10万..." |
| "我们再考虑考虑" | "完全理解。方便问一下，主要还在考虑哪些方面？我可以补充些信息帮助决策。" |
| "用着现有系统挺好的" | "能分享一下现有系统最满意的功能是什么吗？我们可以看看有没有互补的空间。" |
| "需要领导审批" | "理解。如果方便的话，我可以准备一份给领导的简版方案，突出关键价值点和ROI。" |

## 第三、四周：跟岗实战
- 跟随师傅拜访客户 5+ 次
- 独立完成首次客户电话 10+ 通
- 每日写销售日志，师傅点评
- 月末考核：独立完成一次完整的需求分析和方案呈现""",
            },
        },
        {
            "name": "高效客户沟通话术集.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": None,
                "tags": ["话术", "沟通技巧", "客户管理"],
                "full_text_context": """# 高效客户沟通话术集

## 一、电话开场白

### 1.1 首次陌生拜访
> "X总您好，我是[公司名]的[姓名]。我们专注于帮助[行业]企业通过AI技术提升销售效率。注意到贵公司最近在[具体事件/新闻]方面有动作，想和您交流3分钟，看看我们的经验能否给您一些参考。"

### 1.2 老客户回访
> "X总好！上次您提到的[具体问题]，我们这边有了新的解决思路，想第一时间和您分享。另外也想了解一下最近项目进展如何？"

### 1.3 转介绍跟进
> "X总您好，是[介绍人]推荐我联系您的。他提到贵公司在[某方面]有需求，正好是我们的强项。方便聊几分钟吗？"

## 二、需求确认话术

### 2.1 预算确认（委婉方式）
> "为了给您提供最合适的方案，想了解一下这个项目大概的投入预期是怎样的？我们有不同配置的方案可以匹配。"

### 2.2 决策链确认
> "这个项目除了您之外，还有哪些同事会参与评估？我们可以准备不同侧重点的材料，分别给技术部门和管理层。"

### 2.3 时间节点确认
> "这个项目计划什么时候启动？我们需要预留多少时间来做方案演示和试用？"

## 三、产品演示话术

### 3.1 功能演示引导
> "我先给您演示最核心的三个功能，每个大概5分钟。如果哪个点您特别感兴趣，我们可以深入展开。"

### 3.2 对比竞品（不贬低对手）
> "您提到的[竞品]确实也是不错的产品。我们和他们最大的差异在于[差异点]。给您看一个实际对比数据..."

### 3.3 引导试用
> "文字介绍终究有限，建议您用我们的试用版实际体验一下。我可以帮您开通14天免费试用，同时安排一位技术顾问全程支持。"

## 四、商务谈判话术

### 4.1 价格谈判
> "这个价格确实是我们针对贵公司规模给出的最优方案了。不过如果您能确认[年付/3年长约/增加用户数]，我可以向公司申请额外的折扣。"

### 4.2 推动签约
> "方案和价格如果没有异议的话，我建议我们尽快推进合同环节。目前正好赶上[季度末优惠/限时活动]，过了这个时间点就没有额外折扣了。"

### 4.3 合同细节沟通
> "合同的核心条款我已经标注出来了，主要是[付款方式]、[交付周期]和[售后服务]这三块。您看一下有没有需要调整的地方？"

## 五、售后维护话术

### 5.1 定期回访
> "X总好！系统上线已经[X]个月了，使用情况怎么样？有没有遇到什么问题？我们最近新上线了[新功能]，可能对您的团队很有帮助。"

### 5.2 续费沟通
> "您的服务即将在[日期]到期。根据使用数据来看，贵公司团队的活跃度很高，AI助手已经帮助处理了[X]个客户咨询。建议提前续费，我们可以锁定当前价格。" """,
            },
        },
        {
            "name": "销售团队常见FAQ汇总.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": None,
                "tags": ["FAQ", "常见问题", "内部知识"],
                "full_text_context": """# 销售团队常见 FAQ 汇总

## 产品相关

**Q1: NexusAI 支持哪些部署方式？**
A: 支持三种部署方式：
1. SaaS 云端版（推荐，开箱即用）
2. 私有云部署（需客户提供服务器资源）
3. 混合部署（敏感数据本地化，其他功能云端）

**Q2: 数据安全如何保障？**
A: 三重保障：
1. 传输加密：全链路 HTTPS/TLS 1.3
2. 存储加密：AES-256 静态加密
3. 访问控制：RBAC 角色权限 + 行级数据隔离（RLS）
4. 合规认证：通过等保二级评测

**Q3: AI 模型用的什么？回答准确吗？**
A: 支持多模型切换（GPT-4o、Gemini Pro、国产大模型）。准确性通过 RAG 技术保障——AI 回答基于企业自有知识库检索，而非凭空生成。用户可以看到引用来源。

**Q4: 系统能和我们现有的ERP/OA对接吗？**
A: 支持。我们提供标准 RESTful API 和 Webhook 机制，已有金蝶、用友、钉钉、企业微信等对接案例。定制对接需额外评估工作量。

## 商务相关

**Q5: 有免费试用吗？**
A: 提供14天全功能免费试用，无需绑定信用卡。试用期间分配专属技术顾问。

**Q6: 合同最短签多久？**
A: 月付无最低期限，年付享8折优惠，3年长约享7折优惠。

**Q7: 超过用户数怎么收费？**
A: 基础版按用户数计费。专业版和企业版支持弹性扩容，超出部分按月结算。

**Q8: 如果不满意可以退款吗？**
A: 年付客户享有30天无理由退款保障（扣除已使用天数费用）。

## 技术相关

**Q9: 上传的文档有大小限制吗？**
A: 单文件最大 50MB。支持 PDF、Word、Excel、PPT、TXT、Markdown、图片等格式。

**Q10: 知识库检索速度如何？**
A: 基于向量数据库（pgvector + HNSW 索引），P95 检索延迟 < 200ms。""",
            },
        },
    ],
    "competitor_lib": [
        {
            "name": "主要竞品分析报告.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": None,
                "tags": ["竞品分析", "市场调研", "竞争格局"],
                "full_text_context": """# 主要竞品分析报告（2026年Q1）

## 一、竞争格局概览

B2B AI 销售管理赛道主要玩家分为三类：
1. **传统 CRM + AI 增强**：Salesforce Einstein、纷享销客 AI
2. **AI-Native 销售工具**：NexusAI（我方）、SalesGPT、卖哥AI
3. **通用 AI 平台定制**：基于钉钉/飞书/企微的定制方案

## 二、核心竞品对比

### 2.1 Salesforce Einstein
| 维度 | Salesforce Einstein | NexusAI |
|------|-------------------|---------|
| 目标市场 | 大型企业（500人+） | 中小型企业（10-200人） |
| 起步价 | ¥3,000/用户/月 | ¥299/用户/月 |
| AI能力 | 预测型AI为主 | 生成式AI + RAG |
| 中文支持 | 一般（翻译体） | 原生中文 |
| 本地化 | 弱（美国产品） | 强（国产） |
| 部署方式 | 仅SaaS | SaaS/私有化/混合 |

**竞争策略**：强调性价比和中国市场本地化优势，避免在大企业市场正面竞争。

### 2.2 纷享销客
| 维度 | 纷享销客 | NexusAI |
|------|---------|---------|
| 产品成熟度 | 高（10年+） | 中等（成长期） |
| AI深度 | 辅助功能 | 核心驱动力 |
| 知识库 | 基础文档存储 | AI语义检索+RAG |
| 招投标管理 | 无 | 核心功能 |
| 集成能力 | 强（生态完善） | 中等（持续完善） |

**竞争策略**：突出 AI 原生优势和招投标管理差异化功能。

### 2.3 钉钉/飞书定制方案
| 维度 | 平台定制方案 | NexusAI |
|------|------------|---------|
| 成本 | 低（平台内免费/低费） | 中等 |
| 定制灵活度 | 受平台限制 | 高度自定义 |
| AI深度 | 通用AI | 垂直销售领域 |
| 数据归属 | 平台所有 | 客户自有 |

**竞争策略**：强调数据主权、垂直领域深度和独立部署能力。

## 三、我方差异化优势

1. **AI-Native 架构**：不是在传统CRM上叠加AI，而是以AI为核心设计
2. **招投标管理**：市场上极少数将标书分析作为核心功能的产品
3. **灵活部署**：SaaS/私有化/混合部署满足不同安全需求
4. **性价比**：¥299起步，远低于国际品牌
5. **国产替代**：完全国产化，满足信创要求

## 四、竞争话术要点

- 客户提到 Salesforce："我们更适合中国市场，价格只有他们的1/10"
- 客户提到纷享销客："他们擅长CRM，我们擅长AI，特别是招投标场景"
- 客户提到自建/定制："自建的隐性成本很高，我们已经踩过的坑可以帮您避免"
- 客户提到免费工具："免费工具的数据散落各处，长期看管理成本更高"
""",
            },
        },
        {
            "name": "AI销售工具行业趋势报告.md",
            "doc_type": "other",
            "extracted_data": {
                "doc_type": "other",
                "client_name": None,
                "tags": ["行业趋势", "市场分析", "AI销售"],
                "full_text_context": """# AI 销售工具行业趋势报告（2026）

## 一、市场规模

- 2025年中国CRM市场规模：约180亿元
- 2026年预测：约220亿元（YoY +22%）
- AI增强型CRM占比：从2024年的15%提升至2026年的35%
- B2B企业AI工具渗透率：从8%提升至18%

## 二、核心趋势

### 趋势1：从"辅助"到"驱动"
- 2024年：AI作为CRM的辅助功能（智能推荐、自动填充）
- 2026年：AI成为销售流程的核心驱动力（自动跟进、智能决策）
- 预测：2027年50%的B2B销售首次接触将由AI完成

### 趋势2：RAG 技术成为标配
- 企业知识库 + 大模型检索增强（RAG）成为AI销售工具的基础能力
- 向量数据库市场快速增长（Pinecone、pgvector、Milvus）
- 趋势：从文本检索扩展到多模态检索（图片、表格、图纸）

### 趋势3：垂直化深耕
- 通用CRM向垂直行业方案演进
- 重点行业：制造业、医疗器械、IT服务、工程建设
- 行业知识图谱 + 领域模型成为竞争壁垒

### 趋势4：合规与数据主权
- PIPL实施后企业对数据安全要求提升
- 私有化部署需求增长30%
- 国产替代趋势加速（政企客户信创要求）

### 趋势5：Agent化
- 从"问答式AI"向"Agent式AI"演进
- 销售Agent能够自主执行：发送邮件、创建任务、更新CRM
- 人机协作模式：AI处理60%的重复性工作，人类专注高价值判断

## 三、对NexusAI的启示

1. **加速Agent能力建设**：让AI不仅能回答问题，还能自主执行销售动作
2. **深耕2-3个垂直行业**：建立行业壁垒（建议：制造业、IT集成、检测认证）
3. **强化RAG质量**：投资于更精准的知识检索和回答质量
4. **打造数据飞轮**：用户越多→数据越多→AI越准→体验越好→用户越多
5. **重视合规认证**：等保三级 + ISO 27001 作为2026年目标""",
            },
        },
    ],
}


async def get_supabase_client():
    """Create a Supabase client using the same pattern as the backend."""
    try:
        from postgrest import AsyncPostgrestClient
    except ImportError:
        logger.error("postgrest 未安装。请运行: pip install postgrest")
        sys.exit(1)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        logger.error("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_KEY 环境变量")
        sys.exit(1)

    base_url = f"{url}/rest/v1"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    class SimpleClient:
        def __init__(self):
            self.client = AsyncPostgrestClient(base_url, headers=headers)

        def table(self, name: str):
            return self.client.from_(name)

    return SimpleClient()


async def fetch_libraries(client) -> dict[str, int]:
    """Fetch existing knowledge_library entries and return a code->id mapping."""
    try:
        res = await client.table("knowledge_library").select("id, library_code").execute()
        if res.data:
            return {row["library_code"]: row["id"] for row in res.data}
    except Exception as e:
        logger.warning(f"获取知识库分类失败: {e}")
    return {}


async def check_existing_doc(client, doc_name: str) -> bool:
    """Check if a document with the given name already exists."""
    try:
        res = (
            await client.table("documents")
            .select("id")
            .eq("name", doc_name)
            .limit(1)
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        logger.debug(f"检查文档是否存在时出错: {e}")
        return False


async def seed_documents(client, libraries: dict[str, int]):
    """Insert seed documents for each library category."""
    total_inserted = 0
    total_skipped = 0

    for library_code, docs in SEED_DOCUMENTS.items():
        library_id = libraries.get(library_code)
        if not library_id:
            logger.warning(f"知识库 '{library_code}' 未找到，跳过该分类的文档")
            continue

        logger.info(f"--- 正在处理知识库: {library_code} (id={library_id}) ---")

        for doc in docs:
            doc_name = doc["name"]

            # Idempotent check
            if await check_existing_doc(client, doc_name):
                logger.info(f"  [跳过] 文档已存在: {doc_name}")
                total_skipped += 1
                continue

            # Compute content hash for dedup
            full_text = doc["extracted_data"].get("full_text_context", "")
            content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

            record = {
                "name": doc_name,
                "doc_type": doc.get("doc_type", "other"),
                "version": 1,
                "extracted_data": doc["extracted_data"],
                "status": "ready",
                "progress": 100,
                "stage": "completed",
                "visibility": "organization",
                "content_hash": content_hash,
                "library_id": library_id,
                "category": doc.get("doc_type", "other"),
            }

            try:
                res = await client.table("documents").insert(record).execute()
                if res.data:
                    doc_id = res.data[0]["id"]
                    logger.info(f"  [创建] {doc_name} -> id={doc_id}")
                    total_inserted += 1
                else:
                    logger.error(f"  [失败] {doc_name}: 无返回数据")
            except Exception as e:
                logger.error(f"  [失败] {doc_name}: {e}")

    return total_inserted, total_skipped


async def update_library_doc_counts(client, libraries: dict[str, int]):
    """Update doc_count in knowledge_library to reflect actual document counts."""
    for library_code, library_id in libraries.items():
        try:
            # Count documents in this library
            res = (
                await client.table("documents")
                .select("id", count="exact")
                .eq("library_id", library_id)
                .execute()
            )
            count = len(res.data) if res.data else 0

            # Update library doc_count
            await (
                client.table("knowledge_library")
                .update({"doc_count": count})
                .eq("id", library_id)
                .execute()
            )
            logger.info(f"  知识库 '{library_code}' 文档计数更新为: {count}")
        except Exception as e:
            logger.warning(f"  更新 '{library_code}' 文档计数失败: {e}")


async def main():
    logger.info("=" * 60)
    logger.info("知识库文档种子脚本启动")
    logger.info("=" * 60)

    client = await get_supabase_client()

    # 1. Fetch existing libraries
    libraries = await fetch_libraries(client)
    if not libraries:
        logger.error("未找到任何知识库分类。请先执行 20260225_008_knowledge_library.sql 迁移。")
        sys.exit(1)

    logger.info(f"找到 {len(libraries)} 个知识库分类: {list(libraries.keys())}")

    # 2. Seed documents
    inserted, skipped = await seed_documents(client, libraries)

    # 3. Update doc counts
    logger.info("--- 更新知识库文档计数 ---")
    await update_library_doc_counts(client, libraries)

    # Summary
    logger.info("=" * 60)
    logger.info(f"种子脚本完成: 新增 {inserted} 篇文档, 跳过 {skipped} 篇已存在文档")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
