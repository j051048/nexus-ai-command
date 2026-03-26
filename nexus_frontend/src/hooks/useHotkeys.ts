import { useHotkeys as useHotkeysHook } from 'react-hotkeys-hook';

export function useHotkeys() {
  useHotkeysHook('ctrl+k', () => console.log('命令面板'));
  useHotkeysHook('ctrl+n', () => console.log('新建任务'));
}
