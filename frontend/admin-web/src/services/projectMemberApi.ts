import { requestJson } from './client';

export type ProjectMemberRecord = {
  id: number;
  project_id: number;
  user_id: number;
  username: string;
  nickname: string;
  status: 'active' | 'disabled';
  system_role: 'super_admin' | 'normal_user';
  project_role: 'project_admin' | 'project_member';
  joined_at?: string | null;
};

export async function fetchProjectMembers(projectId: number) {
  return (await requestJson<ProjectMemberRecord[]>(`/admin/projects/${projectId}/members`)).data;
}

export async function addProjectMembers(projectId: number, payload: { usernames?: string[]; project_role: string }) {
  return (
    await requestJson<ProjectMemberRecord[]>(`/admin/projects/${projectId}/members`, {
      method: 'POST',
      body: JSON.stringify({
        user_ids: [],
        usernames: payload.usernames || [],
        project_role: payload.project_role,
      }),
    })
  ).data;
}

export async function updateProjectMember(projectId: number, memberId: number, payload: { project_role: string }) {
  return (
    await requestJson<ProjectMemberRecord>(`/admin/projects/${projectId}/members/${memberId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function deleteProjectMember(projectId: number, memberId: number) {
  return (
    await requestJson<{ success: boolean; detail: string }>(`/admin/projects/${projectId}/members/${memberId}`, {
      method: 'DELETE',
    })
  ).data;
}
