export type ProjectMembership = {
  id: number;
  project_id: number;
  project_role: 'project_admin' | 'project_member';
};

export type AuthUser = {
  id: number;
  username: string;
  nickname: string;
  profile?: string | null;
  system_role: 'super_admin' | 'normal_user';
  status: 'active' | 'disabled';
  project_memberships: ProjectMembership[];
};

type AuthState = {
  accessToken: string;
  user: AuthUser;
};

const AUTH_STORAGE_KEY = 'nexusclaw.admin.auth';

export function readAuthState(): AuthState | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthState;
  } catch {
    return null;
  }
}

export function writeAuthState(state: AuthState) {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(state));
}

export function clearAuthState() {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function getAccessToken() {
  return readAuthState()?.accessToken ?? null;
}

export function getStoredUser() {
  return readAuthState()?.user ?? null;
}

export function hasAuthSession() {
  return Boolean(getAccessToken());
}
