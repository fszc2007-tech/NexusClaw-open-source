import {
  checkDemoDedup,
  createDemoKnowledgeBase,
  createDemoKnowledgeItem,
  deleteDemoKnowledgeBase,
  deleteDemoKnowledgeFile,
  deleteDemoKnowledgeItem,
  getDemoGovernanceSummary,
  getDemoConflictTasks,
  getDemoDedupCandidates,
  getDemoStaleTasks,
  generateDemoKnowledgeFileQa,
  getDemoFilePreview,
  getDemoFiles,
  getDemoKnowledgeBases,
  getDemoKnowledgeBaseDashboard,
  getDemoKnowledgeItem,
  getDemoKnowledgeItems,
  importDemoKnowledgeFile,
  publishDemoKnowledgeItem,
  bulkResolveDemoConflictTasks,
  bulkResolveDemoDedupCandidates,
  bulkResolveDemoStaleTasks,
  refreshDemoConflictTasks,
  refreshDemoDedupCandidates,
  refreshDemoStaleTasks,
  resolveDemoConflictTask,
  resolveDemoDedupCandidate,
  resolveDemoStaleTask,
  updateDemoKnowledgeBase,
  updateDemoKnowledgeItem,
  uploadDemoKnowledgeFile,
} from './adminDemoApi';
import { isAdminDemoMode, requestFormData, requestJson } from './client';

export type KnowledgeBaseRecord = {
  id: number;
  project_id: number;
  name: string;
  description?: string | null;
  is_default: boolean;
  updated_at?: string | null;
};

export type KnowledgeBasePayload = {
  name: string;
  description?: string;
  is_default?: boolean;
};

export type KnowledgeItemRecord = {
  id: number;
  project_id: number;
  kb_id: number;
  document_name?: string | null;
  title: string;
  content: string;
  keywords: string[];
  source_type: string;
  source_file_id?: number | null;
  source_meta?: Record<string, unknown>;
  source_url?: string | null;
  source_org?: string | null;
  owner_user_id?: number | null;
  status: string;
  governance_status?: string;
  normalized_content_hash?: string | null;
  duplicate_of_knowledge_id?: number | null;
  superseded_by_knowledge_id?: number | null;
  last_verified_at?: string | null;
  review_due_at?: string | null;
  review_sla_days?: number | null;
  source_snapshot_preview?: string | null;
  source_last_checked_at?: string | null;
  version_no: number;
  published_at?: string | null;
  updated_at?: string | null;
};

export type KnowledgeItemPayload = {
  document_name?: string;
  title: string;
  keywords: string[];
  content: string;
  source_url?: string;
  source_org?: string;
  review_due_at?: string | null;
  review_sla_days?: number | null;
  owner_user_id?: number | null;
  source_type?: string;
  source_file_id?: number;
  status?: string;
  check_duplicate?: boolean;
};

export type FileRecord = {
  id: number;
  project_id: number;
  kb_id: number;
  file_name: string;
  file_ext?: string | null;
  mime_type?: string | null;
  file_size: number;
  content_hash?: string | null;
  storage_path: string;
  preview_path?: string | null;
  parsed_document_path?: string | null;
  parser_name?: string | null;
  parse_meta?: Record<string, unknown>;
  parse_status: string;
  chunk_status: string;
  qa_status: string;
  parse_error?: string | null;
  updated_at?: string | null;
  knowledge_count?: number;
  qa_count?: number;
  qa_generator?: string;
  generated_questions?: string[];
  auto_process_task?: {
    id: number;
    task_type: string;
    status: string;
    request_payload?: Record<string, unknown>;
    result_payload?: Record<string, unknown>;
    error_message?: string | null;
    updated_at?: string | null;
  } | null;
};

export type FilePreview = {
  id: number;
  file_name: string;
  content: string;
  parser_name?: string | null;
  mime_type?: string | null;
  parse_meta?: Record<string, unknown>;
  parse_error?: string | null;
};

