# P4: 自主进化与业务增长智能体（基于 Hermes Agent 调研启发）

## 1. 核心愿景 (Vision)
在 P1-P3 阶段，我们成功构建了**有状态的业务中台界面 (GenUI)**。P4 阶段的目标是让系统具备“像人一样学习”的能力。通过引入 **自我学习循环 (Learning Loop)**，使 Nexus AI 能够根据用户的操作反馈、环境配置和项目历史，自动优化自身的执行策略。

---

## 2. 深度借鉴：Hermes Agent 的核心优势转化

### 2.1 会话洞察同步 (Turn-based Insight Sync)
*   **借鉴点**: `sync_turn` 逻辑。
*   **实现方案**: 在每次复杂业务操作（如“完成一次离职审批”）后，系统会在后台触发异步任务，通过 AI 总结本次操作中的用户偏好或修正方案，并存入 Supabase 的 `agent_memories` 表。
*   **价值**: 实现“越用越懂你”，例如系统能自动记住“财务部刘总审批超过 10 万的单子通常需要补充合同原件”。

### 2.2 物理级 Context 隔离 (Prompt Fencing)
*   **借鉴点**: 使用 XML 标签（如 `<memory-context>`）隔离记忆。
*   **实现方案**: 在 `EnhancedAIChatPanel` 的系统提示词构造中，引入严格的隔离容器：
    ```xml
    <core-instruction>你是 Nexus 业务助手...</core-instruction>
    <learned-context>用户通常在周五下午处理报销...</learned-context>
    <current-data>{GenUI JSON}</current-data>
    ```
*   **价值**: 彻底防止越权指令（Prompt Injection），确保业务逻辑的鲁棒性。

### 2.3 环境感知引导 (Environment Awareness)
*   **借鉴点**: `subdirectory_hints` 自动发现规则。
*   **实现方案**: 引入 **"Domain Hints"** 机制。当用户打开“薪资”页面时，Agent 会静默加载该页面的 `BUS_RULES.md`；当用户在“销售看板”时，自动加载 `CRM_SOP.md`。
*   **价值**: 真正实现“情境化交互”，无需用户显式提醒 AI 当前场景。

---

## 3. 技术落地路线图 (Roadmap)

### 3.1 阶段 A: 持久化记忆层建设
- [ ] **Schema 设计**: 在 Supabase 中增加 `knowledge_graph` 与 `user_traits` 表。
- [ ] **记忆分层**: 实现“短期操作链 (Trajectory)”与“长期业务规则 (Rules)”的分离存储。

### 3.2 阶段 B: 自主反思循环
- [ ] **反思触发器**: 针对 `ApprovalFlow` 和 `KanbanMini` 的成功提交动作，绑定 `onSuccess` 反思任务。
- [ ] **冲突检测**: AI 在写入新记忆时，自动检查并合并与旧记忆冲突的内容。

### 3.3 阶段 C: 动态技能进化
- [ ] **技能发现**: 允许管理员在后台上传新的 `.pen` 或逻辑脚本，Agent 实时热加载相关能力映射。

---

## 4. 商业价值 (Business Impact)
1.  **降低配置成本**: 从“手动配置规则”转向“系统自动学习规则”。
2.  **极高留存率**: Agent 积累的业务洞察是不可迁移的资产，增强产品粘性。
3.  **安全性提升**: 通过规范的隔离机制，满足企业对数据与权限安全的极高要求。

---
*Inspired by Hermes Agent (Nous Research). Adapted for Nexus Business AI Platform.*
