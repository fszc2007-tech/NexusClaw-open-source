import { requestJson } from './client';
import { clearAuthState, getAccessToken, type AuthUser, writeAuthState } from './authStore';

type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: Omit<AuthUser, 'project_memberships'>;
};

export async function login(username: string, password: string) {
  const data = (
    await requestJson<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
  ).data;

  writeAuthState({
    accessToken: data.access_token,
    user: {
      ...data.user,
      project_memberships: [],
    },
  });

  return fetchCurrentUser();
}

export async function fetchCurrentUser() {
  const data = (await requestJson<AuthUser>('/auth/me')).data;
  const accessToken = getAccessToken();
  if (accessToken) {
    writeAuthState({ accessToken, user: data });
  }
  return data;
}

export async function logout() {
  try {
    await requestJson<{ success: boolean }>('/auth/logout', { method: 'POST' });
  } finally {
    clearAuthState();
  }
}
