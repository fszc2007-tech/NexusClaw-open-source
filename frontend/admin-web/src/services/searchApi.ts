import { getDemoSearchResult } from './adminDemoApi';
import { isAdminDemoMode, requestJson } from './client';

export type SearchHit = {
  knowledge_id: number;
  kb_id: number;
  title: string;
  document_name?: string | null;
  snippet: string;
  score: number;
  term_score?: number;
  vector_score?: number;
};

export type CompilationPageHit = {
  page_id: number;
  title: string;
  page_type: string;
  score: number;
  version_no: number;
  health_status: string;
  supporting_source_count: number;
  retrieval_priority: number;
};

export type CompilationReferenceItem = {
  title: string;
  document_name: string;
  snippet: string;
  source_kind?: string;
  compilation_page_id?: number;
  compilation_page_type?: string;
  compilation_version_no?: number;
  score?: number;
};

export type CompilationSource = {
  source_type: string;
  source_id: string;
  source_ref_id?: string | null;
  title: string;
  score?: number;
  support_type?: string;
  source_locator?: Record<string, unknown>;
  quote?: string | null;
};

export type SearchResponse = {
  query: string;
  rewritten_query: string;
  hits: SearchHit[];
  total: number;
  compilation: {
    enabled: boolean;
    usable: boolean;
    strategy: string;
    selected_mode: string;
    fallback_reason?: string | null;
    page_hits: CompilationPageHit[];
    reference_items: CompilationReferenceItem[];
    raw_sources: CompilationSource[];
  };
};

export async function searchKnowledge(
  projectId: number,
  payload: { query: string; selected_kb_ids?: number[] },
) {
  if (isAdminDemoMode()) {
    return getDemoSearchResult(projectId, payload.query);
  }
  return (
    await requestJson<SearchResponse>(`/projects/${projectId}/search`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}
