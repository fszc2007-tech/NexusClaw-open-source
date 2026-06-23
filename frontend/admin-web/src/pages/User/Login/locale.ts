import type { LocaleCode } from '@/i18n/messages';

/** 右上角语言切换顺序与按钮文案（完整文案在 `src/i18n/messages.ts`） */
export const LOGIN_LOCALE_ORDER: LocaleCode[] = ['zh-Hans', 'zh-Hant', 'en'];

export const LOCALE_SWITCH_LABELS: Record<LocaleCode, string> = {
  'zh-Hans': '简',
  'zh-Hant': '繁',
  en: 'EN',
};
