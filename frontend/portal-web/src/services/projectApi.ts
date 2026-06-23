import { requestJson } from './client';

export type ProjectRecord = {
  id: number;
  project_key: string;
  company_name: string;
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

const PROJECT_NAME_OVERRIDES: Record<string, string> = {
  nexusclaw: 'NexusClaw',
};

function normalizeBrandText(text?: string | null) {
  return text;
}

function normalizeProjectRecord(project: ProjectRecord): ProjectRecord {
  return {
    ...project,
    company_name: PROJECT_NAME_OVERRIDES[project.project_key] || normalizeBrandText(project.company_name) || project.company_name,
  };
}

export async function fetchProjects() {
  return (await requestJson<ProjectRecord[]>('/portal/projects')).data.map(normalizeProjectRecord);
}

export async function fetchOpeningSettings(projectId: number) {
  const settings = (await requestJson<OpeningSettings>(`/portal/projects/${projectId}/opening`)).data;
  return {
    ...settings,
    opening_text: normalizeBrandText(settings.opening_text),
  };
}
