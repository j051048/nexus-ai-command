# DESIGN.md — Nexus AI Command Center

> 本文件遵循 [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) 格式，供 AI Agent 和开发者参考，确保 UI 修改保持一致性。

---

## 1. Visual Theme

**双主题策略**：亮色（Clean Professional SaaS）+ 暗色（Cyberpunk Muted）

- **亮色模式**：白色为主、蓝色强调、微妙阴影、干净边框。面向日常办公使用。
- **暗色模式**：近黑底色、科技蓝强调、克制的 glow 效果。面向深度专注场景。
- **Sidebar**：始终使用暗色调（独立于主题切换），参考 Linear/Notion 的暗色导航栏模式。

**设计哲学**：减法优先。避免装饰性特效堆叠，让内容和数据本身说话。

---

## 2. Color Palette

### 基础色

| Token | 亮色 (HSL) | 暗色 (HSL) | 用途 |
|-------|-----------|-----------|------|
| `--background` | `210 20% 98%` | `0 0% 7%` | 页面底色 |
| `--foreground` | `222 47% 11%` | `0 0% 95%` | 主文字 |
| `--card` | `0 0% 100%` | `0 0% 10%` | 卡片底色 |
| `--card-elevated` | `210 20% 96%` | `0 0% 12%` | 浮起卡片 |

### 语义色

| Token | 亮色 | 暗色 | 用途 |
|-------|------|------|------|
| `--primary` | `217 91% 50%` | `211 100% 50%` | 主操作、链接、焦点 |
| `--success` | `142 69% 45%` | `142 69% 50%` | 成功状态 |
| `--warning` | `36 100% 50%` | `36 100% 52%` | 警告状态 |
| `--destructive` | `0 84% 55%` | `0 84% 60%` | 危险操作 |

### 边框与输入

| Token | 亮色 | 暗色 |
|-------|------|------|
| `--border` | `214 20% 88%` | `0 0% 18%` |
| `--input` | `214 20% 92%` | `0 0% 15%` |
| `--muted-foreground` | `215 16% 40%` | `0 0% 55%` |

### 游戏化色

| Token | 值 | 用途 |
|-------|---|------|
| `--gold` | `45 100% 50%` | 排名第一 |
| `--silver` | `0 0% 65%` | 排名第二 |
| `--bronze` | `30 60% 45%` | 排名第三 |
| `--xp-bar` | `280 100% 55%` | 经验值进度条 |

### 使用规范

```css
/* ✅ 正确：使用 CSS 变量 */
color: hsl(var(--primary));
background: hsl(var(--card));

/* ❌ 错误：硬编码 hex 值 */
background: #0d0f14;
color: #141b2e;
```

---

## 3. Typography

**字体**：`Inter`（正文）+ `JetBrains Mono`（代码/数字）

### 字号阶梯（Tailwind Token）

| Token | 大小 | 行高 | 字重 | 用途 |
|-------|------|------|------|------|
| `text-display-lg` | 3rem (48px) | 1.2 | 700 | 英雄区标题 |
| `text-display` | 2.25rem (36px) | 1.25 | 700 | 页面标题 |
| `text-heading-lg` | 1.875rem (30px) | 1.3 | 600 | 区块标题 |
| `text-heading` | 1.5rem (24px) | 1.4 | 600 | 卡片标题 |
| `text-heading-sm` | 1.25rem (20px) | 1.4 | 600 | 子标题 |
| `text-body-lg` | 1.125rem (18px) | 1.6 | 400 | 强调正文 |
| `text-body` | 1rem (16px) | 1.5 | 400 | 默认正文 |
| `text-body-sm` | 0.875rem (14px) | 1.5 | 400 | 次要文字 |
| `text-caption` | 0.75rem (12px) | 1.4 | 400 | 标签、辅助文字 |
| `text-micro` | 0.625rem (10px) | 1.4 | 400 | 徽章、极小标注 |

### 迁移指南

项目中有约 245 处 `text-[10px]` 硬编码，应逐步迁移为 `text-micro`。

```tsx
// ✅ 正确
<span className="text-micro font-black uppercase">SECTION</span>

// ❌ 避免
<span className="text-[10px] font-black uppercase">SECTION</span>
```

---

## 4. Component Styling

### 卡片变体

| 类名 | 效果 | 使用场景 |
|------|------|---------|
| `card-glass` | `bg-card/0.8` + `backdrop-blur(12px)` + 半透明边框 | 浮层卡片、对话框 |
| `glass-card` | `backdrop-blur-xl` + `bg-white/80 dark:bg-gray-900/80` | 内容卡片 |
| `glass-sidebar` | `backdrop-blur-2xl` + `bg-white/60 dark:bg-gray-950/60` | 侧边栏面板 |
| `glass-header` | `backdrop-blur-xl` + `bg-white/70 dark:bg-gray-900/70` | 顶栏 |

### 按钮

- **主要操作**：`bg-primary text-primary-foreground shadow-md shadow-primary/20`
- **悬停**：`hover:shadow-lg hover:shadow-primary/30`
- **按压**：`active:scale-[0.98]`
- **触摸目标**：最小 `min-h-touch min-w-touch`（44px × 44px）

### 输入框

```tsx
className="h-11 rounded-xl bg-background/60 border-white/20 dark:border-white/10
           hover:bg-background/70 hover:border-primary/50
           focus:bg-background/80 transition-all duration-300"
```

注意：不要在输入框上叠加 `backdrop-blur`，它们已在有 blur 的卡片容器内。

