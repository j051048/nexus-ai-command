/**
 * Animation Showcase - 动画效果展示页面
 * 用于开发和测试动画组件
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  FadeInView,
  StaggerList,
  AnimatedNumber,
  TypewriterText,
  AnimatedProgress,
  PulseDot,
  Spinner,
  HoverCardAnimated,
  ShakeWrapper,
} from '@/components/common/AnimatedComponents';
import {
  useCountUp,
  useTypewriter,
  usePulse,
  useInView,
  usePrefersReducedMotion,
  getEnterAnimationClass,
  getHoverAnimationClass,
} from '@/lib/animations';
import {
  Zap,
  TrendingUp,
  Users,
  DollarSign,
  RefreshCw,
  Play,
  AlertCircle,
  CheckCircle,
  Clock,
  Sparkles,
} from 'lucide-react';

export default function AnimationShowcase() {
  const [shakeError, setShakeError] = useState(false);
  const [progressValue, setProgressValue] = useState(65);
  const [counterKey, setCounterKey] = useState(0);
  const prefersReducedMotion = usePrefersReducedMotion();

  const triggerShake = () => {
    setShakeError(true);
    setTimeout(() => setShakeError(false), 500);
  };

  const resetProgress = () => {
    setProgressValue(0);
    setTimeout(() => setProgressValue(Math.floor(Math.random() * 100)), 100);
  };

  const sampleItems = [
    { icon: <TrendingUp className="w-5 h-5" />, label: '销售增长', value: '+23%' },
    { icon: <Users className="w-5 h-5" />, label: '新客户', value: '156' },
    { icon: <DollarSign className="w-5 h-5" />, label: '总收入', value: '¥2.4M' },
    { icon: <Zap className="w-5 h-5" />, label: '转化率', value: '12.5%' },
  ];

  return (
    <div className="min-h-screen bg-background p-6 md:p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Header */}
        <FadeInView animation="slide-up" duration="normal">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <Sparkles className="w-8 h-8 text-primary" />
              <h1 className="text-3xl font-bold">动画组件展示</h1>
            </div>
            <p className="text-muted-foreground">
              Nexus AI SaaS 动画工具库演示
              {prefersReducedMotion && (
                <Badge variant="secondary" className="ml-2">
                  已启用减弱动画
                </Badge>
              )}
            </p>
          </div>
        </FadeInView>

        <Tabs defaultValue="components" className="space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-3">
            <TabsTrigger value="components">组件</TabsTrigger>
            <TabsTrigger value="hooks">Hooks</TabsTrigger>
            <TabsTrigger value="css">CSS 动画</TabsTrigger>
          </TabsList>

          {/* Components Tab */}
          <TabsContent value="components" className="space-y-6">
            {/* Fade In View */}
            <Card>
              <CardHeader>
                <CardTitle>FadeInView - 视口淡入</CardTitle>
                <CardDescription>
                  当元素进入视口时触发动画，支持多种动画类型
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <FadeInView animation="fade" className="p-4 bg-muted rounded-lg text-center">
                    <p className="font-medium">淡入</p>
                  </FadeInView>
                  <FadeInView animation="slide-up" delay={100} className="p-4 bg-muted rounded-lg text-center">
                    <p className="font-medium">上滑</p>
                  </FadeInView>
                  <FadeInView animation="slide-left" delay={200} className="p-4 bg-muted rounded-lg text-center">
                    <p className="font-medium">左滑</p>
                  </FadeInView>
                  <FadeInView animation="scale" delay={300} className="p-4 bg-muted rounded-lg text-center">
                    <p className="font-medium">缩放</p>
                  </FadeInView>
                </div>
              </CardContent>
            </Card>

            {/* Stagger List */}
            <Card>
              <CardHeader>
                <CardTitle>StaggerList - 交错动画列表</CardTitle>
                <CardDescription>
                  列表项依次进入，形成流畅的视觉效果
                </CardDescription>
              </CardHeader>
              <CardContent>
                <StaggerList
                  className="grid grid-cols-2 md:grid-cols-4 gap-4"
                  itemClassName="p-4 bg-muted rounded-lg"
                  animation="slide-up"
                  staggerDelay={80}
                >
                  {sampleItems.map((item) => (
                    <div key={item.label} className="flex items-center gap-3">
                      <div className="p-2 bg-primary/10 rounded-lg text-primary">
                        {item.icon}
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">{item.label}</p>
                        <p className="font-semibold">{item.value}</p>
                      </div>
                    </div>
                  ))}
                </StaggerList>
              </CardContent>
            </Card>

            {/* Animated Number */}
            <Card>
              <CardHeader>
                <CardTitle>AnimatedNumber - 数字动画</CardTitle>
                <CardDescription>
                  数字递增动画，适用于统计数据展示
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-8">
                  <div className="text-center" key={counterKey}>
                    <AnimatedNumber
                      value={1234567}
                      duration={1500}
                      prefix="¥"
                      className="text-4xl font-bold text-primary mono-number"
                    />
                    <p className="text-sm text-muted-foreground mt-1">总收入</p>
                  </div>
                  <div className="text-center" key={counterKey + 1}>
                    <AnimatedNumber
                      value={89.7}
                      duration={1200}
                      decimals={1}
                      suffix="%"
                      className="text-4xl font-bold text-green-500 mono-number"
                    />
                    <p className="text-sm text-muted-foreground mt-1">完成率</p>
                  </div>
                  <div className="text-center" key={counterKey + 2}>
                    <AnimatedNumber
                      value={2847}
                      duration={1000}
                      className="text-4xl font-bold text-orange-500 mono-number"
                    />
                    <p className="text-sm text-muted-foreground mt-1">活跃用户</p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => setCounterKey((k) => k + 10)}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  重新播放
                </Button>
              </CardContent>
            </Card>

            {/* Typewriter */}
            <Card>
              <CardHeader>
                <CardTitle>TypewriterText - 打字机效果</CardTitle>
                <CardDescription>
                  模拟逐字输入效果，适用于 AI 对话等场景
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-muted rounded-lg min-h-[60px]">
                  <TypewriterText
                    text="你好！我是 Nexus AI 助手，很高兴为你服务。有什么我可以帮助你的吗？"
                    speed={40}
                    cursor
                    className="text-lg"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Progress */}
            <Card>
              <CardHeader>
                <CardTitle>AnimatedProgress - 动画进度条</CardTitle>
                <CardDescription>
                  平滑的进度条动画
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <AnimatedProgress value={progressValue} showLabel duration={1000} />
                <div className="flex gap-3">
                  <Button variant="outline" size="sm" onClick={resetProgress}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    随机进度
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Status Indicators */}
            <Card>
              <CardHeader>
                <CardTitle>状态指示器</CardTitle>
                <CardDescription>
                  脉冲点和加载动画
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-8">
                  <div className="flex items-center gap-3">
                    <PulseDot color="success" size="md" />
                    <span>在线</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <PulseDot color="warning" size="md" />
                    <span>处理中</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <PulseDot color="destructive" size="md" />
                    <span>离线</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Spinner size="sm" />
                    <span>加载中</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Spinner size="md" />
                    <span>加载中 (中)</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Spinner size="lg" />
                    <span>加载中 (大)</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Hover Cards */}
            <Card>
              <CardHeader>
                <CardTitle>HoverCardAnimated - 悬浮卡片</CardTitle>
                <CardDescription>
                  鼠标悬停时的平滑提升效果
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {['项目 Alpha', '项目 Beta', '项目 Gamma'].map((name) => (
                    <HoverCardAnimated
                      key={name}
                      className="p-6 bg-card border rounded-xl cursor-pointer"
                    >
                      <h3 className="font-semibold mb-2">{name}</h3>
                      <p className="text-sm text-muted-foreground">
                        悬停查看动画效果
                      </p>
                    </HoverCardAnimated>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Shake Animation */}
            <Card>
              <CardHeader>
                <CardTitle>ShakeWrapper - 抖动效果</CardTitle>
                <CardDescription>
                  用于错误提示或需要用户注意的场景
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4">
                  <ShakeWrapper trigger={shakeError}>
                    <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg flex items-center gap-3">
                      <AlertCircle className="w-5 h-5 text-destructive" />
                      <span>验证码错误，请重新输入</span>
                    </div>
                  </ShakeWrapper>
                  <Button variant="destructive" size="sm" onClick={triggerShake}>
                    触发抖动
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Hooks Tab */}
          <TabsContent value="hooks" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>useCountUp</CardTitle>
                <CardDescription>
                  数字递增动画 Hook，支持自定义缓动函数
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto">
{`const [count, startAnimation, reset] = useCountUp(1000, 1500, {
  startFrom: 0,
  decimals: 2,
  easing: 'easeOutQuart',
});`}
                </pre>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>useInView</CardTitle>
                <CardDescription>
                  视口检测 Hook，支持阈值和边距配置
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto">
{`const [ref, inView] = useInView({
  threshold: 0.5,
  rootMargin: '50px',
  triggerOnce: true,
  onChange: (inView) => console.log(inView),
});`}
                </pre>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>useTypewriter</CardTitle>
                <CardDescription>
                  打字机效果 Hook，支持速度、延迟和回调
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto">
{`const { displayText, isTyping, reset } = useTypewriter(text, {
  speed: 50,
  delay: 1000,
  cursor: true,
  onComplete: () => console.log('Done!'),
});`}
                </pre>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>usePrefersReducedMotion</CardTitle>
                <CardDescription>
                  检测用户是否偏好减弱动画，实现无障碍支持
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto">
{`const prefersReducedMotion = usePrefersReducedMotion();

// 根据用户偏好调整动画
if (prefersReducedMotion) {
  // 使用简化的动画或完全跳过
}`}
                </pre>
                <div className="mt-4 p-3 bg-muted rounded-lg">
                  <p className="text-sm">
                    当前状态：
                    <Badge variant={prefersReducedMotion ? 'secondary' : 'default'} className="ml-2">
                      {prefersReducedMotion ? '减弱动画已启用' : '正常动画'}
                    </Badge>
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>更多 Hooks</CardTitle>
                <CardDescription>
                  查看 src/lib/animations.ts 获取完整的 Hooks 列表
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {[
                    'useScrollProgress',
                    'useParallax',
                    'useSpringValue',
                    'useMousePosition',
                    'useAnimationState',
                    'useDelayedShow',
                    'useDelayedHide',
                    'usePulse',
                  ].map((hook) => (
                    <div
                      key={hook}
                      className="p-3 bg-muted rounded-lg text-sm font-mono"
                    >
                      {hook}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* CSS Animations Tab */}
          <TabsContent value="css" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>CSS 动画类</CardTitle>
                <CardDescription>
                  可直接在 className 中使用的动画类
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { name: 'animate-fade-slide-up', label: '淡入上滑' },
                    { name: 'animate-fade-slide-down', label: '淡入下滑' },
                    { name: 'animate-scale-fade-in', label: '缩放淡入' },
                    { name: 'animate-pop-in', label: '弹出' },
                    { name: 'animate-blur-fade-in', label: '模糊淡入' },
                    { name: 'animate-rotate-in', label: '旋转进入' },
                    { name: 'animate-bounce-subtle', label: '轻微弹跳' },
                    { name: 'animate-glow-pulse', label: '发光脉冲' },
                  ].map((anim, index) => (
                    <div
                      key={anim.name}
                      className={`p-4 bg-muted rounded-lg text-center ${anim.name}`}
                      style={{ animationDelay: `${index * 100}ms` }}
                    >
                      <p className="font-medium">{anim.label}</p>
                      <p className="text-xs text-muted-foreground mt-1 font-mono">
                        {anim.name}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>悬浮效果类</CardTitle>
                <CardDescription>
                  使用 getHoverAnimationClass() 生成悬浮效果
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { effect: 'lift' as const, label: '提升' },
                    { effect: 'glow' as const, label: '发光' },
                    { effect: 'scale' as const, label: '缩放' },
                    { effect: 'brightness' as const, label: '亮度' },
                  ].map((item) => (
                    <div
                      key={item.effect}
                      className={`p-6 bg-card border rounded-lg text-center cursor-pointer ${getHoverAnimationClass(item.effect)}`}
                    >
                      <p className="font-medium">{item.label}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        hover: {item.effect}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>工具类</CardTitle>
                <CardDescription>
                  实用的动画辅助类
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="p-4 bg-muted rounded-lg hover-lift">
                      <p className="font-medium">hover-lift</p>
                      <p className="text-xs text-muted-foreground">悬浮提升效果</p>
                    </div>
                    <div className="p-4 bg-muted rounded-lg float">
                      <p className="font-medium">float</p>
                      <p className="text-xs text-muted-foreground">浮动动画</p>
                    </div>
                    <div className="p-4 bg-muted rounded-lg shimmer h-16 w-24" />
                    <div>
                      <p className="font-medium">shimmer</p>
                      <p className="text-xs text-muted-foreground">闪烁加载效果</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Framer Motion 预设</CardTitle>
                <CardDescription>
                  可与 Framer Motion 配合使用的动画配置
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto">
{`import { fadeInUp, staggerContainer, staggerItem, springPresets } from '@/lib/animations';

<motion.div variants={staggerContainer} initial="initial" animate="animate">
  {items.map((item) => (
    <motion.div key={item.id} variants={staggerItem}>
      {item.content}
    </motion.div>
  ))}
</motion.div>

// 弹簧预设
<motion.button whileTap={{ scale: 0.95 }} transition={springPresets.snappy}>
  点击
</motion.button>`}
                </pre>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}