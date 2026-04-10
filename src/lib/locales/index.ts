/**
 * Locale files index — centralized translation exports
 * P0: i18n full coverage
 */
import zhCN from './zh-CN';
import enUS from './en-US';
import jaJP from './ja-JP';

export const localeMessages = {
  'zh-CN': zhCN,
  'en-US': enUS,
  'ja-JP': jaJP,
} as const;

export type LocaleMessageKey = keyof typeof zhCN;
