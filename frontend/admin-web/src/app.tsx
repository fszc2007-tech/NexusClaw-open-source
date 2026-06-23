import { App as AntdApp, ConfigProvider, theme } from 'antd';
import type { ReactNode } from 'react';

import './global.css';
import { I18nProvider } from '@/i18n/provider';
import { AppMessageBridge } from '@/services/notify';

const adminTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#2563eb',
    colorInfo: '#2563eb',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorText: '#1f2a44',
    colorTextSecondary: '#64748b',
    colorBorderSecondary: 'rgba(217, 226, 240, 0.88)',
    colorBgLayout: '#f6f8fc',
    colorBgContainer: 'rgba(255,255,255,0.92)',
    colorFillSecondary: 'rgba(241, 245, 252, 0.92)',
    borderRadius: 18,
    borderRadiusLG: 28,
    boxShadowSecondary: '0 20px 48px rgba(15, 23, 42, 0.06)',
    fontSize: 15,
    fontSizeSM: 13,
    fontSizeLG: 17,
    fontFamily:
      '"SF Pro Text", "SF Pro Display", -apple-system, BlinkMacSystemFont, "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif',
  },
  components: {
    Layout: {
      headerBg: 'rgba(255,255,255,0.82)',
      siderBg: '#ffffff',
      bodyBg: 'transparent',
    },
    Card: {
      borderRadiusLG: 28,
      bodyPadding: 24,
      headerBg: 'transparent',
    },
    Button: {
      controlHeight: 40,
      borderRadius: 18,
      defaultShadow: '0 8px 18px rgba(148, 163, 184, 0.12)',
      primaryShadow: '0 14px 28px rgba(37, 99, 235, 0.24)',
    },
    Input: {
      controlHeight: 42,
      borderRadius: 16,
      activeBorderColor: '#6d8eff',
      hoverBorderColor: '#8cabff',
    },
    InputNumber: {
      controlHeight: 42,
      borderRadius: 16,
    },
    Select: {
      controlHeight: 42,
      borderRadius: 16,
    },
    Table: {
      headerBg: 'rgba(243, 247, 252, 0.96)',
      headerBorderRadius: 18,
      rowHoverBg: 'rgba(237, 244, 255, 0.92)',
      borderColor: 'rgba(223, 231, 243, 0.92)',
    },
    Tag: {
      borderRadiusSM: 999,
    },
    Modal: {
      borderRadiusLG: 28,
    },
    Drawer: {
      borderRadiusLG: 28,
    },
    Menu: {
      itemBg: 'transparent',
      subMenuItemBg: 'transparent',
      itemColor: '#53627b',
      itemHoverColor: '#1d4ed8',
      itemSelectedColor: '#1d4ed8',
      itemSelectedBg: '#edf4ff',
      itemHoverBg: '#f4f7fd',
      itemBorderRadius: 14,
    },
    Statistic: {
      contentFontSize: 30,
    },
  },
};

export function rootContainer(container: ReactNode) {
  return (
    <ConfigProvider theme={adminTheme}>
      <AntdApp>
        <I18nProvider>
          <AppMessageBridge />
          {container}
        </I18nProvider>
      </AntdApp>
    </ConfigProvider>
  );
}
