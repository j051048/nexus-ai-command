/**
 * 统一的 Toast 提示辅助函数
 * 提供一致的操作反馈体验
 */
import { toast } from 'sonner';

export const toastHelpers = {
  // 成功提示
  success: (message: string, description?: string) => {
    toast.success(message, {
      description,
      duration: 3000,
    });
  },

  // 错误提示
  error: (message: string, description?: string) => {
    toast.error(message, {
      description,
      duration: 4000,
    });
  },

  // 警告提示
  warning: (message: string, description?: string) => {
    toast.warning(message, {
      description,
      duration: 3500,
    });
  },

  // 加载提示（返回 dismiss 函数）
  loading: (message: string) => {
    return toast.loading(message);
  },

  // Promise 操作提示
  promise: <T,>(
    promise: Promise<T>,
    messages: {
      loading: string;
      success: string;
      error: string;
    }
  ) => {
    return toast.promise(promise, messages);
  },
};
