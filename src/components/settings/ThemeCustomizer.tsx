/**
 * P2 UX Enhancement: Theme Customizer
 * 主题定制器组件
 */

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetFooter,
} from '@/components/ui/sheet';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Paintbrush,
  Sun,
  Moon,
  Monitor,
  Check,
  RotateCcw,
  Type,
  Circle,
  Palette,
  Sparkles,
  Eye,
} from 'lucide-react';
import {
  useEnhancedTheme,
  ThemeMode,
  ThemeSettings,
} from '@/contexts/EnhancedThemeContext';
import { toast } from 'sonner';

// ==================== 子组件 ====================

function ModeSelector() {
  const { mode, setMode } = useEnhancedTheme();

  const modes: { value: ThemeMode; label: string; icon: React.ReactNode }[] = [
    { value: 'light', label: '浅色', icon: <Sun className="w-4 h-4" /> },
    { value: 'dark', label: '深色', icon: <Moon className="w-4 h-4" /> },
    { value: 'system', label: '跟随系统', icon: <Monitor className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-3">
      <Label className="text-sm font-medium">外观模式</Label>
      <div className="grid grid-cols-3 gap-2">
        {modes.map(({ value, label, icon }) => (
          <button
            key={value}
            onClick={() => setMode(value)}
            className={cn(
              'flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all',
              'hover:bg-muted/50',
              mode === value
                ? 'border-primary bg-primary/5'
                : 'border-transparent bg-muted/30'
            )}
          >
            <div className={cn(
              'p-2 rounded-md',
              mode === value ? 'bg-primary text-primary-foreground' : 'bg-muted'
            )}>
              {icon}
            </div>
            <span className="text-xs font-medium">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function PresetSelector() {
  const { preset, setPreset, presets, resolvedMode } = useEnhancedTheme();

  const filteredPresets = presets.filter((p) => p.mode === resolvedMode);

  return (
    <div className="space-y-3">
      <Label className="text-sm font-medium">主题预设</Label>
      <div className="grid grid-cols-2 gap-2">
        {filteredPresets.map((p) => (
          <button
            key={p.id}
            onClick={() => setPreset(p.id)}
            className={cn(
              'relative flex items-center gap-3 p-3 rounded-lg border-2 transition-all text-left',
              'hover:bg-muted/50',
              preset === p.id
                ? 'border-primary bg-primary/5'
                : 'border-transparent bg-muted/30'
            )}
          >
            <div
              className="w-8 h-8 rounded-full shadow-inner"
              style={{
                background: `linear-gradient(135deg, hsl(${p.colors.primary}) 0%, hsl(${p.colors.accent}) 100%)`,
              }}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{p.name}</p>
              {p.description && (
                <p className="text-xs text-muted-foreground truncate">
                  {p.description}
                </p>
              )}
            </div>
            {preset === p.id && (
              <Check className="w-4 h-4 text-primary flex-shrink-0" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function FontSizeSelector() {
  const { settings, setFontSize } = useEnhancedTheme();

  const sizes: { value: ThemeSettings['fontSize']; label: string }[] = [
    { value: 'sm', label: '小' },
    { value: 'base', label: '中' },
    { value: 'lg', label: '大' },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">字体大小</Label>
        <span className="text-xs text-muted-foreground">
          {sizes.find((s) => s.value === settings.fontSize)?.label}
        </span>
      </div>
      <div className="flex gap-2">
        {sizes.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setFontSize(value)}
            className={cn(
              'flex-1 py-2 px-3 rounded-md border-2 transition-all',
              'hover:bg-muted/50',
              settings.fontSize === value
                ? 'border-primary bg-primary/5'
                : 'border-transparent bg-muted/30'
            )}
          >
            <Type
              className={cn(
                'mx-auto',
                value === 'sm' && 'w-3 h-3',
                value === 'base' && 'w-4 h-4',
                value === 'lg' && 'w-5 h-5'
              )}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

function RadiusSelector() {
  const { settings, setRadius } = useEnhancedTheme();

  const radiusOptions: { value: ThemeSettings['radius']; label: string }[] = [
    { value: 'none', label: '无' },
    { value: 'sm', label: '小' },
    { value: 'md', label: '中' },
    { value: 'lg', label: '大' },
    { value: 'full', label: '圆' },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium">圆角大小</Label>
        <span className="text-xs text-muted-foreground">
          {radiusOptions.find((r) => r.value === settings.radius)?.label}
        </span>
      </div>
      <div className="flex gap-2">
        {radiusOptions.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setRadius(value)}
            className={cn(
              'flex-1 py-2 px-2 rounded-md border-2 transition-all',
              'hover:bg-muted/50',
              settings.radius === value
                ? 'border-primary bg-primary/5'
                : 'border-transparent bg-muted/30'
            )}
          >
            <div
              className={cn(
                'w-6 h-6 mx-auto bg-primary/50 border-2 border-primary',
                value === 'none' && 'rounded-none',
                value === 'sm' && 'rounded-sm',
                value === 'md' && 'rounded',
                value === 'lg' && 'rounded-lg',
                value === 'full' && 'rounded-full'
              )}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

function AccessibilitySettings() {
  const { settings, setReducedMotion } = useEnhancedTheme();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label className="text-sm font-medium">减弱动画</Label>
          <p className="text-xs text-muted-foreground">
            减少或移除界面动画效果
          </p>
        </div>
        <Switch
          checked={settings.reducedMotion}
          onCheckedChange={setReducedMotion}
        />
      </div>
    </div>
  );
}

function PreviewCard() {
  return (
    <div className="p-4 bg-card border rounded-lg space-y-3">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center">
          <Sparkles className="w-5 h-5 text-primary-foreground" />
        </div>
        <div>
          <p className="font-medium">预览卡片</p>
          <p className="text-sm text-muted-foreground">这是一个示例卡片</p>
        </div>
      </div>
      <div className="flex gap-2">
        <Button size="sm">主要按钮</Button>
        <Button size="sm" variant="outline">次要按钮</Button>
        <Button size="sm" variant="ghost">文字按钮</Button>
      </div>
      <div className="flex gap-2">
        <span className="px-2 py-1 text-xs bg-primary/10 text-primary rounded">标签</span>
        <span className="px-2 py-1 text-xs bg-green-500/10 text-green-500 rounded">成功</span>
        <span className="px-2 py-1 text-xs bg-yellow-500/10 text-yellow-500 rounded">警告</span>
      </div>
    </div>
  );
}

// ==================== 主组件 ====================

interface ThemeCustomizerProps {
  trigger?: React.ReactNode;
}

export function ThemeCustomizer({ trigger }: ThemeCustomizerProps) {
  const { resetToDefaults, preset } = useEnhancedTheme();
  const [open, setOpen] = useState(false);

  const handleReset = () => {
    resetToDefaults();
    toast.success('已恢复默认设置');
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        {trigger || (
          <Button variant="outline" size="icon">
            <Paintbrush className="w-4 h-4" />
          </Button>
        )}
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-md p-0">
        <SheetHeader className="p-6 pb-0">
          <SheetTitle className="flex items-center gap-2">
            <Palette className="w-5 h-5" />
            主题定制
          </SheetTitle>
          <SheetDescription>
            自定义应用的外观和体验
          </SheetDescription>
        </SheetHeader>

        <Tabs defaultValue="appearance" className="flex-1">
          <div className="px-6">
            <TabsList className="w-full">
              <TabsTrigger value="appearance" className="flex-1">
                <Eye className="w-4 h-4 mr-2" />
                外观
              </TabsTrigger>
              <TabsTrigger value="style" className="flex-1">
                <Palette className="w-4 h-4 mr-2" />
                样式
              </TabsTrigger>
              <TabsTrigger value="a11y" className="flex-1">
                <Circle className="w-4 h-4 mr-2" />
                无障碍
              </TabsTrigger>
            </TabsList>
          </div>

          <ScrollArea className="h-[calc(100vh-16rem)] px-6 py-4">
            <TabsContent value="appearance" className="mt-0 space-y-6">
              <ModeSelector />
              <PresetSelector />
            </TabsContent>

            <TabsContent value="style" className="mt-0 space-y-6">
              <FontSizeSelector />
              <RadiusSelector />
              
              <div className="space-y-3">
                <Label className="text-sm font-medium">效果预览</Label>
                <PreviewCard />
              </div>
            </TabsContent>

            <TabsContent value="a11y" className="mt-0 space-y-6">
              <AccessibilitySettings />
              
              <div className="p-4 bg-muted/50 rounded-lg">
                <h4 className="text-sm font-medium mb-2">无障碍提示</h4>
                <ul className="text-xs text-muted-foreground space-y-1">
                  <li>• 使用 Tab 键在元素间导航</li>
                  <li>• 按 Enter 或空格激活按钮</li>
                  <li>• 按 Escape 关闭对话框</li>
                  <li>• 使用 ⌘K 打开命令面板</li>
                </ul>
              </div>
            </TabsContent>
          </ScrollArea>
        </Tabs>

        <SheetFooter className="p-6 pt-0 border-t mt-auto">
          <Button
            variant="outline"
            onClick={handleReset}
            className="w-full"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            恢复默认
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export default ThemeCustomizer;