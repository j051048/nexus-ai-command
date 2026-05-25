import type { ComponentType } from 'react';
import {
  ClipboardCheck,
  FileSearch,
  FlaskConical,
  GitBranch,
  GraduationCap,
  Microscope,
  SearchCheck,
  TimerReset,
} from 'lucide-react';

export type ScientificInstrumentAssetType =
  | 'competitor'
  | 'tender'
  | 'customer_chain'
  | 'sales_play';

export interface ScientificInstrumentKnowledgeAsset {
  id: string;
  title: string;
  type: ScientificInstrumentAssetType;
  scenario: string;
  description: string;
  tags: string[];
  framework: string[];
  aiPrompt: string;
  owner?: string;
  status?: 'active' | 'draft' | 'archived';
  evidenceCount?: number;
  version?: number;
  updatedAt?: string | null;
  icon: ComponentType<{ className?: string }>;
}

export const SCIENTIFIC_INSTRUMENT_TYPE_LABELS: Record<
  ScientificInstrumentAssetType,
  string
> = {
  competitor: '竞品战卡',
  tender: '招投标',
  customer_chain: '决策链',
  sales_play: '销售打法',
};

export const SCIENTIFIC_INSTRUMENT_KNOWLEDGE_ASSETS: ScientificInstrumentKnowledgeAsset[] = [
  {
    id: 'thermo-fisher-lcms-battlecard',
    title: 'Thermo Fisher LC/MS 竞品对比框架',
    type: 'competitor',
    scenario: '液质联用采购、质谱平台更新、科研平台招标',
    description:
      '围绕灵敏度、稳定性、软件生态、耗材成本、服务网络和论文背书构建可复用战卡。',
    tags: ['LC/MS', 'Thermo Fisher', '竞品参数', '售前论证'],
    framework: [
      '核心指标：检测限、线性范围、质量准确度、扫描速度',
      '业务指标：样本通量、维护停机、耗材与维保成本',
      '证据材料：论文引用、标杆客户、应用方案、售后响应',
      '反击话术：把单点参数优势转译为全生命周期收益',
    ],
    aiPrompt:
      '请基于 Thermo Fisher LC/MS 竞品对比框架，为我的产品生成一份销售战卡，包含参数对比、客户关切、反击话术和证据材料清单。',
    icon: Microscope,
  },
  {
    id: 'agilent-chromatography-battlecard',
    title: 'Agilent 色谱系统对标框架',
    type: 'competitor',
    scenario: '高校实验室、第三方检测、药企 QC 色谱采购',
    description:
      '把硬件稳定性、软件工作流、方法迁移、耗材锁定和售后能力拆成可评分维度。',
    tags: ['HPLC', 'GC', 'Agilent', '方法迁移'],
    framework: [
      '系统能力：泵稳定性、进样精度、柱温控制、检测器灵敏度',
      '迁移成本：现有方法兼容、人员学习成本、历史数据连续性',
      '采购风险：耗材绑定、维保周期、备件交付、停机损失',
      '成交策略：先证明方法迁移，再谈总体拥有成本',
    ],
    aiPrompt:
      '请按 Agilent 色谱系统对标框架，帮我准备一份给药企 QC 客户的竞品对比和方法迁移沟通提纲。',
    icon: FlaskConical,
  },
  {
    id: 'shimadzu-technical-comparison',
    title: 'Shimadzu 色谱质谱技术对标框架',
    type: 'competitor',
    scenario: '预算敏感型高校、区域检测中心、国产替代论证',
    description:
      '用于把参数、价格、服务、培训和国产替代政策组合成可解释的采购建议。',
    tags: ['Shimadzu', 'GC-MS', '国产替代', '预算论证'],
    framework: [
      '参数对照：灵敏度、分辨率、稳定性、自动化程度',
      '采购论证：预算约束、国产替代政策、平台共享效率',
      '实施风险：安装周期、培训计划、方法包成熟度',
      '赢单抓手：把预算优势与可交付服务承诺绑定',
    ],
    aiPrompt:
      '请使用 Shimadzu 色谱质谱技术对标框架，生成一份预算敏感客户的采购论证材料和异议处理话术。',
    icon: ClipboardCheck,
  },
  {
    id: 'tender-score-breakdown',
    title: '招投标评分拆解模板',
    type: 'tender',
    scenario: '公开招标、竞争性磋商、技术方案打分前评估',
    description:
      '把招标文件拆成硬性门槛、技术分、商务分、服务分和风险条款，提前预测失分点。',
    tags: ['招标文件', '评分标准', '技术偏离表', '风险条款'],
    framework: [
      '资格门槛：资质、授权、业绩、交付周期',
      '技术分：关键参数、偏离条款、检测报告、应用案例',
      '商务分：报价策略、付款条件、质保承诺、备件价格',
      '风险项：排他参数、模糊验收、服务半径、违约责任',
    ],
    aiPrompt:
      '请按招投标评分拆解模板分析这份招标文件，输出预计得分、硬性风险、可补证据和投标策略。',
    icon: FileSearch,
  },
  {
    id: 'research-institute-buying-chain',
    title: '高校/科研院所采购决策链',
    type: 'customer_chain',
    scenario: '课题组设备采购、公共平台采购、学院统筹采购',
    description:
      '识别 PI、实验老师、平台负责人、采购办、财务和使用学生的不同诉求。',
    tags: ['高校客户', '科研院所', '决策链', '采购办'],
    framework: [
      'PI：研究方向、论文产出、平台影响力、预算来源',
      '实验老师：易用性、稳定性、培训、售后响应',
      '采购办：合规、价格、资质、验收文件',
      '学生/用户：方法模板、上手速度、排队效率',
    ],
    aiPrompt:
      '请根据高校/科研院所采购决策链，为这个客户生成角色地图、关键问题清单和下一步跟进节奏。',
    icon: GraduationCap,
  },
  {
    id: 'funding-lead-follow-up',
    title: '基金/课题线索跟进节奏',
    type: 'sales_play',
    scenario: '国自然、科技部项目、重点实验室建设、论文方向线索',
    description:
      '把基金立项、论文关键词和平台建设计划转成客户触达、资料准备和商机推进节奏。',
    tags: ['基金线索', '论文线索', '重点实验室', '销售节奏'],
    framework: [
      '线索识别：项目名称、关键词、负责人、预算周期',
      '触达时机：立项后 30 天、预算确认、方案论证前',
      '资料准备：应用案例、技术路线、设备配置建议',
      '推进节奏：首访、技术交流、样机演示、方案固化',
    ],
    aiPrompt:
      '请按基金/课题线索跟进节奏，把这条科研项目线索转成客户触达话术、资料清单和 30 天推进计划。',
    icon: TimerReset,
  },
  {
    id: 'technical-visit-playbook',
    title: '技术拜访速记与复盘模板',
    type: 'sales_play',
    scenario: '售前拜访、样机演示、应用方案交流、客户复盘',
    description:
      '把拜访纪要沉淀为需求、竞品、预算、决策链、风险和下一步动作，减少销售跟进断层。',
    tags: ['拜访纪要', '售前', '复盘', '下一步动作'],
    framework: [
      '需求：样品类型、检测目标、通量、精度、预算',
      '竞品：已有设备、对比品牌、客户显性偏好',
      '决策：影响人、拍板人、采购流程、时间窗口',
      '动作：补资料、约演示、报价、内部技术评审',
    ],
    aiPrompt:
      '请用技术拜访速记与复盘模板整理我的拜访记录，输出客户需求、风险、决策链和下一步行动。',
    icon: GitBranch,
  },
  {
    id: 'application-proof-checklist',
    title: '应用证据材料清单',
    type: 'tender',
    scenario: '技术方案、竞品反击、投标附件、客户内部立项',
    description:
      '统一沉淀论文、应用 note、检测报告、客户案例、验收记录和服务承诺。',
    tags: ['应用案例', '论文背书', '检测报告', '验收材料'],
    framework: [
      '学术证据：论文、引用、应用方向、样品类型',
      '交付证据：验收报告、培训记录、服务 SLA',
      '对标证据：第三方检测、标杆客户、方法包',
      '缺口管理：缺证据时的补测、补材料和替代表达',
    ],
    aiPrompt:
      '请按应用证据材料清单，帮我检查当前投标/销售资料还缺哪些证据，并给出补齐优先级。',
    icon: SearchCheck,
  },
];

export const SCIENTIFIC_INSTRUMENT_PROMPTS = [
  '帮我对标 Thermo Fisher 的同类产品，生成一份科学仪器竞品战卡。',
  '根据招标文件评分标准，评估我们的技术方案可能得分和短板。',
  '这个高校实验室客户通常的采购决策链是什么？请给出跟进节奏。',
  '把我的技术拜访记录整理成客户需求、风险和下一步行动。',
];

export const SCIENTIFIC_INSTRUMENT_ICON_BY_TYPE: Record<
  ScientificInstrumentAssetType,
  ComponentType<{ className?: string }>
> = {
  competitor: Microscope,
  tender: FileSearch,
  customer_chain: GraduationCap,
  sales_play: TimerReset,
};
