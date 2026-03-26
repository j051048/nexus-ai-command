# 前端紧急搭建指南（P0 优先级）

## 第一步：安装基础依赖（5 分钟）

```bash
cd nexus_frontend
npm install react-router-dom@6 zustand@4 @tanstack/react-query@5
npm install @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-toast
npm install lucide-react clsx tailwind-merge
npm install -D @types/node
```

## 第二步：创建基础目录结构（2 分钟）

```bash
mkdir -p src/{pages,layouts,lib,api,store}
```

## 第三步：创建核心配置文件

### 3.1 创建 TailwindCSS 配置
文件：`tailwind.config.js`

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
      },
    },
  },
  plugins: [],
}
```

### 3.2 创建全局样式
文件：`src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --border: 217.2 32.6% 17.5%;
  }
}
```

## 第四步：创建最小可用页面（10 分钟）

按照下一个文件的指示创建页面...
