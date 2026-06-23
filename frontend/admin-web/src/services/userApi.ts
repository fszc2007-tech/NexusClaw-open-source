import { requestJson } from './client';

export type UserRecord = {
  id: number;
  username: string;
  nickname: string;
  profile?: string | null;
  system_role: 'super_admin' | 'normal_user';
  status: 'active' | 'disabled';
};

export type UserCreatePayload = {
  username: string;
  password: string;
  nickname?: string;
  profile?: string;
  system_role: 'super_admin' | 'normal_user';
  status: 'active' | 'disabled';
};

export type UserUpdatePayload = {
  username?: string;
  password?: string;
  nickname?: string;
  profile?: string;
  system_role?: 'super_admin' | 'normal_user';
  status?: 'active' | 'disabled';
};

export async function fetchUsers(params?: { username?: string; system_role?: string }) {
  const search = new URLSearchParams();
  if (params?.username) {
    search.set('username', params.username);
  }
  if (params?.system_role) {
    search.set('system_role', params.system_role);
  }
  const suffix = search.toString() ? `?${search.toString()}` : '';
  return (await requestJson<UserRecord[]>(`/admin/users${suffix}`)).data;
}

export async function fetchUser(userId: number) {
  return (await requestJson<UserRecord>(`/admin/users/${userId}`)).data;
}

export async function createUser(payload: UserCreatePayload) {
  return (
    await requestJson<UserRecord>('/admin/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function updateUser(userId: number, payload: UserUpdatePayload) {
  return (
    await requestJson<UserRecord>(`/admin/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  ).data;
}

export async function deleteUser(userId: number) {
  return (
    await requestJson<{ success: boolean; detail: string }>(`/admin/users/${userId}`, {
      method: 'DELETE',
    })
  ).data;
}
