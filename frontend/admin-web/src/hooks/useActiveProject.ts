import { useEffect, useMemo, useState } from 'react';

import { fetchProjects, type ProjectRecord } from '@/services/projectApi';
import { getStoredProjectId, setStoredProjectId } from '@/services/projectStore';

export function useActiveProject() {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [activeProjectId, setActiveProjectIdState] = useState<number | null>(getStoredProjectId());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const items = await fetchProjects();
      setProjects(items);
      setError(null);

      const storedProjectId = getStoredProjectId();
      const resolvedProjectId =
        storedProjectId && items.some((item) => item.id === storedProjectId) ? storedProjectId : items[0]?.id ?? null;
      setActiveProjectIdState(resolvedProjectId);
      setStoredProjectId(resolvedProjectId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '加载项目失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadProjects();
  }, []);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === activeProjectId) ?? null,
    [activeProjectId, projects],
  );

  const setActiveProjectId = (projectId: number) => {
    setActiveProjectIdState(projectId);
    setStoredProjectId(projectId);
  };

  return {
    projects,
    activeProjectId,
    activeProject,
    loading,
    error,
    refreshProjects: loadProjects,
    setActiveProjectId,
  };
}
