import { createDemoDataset, createDemoDatasetItem, getDemoDatasetItems, getDemoDatasets } from './adminDemoApi';
import { isAdminDemoMode, requestJson } from './client';

export type DatasetRecord = {
  id: number;
  project_id: number;
  name: string;
  description?: string | null;
  status: string;
  item_count: number;
  updated_at?: string | null;
};

export type DatasetItemRecord = {
  id: number;
  dataset_id: number;
  query: string;
  ref_answer?: string | null;
  expected_knowledge_ids?: string | null;
  tags?: string | null;
  updated_at?: string | null;
};

export async function fetchDatasets(projectId: number) {
  if (isAdminDemoMode()) {
    return getDemoDatasets(projectId);
  }
  return (await requestJson<DatasetRecord[]>(`/projects/${projectId}/datasets`)).data;
}

export async function createDataset(
  projectId: number,
  payload: { name: string; description?: string; status?: string },
) {
  if (isAdminDemoMode()) {
    return createDemoDataset(projectId, payload);
  }
  return (
    await requestJson<DatasetRecord>(`/projects/${projectId}/datasets`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function fetchDatasetItems(projectId: number, datasetId: number) {
  if (isAdminDemoMode()) {
    return getDemoDatasetItems(datasetId);
  }
  return (await requestJson<DatasetItemRecord[]>(`/projects/${projectId}/datasets/${datasetId}/items`)).data;
}

export async function createDatasetItem(
  projectId: number,
  datasetId: number,
  payload: { query: string; ref_answer?: string; expected_knowledge_ids?: string; tags?: string },
) {
  if (isAdminDemoMode()) {
    return createDemoDatasetItem(datasetId, payload);
  }
  return (
    await requestJson<DatasetItemRecord>(`/projects/${projectId}/datasets/${datasetId}/items`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}
