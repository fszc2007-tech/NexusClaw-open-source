import { requestJson } from './client';
import type { ScenePayload } from './chatApi';

export type SceneActionResponse = {
  message: string;
  scene: ScenePayload;
};

export async function fetchSceneCase(projectId: number, caseId: string) {
  return (await requestJson<ScenePayload>(`/portal/projects/${projectId}/scenes/${caseId}`)).data;
}

export async function executeSceneAction(
  projectId: number,
  caseId: string,
  actionName: string,
  options?: { confirmationToken?: string | null },
) {
  return (
    await requestJson<SceneActionResponse>(`/portal/projects/${projectId}/scenes/${caseId}/actions/${actionName}`, {
      method: 'POST',
      body: JSON.stringify({
        confirmation_token: options?.confirmationToken || null,
      }),
    })
  ).data;
}
