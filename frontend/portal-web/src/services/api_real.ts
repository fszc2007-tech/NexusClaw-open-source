import { askQuestion as askQuestionByProject } from './chatApi';

export async function askQuestion(payload: { session_id?: string; query: string; use_memory?: boolean }) {
  return {
    code: 0,
    message: 'ok',
    data: await askQuestionByProject(1, payload),
  };
}