---

## 5. Layout Principles

### 间距系统（8px 网格）

| Tailwind Token | CSS 变量 | 值 | 用途 |
|----------------|---------|------|------|
| `p-tight` / `gap-tight` | `--spacing-sm` | 0.5rem (8px) | 紧凑间距 |
| `p-element` / `gap-element` | `--spacing-md` | 1rem (16px) | 元素间距 |
| `p-component` / `gap-component` | `--spacing-xl` | 2rem (32px) | 组件间距 |
| `p-section` / `gap-section` | — | 4rem (64px) | 区块间距 |

### ChatFirst 三列布局

```
┌──────────┬────────────────┬──────────────────────┐
│ Sidebar  │   Chat Panel   │    Canvas/Content     │
│  w-64    │  45% → 38% lg  │   55% → 62% lg       │
│  固定     │  → 35% xl      │   → 65% xl           │
│          │               │  max-w 1600/1800px xl  │
└──────────┴────────────────┴──────────────────────┘
```

### 容器最大宽度

- `container`: `max-w-[1400px]`（Tailwind 默认）
- Canvas 内容：`max-w-[1600px] xl:max-w-[1800px]`

---

## 6. Depth & Elevation

### 阴影层级

| Token | 亮色 | 暗色 | 用途 |
|-------|------|------|------|
| `--shadow-card` | 微妙双层阴影 | `0 4px 20px / 0.3` | 默认卡片 |
| `--shadow-elevated` | `0 4px 24px / 0.1` | `0 8px 32px / 0.4` | 浮层、模态 |
| `--shadow-glow-primary` | `0 4px 20px / 0.15` | `0 0 20px / 0.15` | 主色发光（克制） |

### Blur 层级

| 级别 | 值 | 使用场景 |
|------|---|---------|
| `backdrop-blur-sm` | 4px | 次要浮层 |
| `backdrop-blur-md` | 12px | 头部栏 |
| `backdrop-blur-xl` | 24px | 主要卡片、模态 |
| `backdrop-blur-2xl` | 40px | Sidebar |

**禁止** 使用 `backdrop-blur-3xl`（64px），性能开销过大。
**禁止** 在已有 blur 容器内的子元素上再叠加 blur。

### Z-index 分层

| 层级 | 值 | 用途 |
|------|---|------|
| 基础内容 | `z-0` ~ `z-10` | 页面内容 |
| Sidebar | `z-40` | 侧边导航 |
| 模态/覆盖层 | `z-50` | Dialog、Chat Panel 浮层 |

### 圆角

基础圆角 `--radius: 0.875rem`（14px），组件通常使用 `rounded-xl` ~ `rounded-2xl`。

---

## 7. Do's and Don'ts

### ✅ Do

- 使用 CSS 变量和 Tailwind token，不硬编码颜色/间距
- 新增小号文字时使用 `text-micro`（不是 `text-[10px]`）
- Glow 效果只用于 1-2 个焦点元素（CTA 按钮、在线状态指示器）
- 动画使用 `prefers-reduced-motion` 降级
- 触摸目标 ≥ 44px

### ❌ Don't

- 不要在一个页面堆叠 3 种以上视觉特效（blob + particles + mesh + glow = 过度）
- 不要使用 `backdrop-blur-3xl`
- 不要在 blur 容器内嵌套 blur
- 不要使用无限循环动画（`infinite`）除非有明确的用户感知价值（如加载指示器）
- 不要在 className 中硬编码 hex 值（如 `bg-[#0d0f14]`）
- 不要引用不存在的 CSS 类（如 `glass-premium` 当前无定义）

---

## 8. Responsive Behavior

### 断点策略

| 断点 | 宽度 | 布局行为 |
|------|------|---------|
| 默认（mobile） | < 768px | Sidebar 隐藏（抽屉化），Chat 全屏 |
| `md` | ≥ 768px | Sidebar 可见，Chat + Canvas 二列 |
| `lg` | ≥ 1024px | Chat 38%，Canvas 62% |
| `xl` | ≥ 1280px | Chat 35%，Canvas 65%，内容区更宽 |

### 移动端适配

- Sidebar：`hidden md:flex`，移动端通过汉堡菜单触发
- Chat Panel：移动端全屏覆盖 `fixed inset-0 z-50`
- 所有可交互元素保持 44px 最小触摸目标

---

## 9. Agent Prompt Guide

当 AI Agent 修改此项目的 UI 时，请遵循以下规则：

1. **颜色**：只使用 `hsl(var(--xxx))` 格式。查阅 `src/index.css` 中的 `:root` 和 `.dark` 块获取可用变量。
2. **字号**：使用 `text-display` ~ `text-micro` token。禁止裸写 `text-[Npx]`。
3. **间距**：优先使用 `p-element`、`gap-component` 等语义化 token。
4. **Glassmorphism**：使用已定义的 `card-glass`、`glass-card` 等类，不要自行组合 blur + opacity。
5. **动画**：新增动画必须支持 `prefers-reduced-motion`。避免 `infinite` 关键帧。
6. **暗色模式**：所有新增样式必须同时考虑亮色和暗色。使用 `dark:` 前缀或 CSS 变量。
7. **Sidebar**：Sidebar 始终暗色，使用 `bg-sidebar`、`border-sidebar-border` 等 token。
8. **响应式**：新增布局必须考虑 `md:`、`lg:`、`xl:` 三个断点。
9. **性能**：每个页面最多 2 个 `backdrop-blur` 元素。禁止嵌套 blur。
