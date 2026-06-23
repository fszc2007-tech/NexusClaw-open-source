import {
  createDemoProject,
  getDemoMemorySettings,
  getDemoOpeningSettings,
  getDemoProject,
  getDemoProjects,
  getDemoPromptSettings,
  updateDemoMemorySettings,
  updateDemoOpeningSettings,
  updateDemoProject,
  updateDemoPromptSettings,
} from './adminDemoApi';
import { isAdminDemoMode, requestJson } from './client';

export type ProjectCapabilities = {
  multi_turn: boolean;
  sensitive_detection: boolean;
  gov_domain_check: boolean;
  knowledge_tree: boolean;
};

export type ProjectRecord = {
  id: number;
  project_key: string;
  company_name: string;
  name: string;
  description?: string | null;
  logo_url?: string | null;
  status: string;
  capabilities: ProjectCapabilities;
};

export type ProjectPayload = {
  project_key?: string;
  company_name: string;
  description?: string;
  logo_url?: string;
  status?: string;
  capabilities: ProjectCapabilities;
};

export type OpeningSettings = {
  project_id: number;
  mode: 'text' | 'card';
  opening_text?: string | null;
  recommended_questions: string[];
  hot_questions: string[];
  hot_policies: string[];
  enabled: boolean;
};

export type PromptSettings = {
  project_id: number;
  prompt_template: string;
};

export type MemorySettings = {
  project_id: number;
  capability_memory: boolean;
  memory_scope: 'off' | 'session_only';
  memory_ttl_days: number;
  preference_memory_enabled: boolean;
  enabled_scene_keys_json: string[];
  scene_entry_mode: string;
  scene_runtime_config_json: Record<string, unknown>;
};

const PROJECT_NAME_OVERRIDES: Record<string, string> = {
  nexusclaw: 'NexusClaw',
};

function normalizeBrandText(text?: string | null) {
  return text;
}

function normalizeProjectRecord(project: ProjectRecord): ProjectRecord {
  const nextName = PROJECT_NAME_OVERRIDES[project.project_key] || normalizeBrandText(project.company_name) || project.company_name;
  return {
    ...project,
    company_name: nextName,
    name: PROJECT_NAME_OVERRIDES[project.project_key] || normalizeBrandText(project.name) || nextName,
    description: normalizeBrandText(project.description),
  };
}

function normalizeOpeningSettings(settings: OpeningSettings): OpeningSettings {
  return {
    ...settings,
    opening_text: normalizeBrandText(settings.opening_text),
  };
}

export async function fetchProjects() {
  if (isAdminDemoMode()) {
    return (await getDemoProjects()).map(normalizeProjectRecord);
  }
  return (await requestJson<ProjectRecord[]>('/projects')).data.map(normalizeProjectRecord);
}

export async function fetchProject(projectId: number) {
  if (isAdminDemoMode()) {
    return normalizeProjectRecord(await getDemoProject(projectId));
  }
  return normalizeProjectRecord((await requestJson<ProjectRecord>(`/projects/${projectId}`)).data);
}

export async function createProject(payload: ProjectPayload) {
  if (isAdminDemoMode()) {
    return normalizeProjectRecord(await createDemoProject(payload));
  }
  return normalizeProjectRecord((
    await requestJson<ProjectRecord>('/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data);
}

export async function updateProject(projectId: number, payload: Partial<ProjectPayload>) {
  if (isAdminDemoMode()) {
    return normalizeProjectRecord(await updateDemoProject(projectId, payload));
  }
  return normalizeProjectRecord((
    await requestJson<ProjectRecord>(`/projects/${projectId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  ).data);
}

export async function fetchOpeningSettings(projectId: number) {
  if (isAdminDemoMode()) {
    return normalizeOpeningSettings(await getDemoOpeningSettings(projectId));
  }
  return normalizeOpeningSettings((await requestJson<OpeningSettings>(`/projects/${projectId}/settings/opening`)).data);
}

export async function updateOpeningSettings(projectId: number, payload: Omit<OpeningSettings, 'project_id'>) {
  if (isAdminDemoMode()) {
    return normalizeOpeningSettings(await updateDemoOpeningSettings(projectId, payload));
  }
  return normalizeOpeningSettings((
    await requestJson<OpeningSettings>(`/projects/${projectId}/settings/opening`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  ).data);
}

export async function fetchPromptSettings(projectId: number) {
  if (isAdminDemoMode()) {
    return getDemoPromptSettings(projectId);
  }
  return (await requestJson<PromptSettings>(`/projects/${projectId}/settings/prompt`)).data;
}

export async function updatePromptSettings(projectId: number, payload: Omit<PromptSettings, 'project_id'>) {
  if (isAdminDemoMode()) {
    return updateDemoPromptSettings(projectId, payload);
  }
  return (
    await requestJson<PromptSettings>(`/projects/${projectId}/settings/prompt`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function fetchMemorySettings(projectId: number) {
  if (isAdminDemoMode()) {
    return getDemoMemorySettings(projectId);
  }
  return (await requestJson<MemorySettings>(`/projects/${projectId}/settings/memory`)).data;
}

export async function updateMemorySettings(projectId: number, payload: Omit<MemorySettings, 'project_id'>) {
  if (isAdminDemoMode()) {
    return updateDemoMemorySettings(projectId, payload);
  }
  return (
    await requestJson<MemorySettings>(`/projects/${projectId}/settings/memory`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  ).data;
}
