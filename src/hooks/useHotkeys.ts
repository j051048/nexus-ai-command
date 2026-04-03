import { useEffect } from 'react';

type KeyHandler = (event: KeyboardEvent) => void;

export function useHotkeys(key: string, handler: KeyHandler, deps: unknown[] = []) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const keys = key.toLowerCase().split('+');
      const ctrl = keys.includes('ctrl') || keys.includes('cmd');
      const shift = keys.includes('shift');
      const alt = keys.includes('alt');
      const mainKey = keys[keys.length - 1];

      const ctrlPressed = event.ctrlKey || event.metaKey;
      const shiftPressed = event.shiftKey;
      const altPressed = event.altKey;
      const keyPressed = event.key.toLowerCase();

      if (
        (!ctrl || ctrlPressed) &&
        (!shift || shiftPressed) &&
        (!alt || altPressed) &&
        keyPressed === mainKey
      ) {
        event.preventDefault();
        handler(event);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, handler, ...deps]);
}

