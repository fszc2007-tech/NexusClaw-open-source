import { App as AntdApp, ConfigProvider, theme } from 'antd';
import type { ReactNode } from 'react';

import './global.css';
import { I18nProvider } from '@/i18n/provider';
import { AppMessageBridge } from '@/services/notify';

const portalTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#0b6f79',
    colorInfo: '#0b6f79',
    colorSuccess: '#1d8a66',
    colorWarning: '#bf7a17',
    colorError: '#d14343',
    colorText: '#18303b',
    colorTextSecondary: '#637785',
    colorBorderSecondary: '#dde7ea',
    colorBgLayout: '#f2f7f7',
    colorBgContainer: '#ffffff',
    colorFillSecondary: '#eff5f5',
    borderRadius: 14,
    borderRadiusLG: 20,
    fontFamily:
      '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans SC", -apple-system, BlinkMacSystemFont, sans-serif',
    boxShadowSecondary: '0 18px 40px rgba(24, 48, 59, 0.08)',
  },
  components: {
    Button: {
      controlHeight: 42,
      borderRadius: 12,
      primaryShadow: '0 12px 24px rgba(11, 111, 121, 0.22)',
    },
    Card: {
      borderRadiusLG: 20,
      bodyPadding: 24,
    },
    Input: {
      controlHeight: 42,
      borderRadius: 12,
      activeBorderColor: '#0b6f79',
      hoverBorderColor: '#53a1ab',
    },
    Select: {
      controlHeight: 42,
      borderRadius: 12,
    },
    Tag: {
      borderRadiusSM: 999,
    },
    List: {
      itemPaddingSM: '16px 0',
    },
  },
};

export function rootContainer(container: ReactNode) {
  return (
    <ConfigProvider theme={portalTheme}>
      <AntdApp>
        <I18nProvider>
          <AppMessageBridge />
          {container}
        </I18nProvider>
      </AntdApp>
    </ConfigProvider>
  );
}