export type KnowledgeDedupCheck = {
  has_duplicate?: boolean;
  level?: string;
  candidates?: DedupCandidateRecord[];
};

export type DedupCandidateRecord = {
  knowledge_id: number;
  title: string;
  score: number;
  reason: string[];
  dedup_level: string;
};

export type GovernanceDedupRecord = {
  id: number;
  project_id: number;
  new_knowledge_id: number;
  old_knowledge_id: number;
  score: number;
  dedup_level: string;
  action: string;
  reason: string[];
  comment?: string | null;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  new_knowledge: {
    id: number;
    kb_id: number;
    title: string;
    document_name?: string | null;
    status: string;
    governance_status: string;
    updated_at?: string | null;
  };
  old_knowledge: {
    id: number;
    kb_id: number;
    title: string;
    document_name?: string | null;
    status: string;
    governance_status: string;
    updated_at?: string | null;
  };
};

export type GovernanceStaleTaskRecord = {
  id: number;
  project_id: number;
  knowledge_id: number;
  task_type: string;
  status: string;
  reason: string;
  payload?: Record<string, unknown>;
  comment?: string | null;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  knowledge: {
    id: number;
    kb_id: number;
    title: string;
    document_name?: string | null;
    status: string;
    governance_status: string;
    source_url?: string | null;
    source_org?: string | null;
    owner_user_id?: number | null;
    review_due_at?: string | null;
    review_sla_days?: number | null;
    last_verified_at?: string | null;
    source_snapshot_preview?: string | null;
    source_last_checked_at?: string | null;
    updated_at?: string | null;
  };
};

export type GovernanceConflictTaskRecord = {
  id: number;
  project_id: number;
  knowledge_id: number;
  task_type: string;
  status: string;
  reason: string;
  payload?: Record<string, unknown>;
  comment?: string | null;
  reviewed_by?: number | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  knowledge: {
    id: number;
    kb_id: number;
    title: string;
    document_name?: string | null;
    status: string;
    governance_status: string;
    updated_at?: string | null;
  };
  counterpart?: {
    id: number;
    kb_id: number;
    title: string;
    document_name?: string | null;
    status: string;
    governance_status: string;
    updated_at?: string | null;
  } | null;
};

export type GovernanceSummary = {
  knowledge_total_count: number;
  active_knowledge_count: number;
  blocked_knowledge_count: number;
  pending_duplicate_count: number;
  pending_stale_count: number;
  pending_conflict_count: number;
  source_changed_task_count: number;
  source_fetch_failed_task_count: number;
  governance_status_counts: Record<string, number>;
};

export async function fetchKnowledgeBases(projectId: number) {
  if (isAdminDemoMode()) {
    return getDemoKnowledgeBases(projectId);
  }
  return (await requestJson<KnowledgeBaseRecord[]>(`/projects/${projectId}/knowledge/bases`)).data;
}

