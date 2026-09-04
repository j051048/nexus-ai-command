# 贡献指南

## 基本原则

1. 先读 `docs/handbook/00-start-here.md` 和所属领域代码，再修改。
2. 保持改动小而可回滚；不在功能 PR 中顺手重构无关模块。
3. 租户数据必须携带组织上下文，禁止用前端传入的 `organization_id` 作为唯一信任来源。
4. 高风险 Agent 工具必须声明权限、幂等、审计、确认和补偿策略。
5. 不新增宽泛 `except Exception`。确需边界兜底时，记录上下文并转换为领域错误。

## 分支与提交

- 分支：`feature/*`、`fix/*`、`chore/*`；Codex 自动分支使用 `codex/*`。
- 一个提交只表达一个意图，提交信息使用祈使句并说明影响领域。
- 数据库迁移只追加，不修改已进入共享环境的历史迁移。

## 提交前检查

```bash
npx tsc --noEmit
npm run lint
npm test
npm run quality:frontend
python scripts/check_handover_readiness.py
python scripts/check_exception_governance.py

cd nexus_backend
ruff check app/
black --check app/
pytest <受影响测试> -q
```

## 拆分规则

- 页面负责装配，领域组件负责展示，自定义 Hook 负责远端状态，服务层负责业务规则。
- 拆分时先复制等价实现并补契约测试，再切换调用，最后删除旧实现。
- 新前端文件建议不超过 400 行；超过 500 行由 `check_source_size.mjs` 阻断。
- 不为降低行数创建无语义的 `utils2.ts` 或仅转发参数的组件。

## PR 必填项

- 问题、方案、影响范围和回滚方法。
- 已执行的测试及未执行原因。
- Schema/API/权限/成本是否变化。
- UI 改动需附桌面和移动端截图；Agent 改动需附 eval 或契约结果。
- 产品入口、环境变量、Schema、Agent 行为或发布门禁变化时，必须同步更新 `docs/README.md` 所列权威文档；不要修改自动生成的 `docs/handbook/generated/inventory.md`。
