const ACTIVE_PROJECT_ID_KEY = 'nexusclaw.admin.activeProjectId';

export function getStoredProjectId(): number | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const rawValue = window.localStorage.getItem(ACTIVE_PROJECT_ID_KEY);
  if (!rawValue) {
    return null;
  }

  const projectId = Number(rawValue);
  return Number.isFinite(projectId) ? projectId : null;
}

export function setStoredProjectId(projectId: number | null) {
  if (typeof window === 'undefined') {
    return;
  }

  if (projectId === null) {
    window.localStorage.removeItem(ACTIVE_PROJECT_ID_KEY);
    return;
  }

  window.localStorage.setItem(ACTIVE_PROJECT_ID_KEY, String(projectId));
}
