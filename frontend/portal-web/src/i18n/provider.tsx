import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { defaultLocale, localeLabels, messages, type LocaleCode, type MessageValue } from './messages';

const STORAGE_KEY = 'nexusclaw-portal-locale';

type TranslateParams = Record<string, string | number | undefined | null>;

type I18nContextValue = {
  locale: LocaleCode;
  setLocale: (locale: LocaleCode) => void;
  t: (key: string, params?: TranslateParams) => string;
  tList: (key: string) => string[];
  localeOptions: Array<{ value: LocaleCode; label: string }>;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function normalizeLocale(rawLocale?: string | null): LocaleCode {
  if (!rawLocale) {
    return defaultLocale;
  }
  if (rawLocale === 'zh-Hant' || rawLocale === 'zh-TW' || rawLocale === 'zh-HK' || rawLocale === 'zh-MO') {
    return 'zh-Hant';
  }
  if (rawLocale === 'zh-Hans' || rawLocale.startsWith('zh-CN') || rawLocale.startsWith('zh-SG') || rawLocale.startsWith('zh')) {
    return 'zh-Hant';
  }
  if (rawLocale.startsWith('en')) {
    return 'en';
  }
  return defaultLocale;
}

function interpolate(template: string, params?: TranslateParams): string {
  if (!params) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(params[key] ?? ''));
}

function resolveMessage(locale: LocaleCode, key: string): MessageValue | undefined {
  return messages[locale][key] ?? messages[defaultLocale][key];
}

function getInitialLocale(): LocaleCode {
  if (typeof window === 'undefined') {
    return defaultLocale;
  }
  const storedLocale = window.localStorage.getItem(STORAGE_KEY);
  if (storedLocale) {
    return normalizeLocale(storedLocale);
  }
  return normalizeLocale(window.navigator.language);
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<LocaleCode>(getInitialLocale);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, locale);
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      setLocale: (nextLocale) => setLocaleState(normalizeLocale(nextLocale)),
      t: (key, params) => {
        const message = resolveMessage(locale, key);
        if (typeof message !== 'string') {
          return key;
        }
        return interpolate(message, params);
      },
      tList: (key) => {
        const message = resolveMessage(locale, key);
        return Array.isArray(message) ? message : [];
      },
      localeOptions: (Object.keys(localeLabels) as LocaleCode[])
        .filter((item) => item !== 'zh-Hans')
        .map((item) => ({
          value: item,
          label: localeLabels[item],
        })),
    }),
    [locale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider');
  }
  return context;
}
