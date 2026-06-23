import { App } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';
import { useLayoutEffect } from 'react';

type MessageProxy = Pick<MessageInstance, 'open' | 'success' | 'info' | 'warning' | 'error' | 'loading' | 'destroy'>;

let messageApi: MessageInstance | null = null;

function withMessageApi<T>(callback: (api: MessageInstance) => T, fallback: T): T {
  if (!messageApi) {
    return fallback;
  }
  return callback(messageApi);
}

export const message: MessageProxy = {
  open: (...args) => withMessageApi((api) => api.open(...args), null as ReturnType<MessageInstance['open']>),
  success: (...args) => withMessageApi((api) => api.success(...args), null as ReturnType<MessageInstance['success']>),
  info: (...args) => withMessageApi((api) => api.info(...args), null as ReturnType<MessageInstance['info']>),
  warning: (...args) => withMessageApi((api) => api.warning(...args), null as ReturnType<MessageInstance['warning']>),
  error: (...args) => withMessageApi((api) => api.error(...args), null as ReturnType<MessageInstance['error']>),
  loading: (...args) => withMessageApi((api) => api.loading(...args), null as ReturnType<MessageInstance['loading']>),
  destroy: (key) => withMessageApi((api) => api.destroy(key), undefined),
};

export function AppMessageBridge() {
  const { message } = App.useApp();

  useLayoutEffect(() => {
    messageApi = message;
    return () => {
      if (messageApi === message) {
        messageApi = null;
      }
    };
  }, [message]);

  return null;
}
