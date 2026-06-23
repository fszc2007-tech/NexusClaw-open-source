import { API_BASE_URL, requestJson } from './client';

export type ChatAskPayload = {
  session_id?: string;
  query: string;
  use_memory?: boolean;
  source?: string;
  selected_kb_ids?: number[];
  switches?: Record<string, boolean>;
};

export type ChatAskResponse = {
  project_id: number;
  session_id: string;
  query: string;
  query_raw: string;
  rewritten_query: string;
  answer: string;
  suggested_actions?: SuggestedAction[];
  response_mode?: 'knowledge' | 'scene';
  scene?: ScenePayload | null;
  sources: Array<{
    knowledge_id: number;
    kb_id: number;
    title: string;
    document_name?: string | null;
    source_url?: string | null;
    source_org?: string | null;
    score: number;
    snippet: string;
  }>;
  use_memory: boolean;
  memory?: {
    used: boolean;
    summary_hit: boolean;
    state_hit: boolean;
    preference_hit: boolean;
  };
  policy_basis?: {
    source_mode: string;
    source_count: number;
    retrieval_usable?: boolean;
  };
  prompt_snapshot?: string | null;
  trace_id?: string | null;
};

export type SuggestedAction = {
  key: string;
  label: string;
  prompt: string;
};

export type SceneCitation = {
  label: string;
  url: string;
};

export type SceneAction = {
  name: string;
  label: string;
  requires_confirmation?: boolean;
  confirmation_token?: string;
  confirmation_prompt?: string;
  confirmation_type?: string;
};

export type ScenePanels = {
  summary?: {
    title: string;
    payload: Record<string, unknown>;
    display_payload?: Record<string, unknown>;
    missing_fields: string[];
    route_key?: string | null;
    field_labels?: Record<string, string>;
    visible_fields?: string[];
    recommended_fields?: string[];
    pending_confirmation_fields?: string[];
    field_options?: Record<
      string,
      Array<{
        value: string;
        label: string;
        description?: string;
        default?: boolean;
      }>
    >;
  };
  route_overview?: {
    form_no?: string | null;
    title: string;
    handling_mode: string;
    description?: string | null;
    submission_guide?: string | null;
  };
  pdf_preview?: {
    preview_url?: string | null;
    final_url?: string | null;
  };
  mail_preview?: {
    to: string;
    subject: string;
    body: string;
    attachment_path?: string | null;
  } | null;
};

export type ScenePayload = {
  scene_key: string;
  case_id: string;
  state: string;
  status: string;
  route_key?: string | null;
  summary?: string | null;
  missing_fields: string[];
  next_actions: SceneAction[];
  panels: ScenePanels;
  citations: SceneCitation[];
  mail_delivery_mode?: string;
};

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

export async function askQuestion(projectId: number, payload: ChatAskPayload) {
  return (
    await requestJson<ChatAskResponse>(`/portal/projects/${projectId}/chat/ask`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function fetchSessions(projectId: number) {
  return (await requestJson<ChatSessionSummary[]>(`/portal/projects/${projectId}/chat/sessions`)).data;
}

type ChatStreamMeta = {
  session_id: string;
  rewritten_query: string;
  sources: ChatAskResponse['sources'];
  suggested_actions?: SuggestedAction[];
  trace_id: string;
  use_memory: boolean;
  retrieval_usable: boolean;
  response_mode?: 'knowledge' | 'scene';
  scene?: ScenePayload | null;
};

type ChatStreamDone = {
  session_id: string;
  answer: string;
  sources: ChatAskResponse['sources'];
  suggested_actions?: SuggestedAction[];
  model_name: string;
  trace_id: string;
  response_mode?: 'knowledge' | 'scene';
  scene?: ScenePayload | null;
};

type StreamHandlers = {
  onMeta?: (payload: ChatStreamMeta) => void;
  onDelta?: (content: string) => void;
  onDone?: (payload: ChatStreamDone) => void;
  onError?: (message: string) => void;
};

export async function streamAskQuestion(projectId: number, payload: ChatAskPayload, handlers: StreamHandlers) {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/portal/projects/${projectId}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('后端服务不可用，请确认 API 服务已启动，并检查 127.0.0.1:8000 是否可访问。');
    }
    throw error instanceof Error ? error : new Error('流式响应失败');
  }

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    const detail =
      (errorPayload && typeof errorPayload === 'object' && 'detail' in errorPayload && String(errorPayload.detail)) ||
      response.statusText;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  if (!response.body) {
    throw new Error('流式响应不可用');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const handleEventBlock = (block: string) => {
    const lines = block
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    const eventLine = lines.find((line) => line.startsWith('event:'));
    const dataLine = lines.find((line) => line.startsWith('data:'));
    if (!eventLine || !dataLine) {
      return;
    }

    const eventName = eventLine.replace(/^event:\s*/, '');
    const payloadText = dataLine.replace(/^data:\s*/, '');
    const eventPayload = JSON.parse(payloadText);

    if (eventName === 'meta') {
      handlers.onMeta?.(eventPayload);
      return;
    }
    if (eventName === 'delta') {
      handlers.onDelta?.(String(eventPayload.content || ''));
      return;
    }
    if (eventName === 'done') {
      handlers.onDone?.(eventPayload);
      return;
    }
    if (eventName === 'error') {
      handlers.onError?.(String(eventPayload.message || '流式响应失败'));
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    parts.forEach(handleEventBlock);
    if (done) {
      if (buffer.trim()) {
        handleEventBlock(buffer.trim());
      }
      break;
    }
  }
}
