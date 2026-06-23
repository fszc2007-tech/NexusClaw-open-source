export { requestJson } from './client';
export { fetchProjects } from './projectApi';

export async function fetchProjectPersona(projectId: string) {
  return {
    code: 0,
    message: 'persona_not_supported_in_v2',
    data: {
      project_id: Number(projectId),
      assistant_name: 'Nexus 助手',
      assistant_role: '专业业务问答助手',
    },
  };
}
