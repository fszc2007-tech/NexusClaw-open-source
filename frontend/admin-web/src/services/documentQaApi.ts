import { requestFormData, requestJson } from './client';

export type DocumentQaFileRecord = {
  id: number;
  project_id: number;
  kb_id: number;
  file_name: string;
  file_ext?: string | null;
  mime_type?: string | null;
  file_size: number;
  parse_status: string;
  chunk_status: string;
  qa_status: string;
  parse_error?: string | null;
  updated_at?: string | null;
  parse_meta?: Record<string, unknown>;
};

export type DocumentQaBlock = {
  block_id: string;
  block_type: string;
  text: string;
  order_no: number;
  page_no?: number | null;
  sheet_name?: string | null;
  slide_no?: number | null;
  section_title?: string | null;
  metadata?: Record<string, unknown>;
};

export type DocumentQaPreview = {
  id: number;
  file_name: string;
  content: string;
  parser_name?: string | null;
  mime_type?: string | null;
  parse_meta?: Record<string, unknown>;
  parse_error?: string | null;
  blocks?: DocumentQaBlock[];
};

export type DocumentQaCitation = {
  block_id?: string | null;
  quote: string;
  page_no?: number | null;
  sheet_name?: string | null;
  slide_no?: number | null;
  score?: number;
};

export type DocumentQaAskResult = {
  file_id: number;
  query: string;
  answer: string;
  citations: DocumentQaCitation[];
  trace_id?: string | null;
  model_name?: string | null;
};

export async function fetchDocumentQaFiles(projectId: number) {
  return (await requestJson<DocumentQaFileRecord[]>(`/projects/${projectId}/document-qa/files`)).data;
}

export async function uploadDocumentQaFile(projectId: number, file: File, overwriteSameName = false) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('overwrite_same_name', String(overwriteSameName));
  return (await requestFormData<DocumentQaFileRecord>(`/projects/${projectId}/document-qa/files/upload`, formData)).data;
}

export async function fetchDocumentQaPreview(projectId: number, fileId: number) {
  return (await requestJson<DocumentQaPreview>(`/projects/${projectId}/document-qa/files/${fileId}/preview`)).data;
}

export async function askDocumentQa(projectId: number, payload: { file_id: number; query: string }) {
  return (
    await requestJson<DocumentQaAskResult>(`/projects/${projectId}/document-qa/ask`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}
