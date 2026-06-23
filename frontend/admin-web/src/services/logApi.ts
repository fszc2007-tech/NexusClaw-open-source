import { getDemoChatLogDetail, getDemoChatLogs } from './adminDemoApi';
import { isAdminDemoMode, requestJson } from './client';

export type ChatLogSummary = {
  session_id: string;
  title: string;
  source: string;
  query?: string | null;
  rewritten_query?: string | null;
  answer?: string | null;
  feedback: string;
  trace_id?: string | null;
  updated_at?: string | null;
};

export type ChatLogTurn = {
  id: number;
  query?: string | null;
  rewritten_query?: string | null;
  answer?: string | null;
  sources: Array<{
    knowledge_id: number;
    kb_id: number;
    title: string;
    document_name?: string | null;
    score: number;
    snippet: string;
  }>;
  prompt_snapshot?: string | null;
  model_name?: string | null;
  trace_id?: string | null;
  created_at?: string | null;
};

export type ChatLogDetail = {
  session_id: string;
  title: string;
  source: string;
  status: string;
  selected_kb_ids: number[];
  turns: ChatLogTurn[];
};

export async function fetchChatLogs(
  projectId: number,
  filters?: { sessionId?: string; queryKeyword?: string; answerKeyword?: string },
) {
  if (isAdminDemoMode()) {
    return getDemoChatLogs(projectId, filters);
  }
  const params = new URLSearchParams();
  if (filters?.sessionId) {
    params.set('session_id', filters.sessionId);
  }
  if (filters?.queryKeyword) {
    params.set('query_keyword', filters.queryKeyword);
  }
  if (filters?.answerKeyword) {
    params.set('answer_keyword', filters.answerKeyword);
  }

  const query = params.toString() ? `?${params.toString()}` : '';
  return (await requestJson<ChatLogSummary[]>(`/projects/${projectId}/logs/chat${query}`)).data;
}

export async function fetchChatLogDetail(projectId: number, sessionId: string) {
  if (isAdminDemoMode()) {
    return getDemoChatLogDetail(projectId, sessionId);
  }
  return (await requestJson<ChatLogDetail>(`/projects/${projectId}/logs/chat/${sessionId}`)).data;
}
