import { askDemoProjectChat, buildDemoStreamMeta, getDemoSessionDetail, getDemoSessions } from './adminDemoApi';
import { API_BASE_URL, isAdminDemoMode, requestJson } from './client';
import { getAccessToken } from './authStore';

export type ChatSessionSummary = {
  session_id: string;
  title: string;
  source: string;
  status: string;
  selected_kb_ids: number[];
  summary?: string | null;
  state_json?: Record<string, unknown>;
  last_query?: string | null;
  last_answer?: string | null;
  last_active_at?: string | null;
};

export type ChatSessionTurn = {
  id: number;
  query: string;
  rewritten_query: string;
  answer: string;
  sources: Array<{
    knowledge_id: number;
    kb_id?: number;
    title: string;
    score?: number;
    snippet?: string;
  }>;
  used_memory: boolean;
  memory_snapshot?: Record<string, unknown> | null;
  safety_flags?: Record<string, unknown> | null;
  prompt_snapshot?: string | null;
  model_name?: string | null;
  trace_id?: string | null;
  created_at?: string | null;
};

export type ChatSessionDetail = {
  session_id: string;
  title: string;
  source: string;
  status: string;
  selected_kb_ids: number[];
  summary?: string | null;
  state_json?: Record<string, unknown>;
  turns: ChatSessionTurn[];
};

export type ChatAskResult = {
  project_id: number;
  session_id: string;
  query: string;
  query_raw: string;
  rewritten_query: string;
  answer: string;
  sources: ChatSessionTurn['sources'];
  use_memory: boolean;
  memory: {
    used: boolean;
    summary_hit: boolean;
    state_hit: boolean;
    preference_hit: boolean;
  };
  policy_basis: {
    source_mode: string;
    source_count: number;
    retrieval_usable?: boolean;
  };
  prompt_snapshot?: string | null;
  trace_id?: string | null;
};

export type ChatStreamMeta = {
  session_id: string;
  rewritten_query: string;
  sources: ChatSessionTurn['sources'];
  trace_id?: string | null;
  use_memory: boolean;
  retrieval_usable?: boolean;
};

export async function fetchProjectSessions(projectId: string) {
  if (isAdminDemoMode()) {
    return {
      code: 0,
      message: 'ok',
      data: getDemoSessions(Number(projectId)),
    };
  }
  return requestJson<ChatSessionSummary[]>(`/projects/${projectId}/chat/sessions`);
}

export async function fetchProjectSessionDetail(projectId: number, sessionId: string) {
  if (isAdminDemoMode()) {
    return getDemoSessionDetail(projectId, sessionId);
  }
  return (await requestJson<ChatSessionDetail>(`/projects/${projectId}/chat/sessions/${sessionId}`)).data;
}

export async function askProjectChat(
  projectId: number,
  payload: {
    session_id?: string | null;
    query: string;
    use_memory?: boolean;
    source?: string;
    selected_kb_ids?: number[];
    switches?: Record<string, boolean>;
  },
) {
  if (isAdminDemoMode()) {
    return askDemoProjectChat(projectId, payload);
  }
  return (
    await requestJson<ChatAskResult>(`/projects/${projectId}/chat/ask`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function streamProjectChat(
  projectId: number,
  payload: {
    session_id?: string | null;
    query: string;
    use_memory?: boolean;
    source?: string;
    selected_kb_ids?: number[];
    switches?: Record<string, boolean>;
  },
  handlers: {
    onMeta?: (payload: ChatStreamMeta) => void;
    onDelta?: (chunk: string) => void;
    onDone?: (payload: { session_id: string; answer: string; sources: ChatSessionTurn['sources']; trace_id?: string | null }) => void;
    onError?: (message: string) => void;
  },
) {
  if (isAdminDemoMode()) {
    const result = askDemoProjectChat(projectId, payload);
    const meta = buildDemoStreamMeta(result);
    handlers.onMeta?.(meta);
    const chunks = result.answer.match(/.{1,22}/g) || [result.answer];
    chunks.forEach((chunk) => handlers.onDelta?.(chunk));
    handlers.onDone?.({
      session_id: result.session_id,
      answer: result.answer,
      sources: result.sources,
      trace_id: result.trace_id,
    });
    return;
  }

  let response: Response;
  try {
    const accessToken = getAccessToken();
    response = await fetch(`${API_BASE_URL}/projects/${projectId}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('后端服务不可用，请确认 API 服务已启动，并检查 127.0.0.1:8000 是否可访问。');
    }
    throw error instanceof Error ? error : new Error('stream_request_failed');
  }

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    const detail =
      (errorPayload && typeof errorPayload === 'object' && 'detail' in errorPayload && String(errorPayload.detail)) ||
      response.statusText;
    throw new Error(detail || response.statusText || 'stream_request_failed');
  }

  if (!response.body) {
    throw new Error('stream_not_supported');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const processEventBlock = (block: string) => {
    const lines = block.split('\n');
    let eventName = 'message';
    const dataLines: string[] = [];

    lines.forEach((line) => {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    });

    const rawData = dataLines.join('\n');
    if (!rawData) {
      return;
    }

    const payload = JSON.parse(rawData) as Record<string, unknown>;
    if (eventName === 'meta') {
      handlers.onMeta?.(payload as ChatStreamMeta);
      return;
    }
    if (eventName === 'delta') {
      handlers.onDelta?.(String(payload.content || ''));
      return;
    }
    if (eventName === 'done') {
      handlers.onDone?.({
        session_id: String(payload.session_id || ''),
        answer: String(payload.answer || ''),
        sources: (payload.sources as ChatSessionTurn['sources']) || [],
        trace_id: payload.trace_id ? String(payload.trace_id) : null,
      });
      return;
    }
    if (eventName === 'error') {
      handlers.onError?.(String(payload.message || 'stream_error'));
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    let separatorIndex = buffer.indexOf('\n\n');
    while (separatorIndex >= 0) {
      const block = buffer.slice(0, separatorIndex).trim();
      buffer = buffer.slice(separatorIndex + 2);
      if (block) {
        processEventBlock(block);
      }
      separatorIndex = buffer.indexOf('\n\n');
    }
  }

  const trailingBlock = buffer.trim();
  if (trailingBlock) {
    processEventBlock(trailingBlock);
  }
}