export async function createKnowledgeBase(
  projectId: number,
  payload: KnowledgeBasePayload,
) {
  if (isAdminDemoMode()) {
    return createDemoKnowledgeBase(projectId, payload);
  }
  return (
    await requestJson<KnowledgeBaseRecord>(`/projects/${projectId}/knowledge/bases`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function updateKnowledgeBase(projectId: number, kbId: number, payload: KnowledgeBasePayload) {
  if (isAdminDemoMode()) {
    return updateDemoKnowledgeBase(projectId, kbId, payload);
  }
  return (
    await requestJson<KnowledgeBaseRecord>(`/projects/${projectId}/knowledge/bases/${kbId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function deleteKnowledgeBase(projectId: number, kbId: number) {
  if (isAdminDemoMode()) {
    return deleteDemoKnowledgeBase(projectId, kbId);
  }
  return (
    await requestJson<KnowledgeBaseRecord>(`/projects/${projectId}/knowledge/bases/${kbId}`, {
      method: 'DELETE',
    })
  ).data;
}

export async function fetchKnowledgeBaseDashboard(projectId: number, kbId: number) {
  if (isAdminDemoMode()) {
    return getDemoKnowledgeBaseDashboard(projectId, kbId);
  }
  return (await requestJson<Record<string, number>>(`/projects/${projectId}/knowledge/bases/${kbId}/dashboard`)).data;
}

export async function fetchKnowledgeItems(projectId: number, kbId: number, status?: string) {
  if (isAdminDemoMode()) {
    return getDemoKnowledgeItems(projectId, kbId, status);
  }
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return (await requestJson<KnowledgeItemRecord[]>(`/projects/${projectId}/knowledge/bases/${kbId}/items${query}`)).data;
}

export async function fetchKnowledgeItem(projectId: number, kbId: number, knowledgeId: number) {
  if (isAdminDemoMode()) {
    return getDemoKnowledgeItem(projectId, kbId, knowledgeId);
  }
  return (
    await requestJson<KnowledgeItemRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/items/${knowledgeId}`)
  ).data;
}

export async function createKnowledgeItem(projectId: number, kbId: number, payload: KnowledgeItemPayload) {
  if (isAdminDemoMode()) {
    return createDemoKnowledgeItem(projectId, kbId, payload);
  }
  return (
    await requestJson<KnowledgeItemRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/items`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function updateKnowledgeItem(projectId: number, kbId: number, knowledgeId: number, payload: KnowledgeItemPayload) {
  if (isAdminDemoMode()) {
    return updateDemoKnowledgeItem(projectId, kbId, knowledgeId, payload);
  }
  return (
    await requestJson<KnowledgeItemRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/items/${knowledgeId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function publishKnowledgeItem(projectId: number, kbId: number, knowledgeId: number) {
  if (isAdminDemoMode()) {
    return publishDemoKnowledgeItem(projectId, kbId, knowledgeId);
  }
  return (
    await requestJson<KnowledgeItemRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/items/${knowledgeId}/publish`, {
      method: 'POST',
    })
  ).data;
}

export async function deleteKnowledgeItem(projectId: number, kbId: number, knowledgeId: number) {
  if (isAdminDemoMode()) {
    return deleteDemoKnowledgeItem(projectId, kbId, knowledgeId);
  }
  return (
    await requestJson<KnowledgeItemRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/items/${knowledgeId}`, {
      method: 'DELETE',
    })
  ).data;
}

export async function fetchKnowledge(projectId: string) {
  const bases = await fetchKnowledgeBases(Number(projectId));
  return {
    code: 0,
    message: 'ok',
    data: bases,
  };
}

export async function fetchKnowledgeList(projectId: string) {
  return fetchKnowledge(projectId);
}

export async function checkDedup(projectId: string, payload: { title: string; keywords: string[]; content: string }) {
  if (isAdminDemoMode()) {
    return checkDemoDedup(projectId, payload);
  }
  return requestJson<KnowledgeDedupCheck>(`/projects/${projectId}/knowledge/dedup/check`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function checkKnowledgeDedup(
  projectId: string,
  payload: { title: string; keywords: string[]; content: string },
) {
  return checkDedup(projectId, payload);
}

export async function fetchGovernanceDedupCandidates(projectId: number, action = 'pending', kbId?: number) {
  if (isAdminDemoMode()) {
    return getDemoDedupCandidates(projectId, action, kbId);
  }
  const params = new URLSearchParams();
  if (action) params.set('action', action);
  if (typeof kbId === 'number') params.set('kb_id', String(kbId));
  const query = params.toString() ? `?${params.toString()}` : '';
  return (await requestJson<GovernanceDedupRecord[]>(`/projects/${projectId}/knowledge/dedup/candidates${query}`)).data;
}

export async function refreshGovernanceDedupCandidates(projectId: number, kbId?: number) {
  if (isAdminDemoMode()) {
    return refreshDemoDedupCandidates(projectId, kbId);
  }
  return (
    await requestJson<{ knowledge_count: number; pending_candidate_count: number }>(`/projects/${projectId}/knowledge/dedup/refresh`, {
      method: 'POST',
      body: JSON.stringify({ kb_id: kbId ?? null }),
    })
  ).data;
}

export async function resolveGovernanceDedupCandidate(
  projectId: number,
  payload: { record_id: number; action: string; comment?: string },
) {
  if (isAdminDemoMode()) {
    return resolveDemoDedupCandidate(projectId, payload);
  }
  return (
    await requestJson<{ id: number; action: string; new_knowledge_id: number; new_governance_status: string }>(
      `/projects/${projectId}/knowledge/dedup/resolve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    )
  ).data;
}

export async function bulkResolveGovernanceDedupCandidates(
  projectId: number,
  payload: { record_ids: number[]; action: string; comment?: string },
) {
  if (isAdminDemoMode()) {
    return bulkResolveDemoDedupCandidates(projectId, payload);
  }
  return (
    await requestJson<{ action: string; resolved_count: number; resolved_record_ids: number[] }>(
      `/projects/${projectId}/knowledge/dedup/bulk-resolve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    )
  ).data;
}

export async function fetchGovernanceSummary(projectId: number, kbId?: number) {
  if (isAdminDemoMode()) {
    return getDemoGovernanceSummary(projectId, kbId);
  }
  const params = new URLSearchParams();
  if (typeof kbId === 'number') params.set('kb_id', String(kbId));
  const query = params.toString() ? `?${params.toString()}` : '';
  return (await requestJson<GovernanceSummary>(`/projects/${projectId}/knowledge/governance/summary${query}`)).data;
}

export async function fetchGovernanceStaleTasks(projectId: number, status = 'pending', kbId?: number) {
  if (isAdminDemoMode()) {
    return getDemoStaleTasks(projectId, status, kbId);
  }
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (typeof kbId === 'number') params.set('kb_id', String(kbId));
  const query = params.toString() ? `?${params.toString()}` : '';
  return (await requestJson<GovernanceStaleTaskRecord[]>(`/projects/${projectId}/knowledge/governance/stale/tasks${query}`)).data;
}

export async function refreshGovernanceStaleTasks(projectId: number, kbId?: number, staleAfterDays?: number) {
  if (isAdminDemoMode()) {
    return refreshDemoStaleTasks(projectId, kbId, staleAfterDays);
  }
  return (
    await requestJson<{ checked_count: number; created_task_count: number; source_change_count: number; stale_after_days: number }>(
      `/projects/${projectId}/knowledge/governance/stale/scan`,
      {
        method: 'POST',
        body: JSON.stringify({ kb_id: kbId ?? null, stale_after_days: staleAfterDays ?? null }),
      },
    )
  ).data;
}

export async function resolveGovernanceStaleTask(
  projectId: number,
  payload: { task_id: number; action: string; comment?: string; next_review_days?: number },
) {
  if (isAdminDemoMode()) {
    return resolveDemoStaleTask(projectId, payload);
  }
  return (
    await requestJson<{ id: number; action: string; knowledge_id: number; new_governance_status: string }>(
      `/projects/${projectId}/knowledge/governance/stale/resolve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    )
  ).data;
}

export async function bulkResolveGovernanceStaleTasks(
  projectId: number,
  payload: { task_ids: number[]; action: string; comment?: string; next_review_days?: number },
) {
  if (isAdminDemoMode()) {
    return bulkResolveDemoStaleTasks(projectId, payload);
  }
  return (
    await requestJson<{ action: string; resolved_count: number; resolved_task_ids: number[] }>(
      `/projects/${projectId}/knowledge/governance/stale/bulk-resolve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    )
  ).data;
}

export async function fetchGovernanceConflictTasks(projectId: number, status = 'pending', kbId?: number) {
  if (isAdminDemoMode()) {
    return getDemoConflictTasks(projectId, status, kbId);
  }
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (typeof kbId === 'number') params.set('kb_id', String(kbId));
  const query = params.toString() ? `?${params.toString()}` : '';
  return (await requestJson<GovernanceConflictTaskRecord[]>(`/projects/${projectId}/knowledge/governance/conflict/tasks${query}`)).data;
}

export async function refreshGovernanceConflictTasks(projectId: number, kbId?: number) {
  if (isAdminDemoMode()) {
    return refreshDemoConflictTasks(projectId, kbId);
  }
  return (
    await requestJson<{ checked_count: number; created_task_count: number }>(
      `/projects/${projectId}/knowledge/governance/conflict/scan`,
      {
        method: 'POST',
        body: JSON.stringify({ kb_id: kbId ?? null }),
      },
    )
  ).data;
}

export async function resolveGovernanceConflictTask(
  projectId: number,
  payload: { task_id: number; action: string; comment?: string },
) {
  if (isAdminDemoMode()) {
    return resolveDemoConflictTask(projectId, payload);
  }
  return (
    await requestJson<{ id: number; action: string; knowledge_id: number; new_governance_status: string }>(
      `/projects/${projectId}/knowledge/governance/conflict/resolve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    )
  ).data;
}

export async function bulkResolveGovernanceConflictTasks(
  projectId: number,
  payload: { task_ids: number[]; action: string; comment?: string },
) {
  if (isAdminDemoMode()) {
    return bulkResolveDemoConflictTasks(projectId, payload);
  }
  return (
    await requestJson<{ action: string; resolved_count: number; resolved_task_ids: number[] }>(
      `/projects/${projectId}/knowledge/governance/conflict/bulk-resolve`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    )
  ).data;
}

export async function fetchFiles(projectId: number, kbId: number) {
  if (isAdminDemoMode()) {
    return getDemoFiles(projectId, kbId);
  }
  return (await requestJson<FileRecord[]>(`/projects/${projectId}/knowledge/bases/${kbId}/files`)).data;
}

export async function uploadKnowledgeFile(
  projectId: number,
  kbId: number,
  file: File,
  overwriteSameName = false,
) {
  if (isAdminDemoMode()) {
    return uploadDemoKnowledgeFile(projectId, kbId, file);
  }
  const formData = new FormData();
  formData.append('upload', file);
  formData.append('overwrite_same_name', String(overwriteSameName));
  formData.append('auto_process', 'true');
  return (
    await requestFormData<FileRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/files`, formData)
  ).data;
}

export async function fetchFilePreview(projectId: number, kbId: number, fileId: number) {
  if (isAdminDemoMode()) {
    return getDemoFilePreview(fileId);
  }
  return (
    await requestJson<FilePreview>(`/projects/${projectId}/knowledge/bases/${kbId}/files/${fileId}/preview`)
  ).data;
}

export async function importKnowledgeFile(
  projectId: number,
  kbId: number,
  fileId: number,
  payload: { chunk_size: number; generate_qa: boolean },
) {
  if (isAdminDemoMode()) {
    return importDemoKnowledgeFile(projectId, kbId, fileId);
  }
  return (
    await requestJson<FileRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/files/${fileId}/import`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function generateKnowledgeFileQa(
  projectId: number,
  kbId: number,
  fileId: number,
  payload: { chunk_size?: number; max_pairs?: number } = {},
) {
  if (isAdminDemoMode()) {
    return generateDemoKnowledgeFileQa(projectId, kbId, fileId, payload);
  }
  return (
    await requestJson<FileRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/files/${fileId}/generate-qa`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function deleteKnowledgeFile(projectId: number, kbId: number, fileId: number) {
  if (isAdminDemoMode()) {
    return deleteDemoKnowledgeFile(projectId, kbId, fileId);
  }
  return (
    await requestJson<FileRecord>(`/projects/${projectId}/knowledge/bases/${kbId}/files/${fileId}`, {
      method: 'DELETE',
    })
  ).data;
}
