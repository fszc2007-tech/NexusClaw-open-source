export type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

const DEFAULT_API_BASE_URL = '/api/v1';
const NETWORK_ERROR_MESSAGE = '后端服务不可用，请确认 API 服务已启动，并检查 127.0.0.1:8000 是否可访问。';

export const API_BASE_URL = (process.env.UMI_APP_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, '');

function buildUrl(path: string) {
  return path.startsWith('http://') || path.startsWith('https://') ? path : `${API_BASE_URL}${path}`;
}

function normalizeRequestError(error: unknown) {
  if (error instanceof TypeError) {
    return new Error(NETWORK_ERROR_MESSAGE);
  }
  return error instanceof Error ? error : new Error('请求失败');
}

async function parseResponse<T>(response: Response): Promise<ApiEnvelope<T>> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      (payload && typeof payload === 'object' && 'detail' in payload && String(payload.detail)) || response.statusText;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return payload as ApiEnvelope<T>;
}

export async function requestJson<T>(path: string, options?: RequestInit): Promise<ApiEnvelope<T>> {
  try {
    const response = await fetch(buildUrl(path), {
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
      ...options,
    });

    return parseResponse<T>(response);
  } catch (error) {
    throw normalizeRequestError(error);
  }
}
