import { useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

type ShortcutHandler = () => void;

interface ShortcutConfig {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
  handler: ShortcutHandler;
  description: string;
  category: 'navigation' | 'action' | 'ai' | 'general';
}

// 检测是否是 Mac 系统
const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform);

// 获取修饰键显示文本
export function getModifierSymbol(modifier: 'ctrl' | 'meta' | 'shift' | 'alt'): string {
  if (isMac) {
    switch (modifier) {
      case 'ctrl': return '⌃';
      case 'meta': return '⌘';
      case 'shift': return '⇧';
      case 'alt': return '⌥';
    }
  } else {
    switch (modifier) {
      case 'ctrl': return 'Ctrl';
      case 'meta': return 'Win';
      case 'shift': return 'Shift';
      case 'alt': return 'Alt';
    }
  }
}

// 格式化快捷键显示
export function formatShortcut(config: Omit<ShortcutConfig, 'handler' | 'description' | 'category'>): string {
  const parts: string[] = [];
  
  if (config.ctrl) parts.push(getModifierSymbol('ctrl'));
  if (config.meta) parts.push(getModifierSymbol('meta'));
  if (config.alt) parts.push(getModifierSymbol('alt'));
  if (config.shift) parts.push(getModifierSymbol('shift'));
  
  parts.push(config.key.toUpperCase());
  
  return isMac ? parts.join('') : parts.join('+');
}

// 全局快捷键配置
const createShortcuts = (
  navigate: (path: string) => void,
  callbacks: {
    toggleAIChat?: () => void;
    openCommandPalette?: () => void;
    toggleSidebar?: () => void;
    toggleTheme?: () => void;
    save?: () => void;
    createNew?: () => void;
  }
): ShortcutConfig[] => [
  // 导航快捷键
  {
    key: 'd',
    meta: isMac,
    ctrl: !isMac,
    shift: true,
    handler: () => navigate('/dashboard'),
    description: '前往仪表盘',
    category: 'navigation',
  },
  {
    key: 'p',
    meta: isMac,
    ctrl: !isMac,
    shift: true,
    handler: () => navigate('/projects'),
    description: '前往项目管理',
    category: 'navigation',
  },
  {
    key: 'a',
    meta: isMac,
    ctrl: !isMac,
    shift: true,
    handler: () => navigate('/approval'),
    description: '前往审批中心',
    category: 'navigation',
  },
  {
    key: 's',
    meta: isMac,
    ctrl: !isMac,
    shift: true,
    handler: () => navigate('/sales'),
    description: '前往销售管理',
    category: 'navigation',
  },
  
  // AI 快捷键
  {
    key: '/',
    meta: isMac,
    ctrl: !isMac,
    handler: () => callbacks.toggleAIChat?.(),
    description: '打开/关闭 AI 助手',
    category: 'ai',
  },
  {
    key: 'k',
    meta: isMac,
    ctrl: !isMac,
    handler: () => callbacks.openCommandPalette?.(),
    description: '打开命令面板',
    category: 'ai',
  },
  
  // 通用快捷键
  {
    key: 'b',
    meta: isMac,
    ctrl: !isMac,
    handler: () => callbacks.toggleSidebar?.(),
    description: '切换侧边栏',
    category: 'general',
  },
  {
    key: 'j',
    meta: isMac,
    ctrl: !isMac,
    handler: () => callbacks.toggleTheme?.(),
    description: '切换主题',
    category: 'general',
  },
  
  // 操作快捷键
  {
    key: 'n',
    meta: isMac,
    ctrl: !isMac,
    handler: () => callbacks.createNew?.(),
    description: '新建',
    category: 'action',
  },
];

export function useKeyboardShortcuts(callbacks: {
  toggleAIChat?: () => void;
  openCommandPalette?: () => void;
  toggleSidebar?: () => void;
  toggleTheme?: () => void;
  save?: () => void;
  createNew?: () => void;
} = {}) {
  const navigate = useNavigate();
  const shortcutsRef = useRef<ShortcutConfig[]>([]);

  // 更新快捷键配置
  useEffect(() => {
    shortcutsRef.current = createShortcuts(navigate, callbacks);
  }, [navigate, callbacks]);

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // 忽略输入框中的快捷键（除了特定的全局快捷键）
    const target = event.target as HTMLElement;
    const isInputField = 
      target.tagName === 'INPUT' || 
      target.tagName === 'TEXTAREA' || 
      target.isContentEditable;

    // 命令面板快捷键在任何情况下都应该工作
    const isCommandPaletteShortcut = 
      event.key === 'k' && (event.metaKey || event.ctrlKey);

    if (isInputField && !isCommandPaletteShortcut) {
      return;
    }

    for (const shortcut of shortcutsRef.current) {
      const metaMatch = shortcut.meta ? (isMac ? event.metaKey : event.ctrlKey) : true;
      const ctrlMatch = shortcut.ctrl ? event.ctrlKey : !shortcut.meta || !event.ctrlKey;
      const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;
      const altMatch = shortcut.alt ? event.altKey : !event.altKey;
      const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();

      if (metaMatch && ctrlMatch && shiftMatch && altMatch && keyMatch) {
        event.preventDefault();
        event.stopPropagation();
        shortcut.handler();
        return;
      }
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return {
    shortcuts: shortcutsRef.current,
    formatShortcut,
    getModifierSymbol,
  };
}

// 单独的快捷键 Hook，用于特定组件
export function useShortcut(
  key: string,
  handler: ShortcutHandler,
  options: {
    ctrl?: boolean;
    meta?: boolean;
    shift?: boolean;
    alt?: boolean;
    enabled?: boolean;
  } = {}
) {
  const { ctrl, meta, shift, alt, enabled = true } = options;

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      const metaMatch = meta ? event.metaKey : !event.metaKey;
      const ctrlMatch = ctrl ? event.ctrlKey : !event.ctrlKey;
      const shiftMatch = shift ? event.shiftKey : !event.shiftKey;
      const altMatch = alt ? event.altKey : !event.altKey;
      const keyMatch = event.key.toLowerCase() === key.toLowerCase();

      if (metaMatch && ctrlMatch && shiftMatch && altMatch && keyMatch) {
        event.preventDefault();
        handler();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [key, handler, ctrl, meta, shift, alt, enabled]);
}

export default useKeyboardShortcuts;