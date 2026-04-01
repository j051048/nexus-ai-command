import { useHotkeys } from '@/hooks/useHotkeys';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

export function GlobalHotkeys() {
  const navigate = useNavigate();
  const [searchOpen, setSearchOpen] = useState(false);

  // Ctrl+K: 打开搜索
  useHotkeys('ctrl+k', () => {
    setSearchOpen(true);
  });

  // Ctrl+N: 新建（根据当前页面）
  useHotkeys('ctrl+n', () => {
    // 可以根据当前路由触发不同的新建操作
    console.log('新建快捷键');
  });

  // Ctrl+/: 显示快捷键帮助
  useHotkeys('ctrl+/', () => {
    console.log('快捷键帮助');
  });

  return null;
}
