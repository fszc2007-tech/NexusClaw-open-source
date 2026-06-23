import type {
  FilePreview,
  FileRecord,
  GovernanceConflictTaskRecord,
  GovernanceDedupRecord,
  GovernanceSummary,
  KnowledgeBaseRecord,
  KnowledgeDedupCheck,
  KnowledgeItemRecord,
} from './knowledgeApi';
import type { ChatLogDetail, ChatLogSummary, ChatLogTurn } from './logApi';
import type { MemorySettings, OpeningSettings, ProjectPayload, ProjectRecord, PromptSettings } from './projectApi';
import type {
  ChatAskResult,
  ChatSessionDetail,
  ChatSessionSummary,
  ChatSessionTurn,
  ChatStreamMeta,
} from './sessionApi';
import type { SearchHit, SearchResponse } from './searchApi';
import type { DatasetItemRecord, DatasetRecord } from './testingApi';

type AdminDemoState = {
  projects: ProjectRecord[];
  openingSettings: Record<number, OpeningSettings>;
  promptSettings: Record<number, PromptSettings>;
  memorySettings: Record<number, MemorySettings>;
  knowledgeBases: KnowledgeBaseRecord[];
  knowledgeItems: KnowledgeItemRecord[];
  files: FileRecord[];
  filePreviews: Record<number, FilePreview>;
  sessions: Record<number, ChatSessionDetail[]>;
  datasets: DatasetRecord[];
  datasetItems: DatasetItemRecord[];
};

const STORAGE_KEY = 'nexusclaw.admin.demoState';

function nowIso() {
  return new Date().toISOString();
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function defaultProjects(): ProjectRecord[] {
  return [
    {
      id: 1,
      project_key: 'hk-gov-assistant',
      company_name: 'NexusClaw 示範項目',
      name: 'NexusClaw 示範項目',
      description: '用於本地體驗項目、知識、日誌與測試鏈路。',
      logo_url: null,
      status: 'active',
      capabilities: {
        multi_turn: true,
        sensitive_detection: true,
        gov_domain_check: true,
        knowledge_tree: true,
      },
    },
    {
      id: 2,
      project_key: 'hk-social-service',
      company_name: 'NexusClaw 民生諮詢項目',
      name: 'NexusClaw 民生諮詢項目',
      description: '模擬民生諮詢知識問答與檢索體驗。',
      logo_url: null,
      status: 'active',
      capabilities: {
        multi_turn: true,
        sensitive_detection: true,
        gov_domain_check: false,
        knowledge_tree: false,
      },
    },
  ];
}

function defaultState(): AdminDemoState {
  const projects = defaultProjects();
  const knowledgeBases: KnowledgeBaseRecord[] = [
    { id: 101, project_id: 1, name: '出入境业务知识库', description: '港澳通行证与签注相关政策', is_default: true },
    { id: 102, project_id: 1, name: '公积金与居住证知识库', description: '住房与居住相关业务', is_default: false },
    { id: 201, project_id: 2, name: '民生服务知识库', description: '教育、社保、就业服务', is_default: true },
  ];
  const files: FileRecord[] = [
    {
      id: 1001,
      project_id: 1,
      kb_id: 101,
      file_name: '港澳通行证办理指南.md',
      file_ext: 'md',
      mime_type: 'text/markdown',
      file_size: 24 * 1024,
      content_hash: 'demo-hk-pass',
      storage_path: 'demo://港澳通行证办理指南.md',
      preview_path: null,
      parsed_document_path: null,
      parser_name: 'demo-parser',
      parse_meta: { block_count: 12, page_count: 1, route_kind: 'native', chunk_strategy: 'paragraph' },
      parse_status: 'completed',
      chunk_status: 'completed',
      qa_status: 'generated',
      parse_error: null,
      updated_at: nowIso(),
      knowledge_count: 18,
    },
  ];
  const knowledgeItems: KnowledgeItemRecord[] = [
    {
      id: 501,
      project_id: 1,
      kb_id: 101,
      document_name: '港澳通行证办理指南.md',
      title: '港澳通行证怎么办理？',
      content: '首次办理需准备身份证明材料、证件照，并按窗口要求预约办理时间。',
      keywords: ['港澳通行证', '办理'],
      source_type: 'file_qa',
      source_file_id: 1001,
      source_meta: { qa_kind: 'generated' },
      status: 'active',
      version_no: 1,
      published_at: nowIso(),
      updated_at: nowIso(),
    },
    {
      id: 502,
      project_id: 1,
      kb_id: 101,
      document_name: '人工维护',
      title: '港澳通行证办理流程',
      content: '先准备材料，再预约窗口，最后按要求提交办理。',
      keywords: ['通行证', '流程'],
      source_type: 'manual',
      source_file_id: null,
      source_meta: {},
      status: 'editing',
      version_no: 2,
      published_at: null,
      updated_at: nowIso(),
    },
  ];
  const filePreviews: Record<number, FilePreview> = {
    1001: {
      id: 1001,
      file_name: '港澳通行证办理指南.md',
      content:
        '港澳通行证首次办理需准备身份证明材料、符合要求的证件照，并根据当地出入境大厅要求预约办理时间。\n\n如需加急或续签，请以窗口通知和最新政策为准。',
      parser_name: 'demo-parser',
      mime_type: 'text/markdown',
      parse_meta: { block_count: 12, page_count: 1, route_kind: 'native', chunk_strategy: 'paragraph' },
      parse_error: null,
    },
  };
  const openingSettings: Record<number, OpeningSettings> = Object.fromEntries(
    projects.map((project) => [
      project.id,
      {
        project_id: project.id,
        mode: 'card',
        opening_text: `您好，我是${project.company_name}的智能助手，请输入您想咨询的问题。`,
        recommended_questions: ['报税表逾期提交会有什么后果？', '个人薪俸税怎么申请免税额？', '公司利得税报税需要准备哪些资料？'],
        hot_questions: ['雇主报税表常见截止时间', '薪俸税免税额如何计算？'],
        hot_policies: ['个人入息课税说明', '利得税报税须知'],
        enabled: true,
      },
    ]),
  );
  const promptSettings: Record<number, PromptSettings> = Object.fromEntries(
    projects.map((project) => [
      project.id,
      {
        project_id: project.id,
        prompt_template: '你是一个专业的政务问答助手。\n参考知识：{qa}\n历史对话：{history}\n用户问题：{query}',
      },
    ]),
  );
  const memorySettings: Record<number, MemorySettings> = Object.fromEntries(
    projects.map((project) => [
      project.id,
      {
        project_id: project.id,
        capability_memory: true,
        memory_scope: 'session_only',
        memory_ttl_days: 7,
        preference_memory_enabled: false,
        enabled_scene_keys_json: ['hk_tax_address_change'],
        scene_entry_mode: 'chat',
        scene_runtime_config_json: {},
      },
    ]),
  );
  const sessions: Record<number, ChatSessionDetail[]> = {
    1: [
      {
        session_id: 'demo-sess-001',
        title: '港澳通行证办理咨询',
        source: 'admin',
        status: 'active',
        selected_kb_ids: [101],
        summary: '围绕港澳通行证首次办理和材料准备给出答复。',
        state_json: {},
        turns: [
          {
            id: 1,
            query: '港澳通行证怎么办理？',
            rewritten_query: '港澳通行证首次办理流程与材料',
            answer:
              '本地演示模式下，建议先确认本人身份证明、照片、预约方式和办理地点。正式上线后，这里会展示真实后端生成的答案与引用来源。',
            sources: [
              {
                knowledge_id: 501,
                kb_id: 101,
                title: '港澳通行证办理指南',
                score: 0.96,
                snippet: '首次办理需准备身份证明、预约信息和符合要求的证件照。',
              },
            ],
            used_memory: true,
            memory_snapshot: null,
            safety_flags: null,
            prompt_snapshot: 'demo prompt snapshot',
            model_name: 'demo-assistant',
            trace_id: 'demo-trace-001',
            created_at: nowIso(),
          },
        ],
      },
    ],
    2: [],
  };
  const datasets: DatasetRecord[] = [
    {
      id: 301,
      project_id: 1,
      name: '政务咨询样本集',
      description: '本地演示测试集',
      status: 'active',
      item_count: 2,
      updated_at: nowIso(),
    },
  ];
  const datasetItems: DatasetItemRecord[] = [
    {
      id: 401,
      dataset_id: 301,
      query: '港澳通行证怎么办理？',
      ref_answer: '需准备身份证明并预约办理。',
      expected_knowledge_ids: '501',
      tags: '出入境,通行证',
      updated_at: nowIso(),
    },
    {
      id: 402,
      dataset_id: 301,
      query: '居住证办理周期多久？',
      ref_answer: '一般以当地窗口通知为准。',
      expected_knowledge_ids: '601',
      tags: '居住证',
      updated_at: nowIso(),
    },
  ];

  return {
    projects,
    openingSettings,
    promptSettings,
    memorySettings,
    knowledgeBases,
    knowledgeItems,
    files,
    filePreviews,
    sessions,
    datasets,
    datasetItems,
  };
}

function readState(): AdminDemoState {
  if (typeof window === 'undefined') {
    return defaultState();
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    const initialState = defaultState();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(initialState));
    return initialState;
  }

  try {
    return JSON.parse(raw) as AdminDemoState;
  } catch {
    const initialState = defaultState();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(initialState));
    return initialState;
  }
}

function writeState(state: AdminDemoState) {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function mutate<T>(mutator: (state: AdminDemoState) => T): T {
  const state = readState();
  const result = mutator(state);
  writeState(state);
  return result;
}

function nextId(values: number[]) {
  return (values.length ? Math.max(...values) : 0) + 1;
}

function projectById(state: AdminDemoState, projectId: number) {
  const project = state.projects.find((item) => item.id === projectId);
  if (!project) {
    throw new Error(`未找到项目 ${projectId}`);
  }
  return project;
}

function fallbackMemorySettings(projectId: number): MemorySettings {
  return {
    project_id: projectId,
    capability_memory: true,
    memory_scope: 'session_only',
    memory_ttl_days: 7,
    preference_memory_enabled: false,
    enabled_scene_keys_json: ['hk_tax_address_change'],
    scene_entry_mode: 'chat',
    scene_runtime_config_json: {},
  };
}

function buildSessionSummary(session: ChatSessionDetail): ChatSessionSummary {
  const lastTurn = session.turns[session.turns.length - 1];
  return {
    session_id: session.session_id,
    title: session.title,
    source: session.source,
    status: session.status,
    selected_kb_ids: session.selected_kb_ids,
    summary: session.summary,
    state_json: session.state_json,
    last_query: lastTurn?.query || null,
    last_answer: lastTurn?.answer || null,
    last_active_at: lastTurn?.created_at || null,
  };
}

function buildAnswer(projectName: string, query: string, sourceTitles: string[]) {
  return [
    `当前为本地演示数据模式，已根据“${projectName}”的示例知识给出稳定答复。`,
    `关于“${query}”，建议优先确认办理条件、材料清单、预约方式和窗口要求。`,
    sourceTitles.length ? `本次参考来源：${sourceTitles.join('、')}。` : '当前未命中具体来源，建议补充问题细节。',
  ].join('\n\n');
}

function buildSources(state: AdminDemoState, projectId: number, selectedKbIds?: number[]) {
  const candidates = state.knowledgeBases.filter(
    (kb) => kb.project_id === projectId && (!selectedKbIds?.length || selectedKbIds.includes(kb.id)),
  );
  return candidates.slice(0, 2).map((kb, index) => ({
    knowledge_id: 500 + kb.id + index,
    kb_id: kb.id,
    title: `${kb.name} · 示例条目`,
    score: Number((0.92 - index * 0.08).toFixed(2)),
    snippet: `${kb.name}中与当前问题最相关的演示摘要片段。`,
  }));
}

export function getDemoProjects() {
  return clone(readState().projects);
}

export function getDemoProject(projectId: number) {
  return clone(projectById(readState(), projectId));
}

export function createDemoProject(payload: ProjectPayload) {
  return mutate((state) => {
    const projectId = nextId(state.projects.map((item) => item.id));
    const project: ProjectRecord = {
      id: projectId,
      project_key: payload.project_key || `project-${projectId}`,
      company_name: payload.company_name,
      name: payload.company_name,
      description: payload.description || null,
      logo_url: payload.logo_url || null,
      status: payload.status || 'active',
      capabilities: payload.capabilities,
    };
    state.projects.unshift(project);
    state.openingSettings[projectId] = {
      project_id: projectId,
      mode: 'card',
      opening_text: `您好，我是${project.company_name}的智能助手。`,
      recommended_questions: [],
      hot_questions: [],
      hot_policies: [],
      enabled: true,
    };
    state.promptSettings[projectId] = {
      project_id: projectId,
      prompt_template: '你是一个专业的政务问答助手。\n参考知识：{qa}\n历史对话：{history}\n用户问题：{query}',
    };
    state.memorySettings[projectId] = {
      project_id: projectId,
      capability_memory: true,
      memory_scope: 'session_only',
      memory_ttl_days: 7,
      preference_memory_enabled: false,
      enabled_scene_keys_json: ['hk_tax_address_change'],
      scene_entry_mode: 'chat',
      scene_runtime_config_json: {},
    };
    state.sessions[projectId] = [];
    return clone(project);
  });
}

export function updateDemoProject(projectId: number, payload: Partial<ProjectPayload>) {
  return mutate((state) => {
    const project = projectById(state, projectId);
    Object.assign(project, {
      project_key: payload.project_key ?? project.project_key,
      company_name: payload.company_name ?? project.company_name,
      name: payload.company_name ?? project.name,
      description: payload.description ?? project.description,
      logo_url: payload.logo_url ?? project.logo_url,
      status: payload.status ?? project.status,
      capabilities: payload.capabilities ?? project.capabilities,
    });
    return clone(project);
  });
}

export function getDemoOpeningSettings(projectId: number) {
  const state = readState();
  return clone(state.openingSettings[projectId]);
}

export function updateDemoOpeningSettings(projectId: number, payload: Omit<OpeningSettings, 'project_id'>) {
  return mutate((state) => {
    state.openingSettings[projectId] = {
      project_id: projectId,
      ...payload,
    };
    return clone(state.openingSettings[projectId]);
  });
}

export function getDemoPromptSettings(projectId: number) {
  const state = readState();
  return clone(state.promptSettings[projectId]);
}

export function updateDemoPromptSettings(projectId: number, payload: Omit<PromptSettings, 'project_id'>) {
  return mutate((state) => {
    state.promptSettings[projectId] = {
      project_id: projectId,
      ...payload,
    };
    return clone(state.promptSettings[projectId]);
  });
}

export function getDemoMemorySettings(projectId: number) {
  const state = readState();
  return clone(state.memorySettings?.[projectId] || fallbackMemorySettings(projectId));
}

export function updateDemoMemorySettings(projectId: number, payload: Omit<MemorySettings, 'project_id'>) {
  return mutate((state) => {
    state.memorySettings = state.memorySettings || {};
    state.memorySettings[projectId] = {
      project_id: projectId,
      ...payload,
      preference_memory_enabled: false,
    };
    return clone(state.memorySettings[projectId]);
  });
}

export function getDemoKnowledgeBases(projectId: number) {
  return clone(readState().knowledgeBases.filter((item) => item.project_id === projectId));
}

export function createDemoKnowledgeBase(projectId: number, payload: { name: string; description?: string; is_default?: boolean }) {
  return mutate((state) => {
    const kbId = nextId(state.knowledgeBases.map((item) => item.id));
    if (payload.is_default) {
      state.knowledgeBases
        .filter((item) => item.project_id === projectId)
        .forEach((item) => {
          item.is_default = false;
        });
    }
    const record: KnowledgeBaseRecord = {
      id: kbId,
      project_id: projectId,
      name: payload.name,
      description: payload.description || null,
      is_default: Boolean(payload.is_default),
    };
    state.knowledgeBases.push(record);
    return clone(record);
  });
}

export function updateDemoKnowledgeBase(
  projectId: number,
  kbId: number,
  payload: { name: string; description?: string; is_default?: boolean },
) {
  return mutate((state) => {
    const record = state.knowledgeBases.find((item) => item.project_id === projectId && item.id === kbId);
    if (!record) {
      throw new Error('未找到知识库');
    }
    if (payload.is_default) {
      state.knowledgeBases
        .filter((item) => item.project_id === projectId && item.id !== kbId)
        .forEach((item) => {
          item.is_default = false;
        });
    }
    record.name = payload.name ?? record.name;
    record.description = payload.description ?? record.description;
    record.is_default = payload.is_default ?? record.is_default;
    return clone(record);
  });
}

export function deleteDemoKnowledgeBase(projectId: number, kbId: number) {
  return mutate((state) => {
    const index = state.knowledgeBases.findIndex((item) => item.project_id === projectId && item.id === kbId);
    if (index < 0) {
      throw new Error('未找到知识库');
    }
    const [record] = state.knowledgeBases.splice(index, 1);
    state.knowledgeItems = state.knowledgeItems.filter((item) => !(item.project_id === projectId && item.kb_id === kbId));
    const fileIds = state.files.filter((item) => item.project_id === projectId && item.kb_id === kbId).map((item) => item.id);
    state.files = state.files.filter((item) => !(item.project_id === projectId && item.kb_id === kbId));
    for (const fileId of fileIds) {
      delete state.filePreviews[fileId];
    }
    return clone(record);
  });
}

export function getDemoKnowledgeBaseDashboard(projectId: number, kbId: number) {
  const items = readState().knowledgeItems.filter((item) => item.project_id === projectId && item.kb_id === kbId);
  return clone(
    items.reduce<Record<string, number>>(
      (accumulator, item) => {
        accumulator.all += 1;
        accumulator[item.status] = (accumulator[item.status] ?? 0) + 1;
        return accumulator;
      },
      {
        all: 0,
        editing: 0,
        publishing: 0,
        active: 0,
        publish_failed: 0,
        offline: 0,
        offline_failed: 0,
      },
    ),
  );
}

export function getDemoKnowledgeItems(projectId: number, kbId: number, status?: string) {
  const items = readState().knowledgeItems.filter(
    (item) => item.project_id === projectId && item.kb_id === kbId && (!status || item.status === status),
  );
  return clone(items.sort((left, right) => right.id - left.id));
}

export function getDemoKnowledgeItem(projectId: number, kbId: number, knowledgeId: number) {
  const item = readState().knowledgeItems.find(
    (record) => record.project_id === projectId && record.kb_id === kbId && record.id === knowledgeId,
  );
  if (!item) {
    throw new Error('未找到知识条目');
  }
  return clone(item);
}

export function createDemoKnowledgeItem(
  projectId: number,
  kbId: number,
  payload: {
    document_name?: string;
    title: string;
    keywords: string[];
    content: string;
    source_type?: string;
    source_file_id?: number;
    status?: string;
  },
) {
  return mutate((state) => {
    const record: KnowledgeItemRecord = {
      id: nextId(state.knowledgeItems.map((item) => item.id)),
      project_id: projectId,
      kb_id: kbId,
      document_name: payload.document_name || null,
      title: payload.title,
      content: payload.content,
      keywords: payload.keywords || [],
      source_type: payload.source_type || 'manual',
      source_file_id: payload.source_file_id || null,
      source_meta: {},
      status: payload.status || 'editing',
      version_no: 1,
      published_at: payload.status === 'active' ? nowIso() : null,
      updated_at: nowIso(),
    };
    state.knowledgeItems.unshift(record);
    return clone(record);
  });
}

export function updateDemoKnowledgeItem(
  projectId: number,
  kbId: number,
  knowledgeId: number,
  payload: {
    document_name?: string;
    title: string;
    keywords: string[];
    content: string;
    source_type?: string;
    source_file_id?: number;
    status?: string;
  },
) {
  return mutate((state) => {
    const record = state.knowledgeItems.find(
      (item) => item.project_id === projectId && item.kb_id === kbId && item.id === knowledgeId,
    );
    if (!record) {
      throw new Error('未找到知识条目');
    }
    record.document_name = payload.document_name ?? record.document_name;
    record.title = payload.title ?? record.title;
    record.content = payload.content ?? record.content;
    record.keywords = payload.keywords ?? record.keywords;
    record.source_type = payload.source_type ?? record.source_type;
    record.source_file_id = payload.source_file_id ?? record.source_file_id;
    record.status = payload.status ?? record.status;
    record.version_no += 1;
    record.updated_at = nowIso();
    if (record.status === 'active') {
      record.published_at = nowIso();
    }
    return clone(record);
  });
}

export function publishDemoKnowledgeItem(projectId: number, kbId: number, knowledgeId: number) {
  return mutate((state) => {
    const record = state.knowledgeItems.find(
      (item) => item.project_id === projectId && item.kb_id === kbId && item.id === knowledgeId,
    );
    if (!record) {
      throw new Error('未找到知识条目');
    }
    record.status = 'active';
    record.published_at = nowIso();
    record.updated_at = nowIso();
    return clone(record);
  });
}

export function deleteDemoKnowledgeItem(projectId: number, kbId: number, knowledgeId: number) {
  return mutate((state) => {
    const index = state.knowledgeItems.findIndex(
      (item) => item.project_id === projectId && item.kb_id === kbId && item.id === knowledgeId,
    );
    if (index < 0) {
      throw new Error('未找到知识条目');
    }
    const [record] = state.knowledgeItems.splice(index, 1);
    return clone(record);
  });
}

export function checkDemoDedup(projectId: string, payload: { title: string; keywords: string[]; content: string }): {
  code: number;
  message: string;
  data: KnowledgeDedupCheck;
} {
  const bases = getDemoKnowledgeBases(Number(projectId));
  const duplicated = bases.some((item) => payload.title.includes(item.name) || payload.content.includes(item.name));
  return {
    code: 0,
    message: 'ok',
    data: {
      has_duplicate: duplicated,
      level: duplicated ? 'medium' : 'low',
      candidates: duplicated
        ? bases.slice(0, 2).map((item) => ({
            knowledge_id: item.id,
            title: item.name,
            score: 0.72,
            dedup_level: 'medium',
            reason: ['演示数据：标题高度相似'],
          }))
        : [],
    },
  };
}

export function getDemoFiles(projectId: number, kbId: number) {
  return clone(readState().files.filter((item) => item.project_id === projectId && item.kb_id === kbId));
}

export async function uploadDemoKnowledgeFile(projectId: number, kbId: number, file: File) {
  const content = await file.text().catch(() => '');
  return mutate((state) => {
    const fileId = nextId(state.files.map((item) => item.id));
    const record: FileRecord = {
      id: fileId,
      project_id: projectId,
      kb_id: kbId,
      file_name: file.name,
      file_ext: file.name.split('.').pop() || '',
      mime_type: file.type || 'application/octet-stream',
      file_size: file.size,
      content_hash: `demo-${fileId}`,
      storage_path: `demo://${file.name}`,
      preview_path: null,
      parsed_document_path: null,
      parser_name: 'demo-parser',
      parse_meta: { block_count: 1, page_count: 1, route_kind: 'upload', chunk_strategy: 'paragraph' },
      parse_status: 'completed',
      chunk_status: 'pending',
      qa_status: 'pending',
      parse_error: null,
      updated_at: nowIso(),
      knowledge_count: 0,
    };
    state.files.unshift(record);
    state.filePreviews[fileId] = {
      id: fileId,
      file_name: file.name,
      content: content || '当前文件为二进制或无法直接预览，演示模式下仅保存上传记录。',
      parser_name: 'demo-parser',
      mime_type: file.type || 'application/octet-stream',
      parse_meta: record.parse_meta,
      parse_error: null,
    };
    return clone(record);
  });
}

export function getDemoFilePreview(fileId: number) {
  return clone(readState().filePreviews[fileId]);
}

export function importDemoKnowledgeFile(projectId: number, kbId: number, fileId: number) {
  return mutate((state) => {
    const file = state.files.find((item) => item.id === fileId && item.project_id === projectId && item.kb_id === kbId);
    if (!file) {
      throw new Error('未找到文件');
    }
    file.chunk_status = 'completed';
    file.qa_status = file.qa_status === 'generated' ? 'generated' : 'skipped';
    file.knowledge_count = Math.max(file.knowledge_count ?? 0, 12);
    file.updated_at = nowIso();
    return clone(file);
  });
}

export function generateDemoKnowledgeFileQa(
  projectId: number,
  kbId: number,
  fileId: number,
  payload?: { chunk_size?: number; max_pairs?: number },
) {
  return mutate((state) => {
    const file = state.files.find((item) => item.id === fileId && item.project_id === projectId && item.kb_id === kbId);
    if (!file) {
      throw new Error('未找到文件');
    }
    const preview = state.filePreviews[fileId];
    const maxPairs = Math.max(1, payload?.max_pairs ?? 3);
    const paragraphs = (preview?.content || '')
      .split(/\n{2,}/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, maxPairs);
    state.knowledgeItems = state.knowledgeItems.filter(
      (item) => !(item.project_id === projectId && item.kb_id === kbId && item.source_file_id === fileId && item.source_type === 'file_qa'),
    );
    const nextKnowledgeId = nextId(state.knowledgeItems.map((item) => item.id));
    const records = paragraphs.map<KnowledgeItemRecord>((paragraph, index) => ({
      id: nextKnowledgeId + index,
      project_id: projectId,
      kb_id: kbId,
      document_name: file.file_name,
      title: `${file.file_name} QA ${index + 1}`,
      content: paragraph,
      keywords: [file.file_name],
      source_type: 'file_qa',
      source_file_id: fileId,
      source_meta: { qa_kind: 'generated' },
      status: 'active',
      version_no: 1,
      published_at: nowIso(),
      updated_at: nowIso(),
    }));
    state.knowledgeItems.unshift(...records.reverse());
    file.qa_status = records.length ? 'generated' : 'skipped';
    file.qa_generator = 'fallback_rule';
    file.knowledge_count = records.length;
    file.updated_at = nowIso();
    return clone(file);
  });
}

export function deleteDemoKnowledgeFile(projectId: number, kbId: number, fileId: number) {
  return mutate((state) => {
    const index = state.files.findIndex((item) => item.id === fileId && item.project_id === projectId && item.kb_id === kbId);
    if (index < 0) {
      throw new Error('未找到文件');
    }
    const [file] = state.files.splice(index, 1);
    delete state.filePreviews[fileId];
    state.knowledgeItems = state.knowledgeItems.filter(
      (item) => !(item.project_id === projectId && item.kb_id === kbId && item.source_file_id === fileId),
    );
    return clone(file);
  });
}

export function getDemoSessions(projectId: number): ChatSessionSummary[] {
  const sessions = readState().sessions[projectId] || [];
  return clone(sessions.map(buildSessionSummary));
}

export function getDemoSessionDetail(projectId: number, sessionId: string) {
  const sessions = readState().sessions[projectId] || [];
  const session = sessions.find((item) => item.session_id === sessionId);
  if (!session) {
    throw new Error('未找到会话');
  }
  return clone(session);
}

export function askDemoProjectChat(
  projectId: number,
  payload: {
    session_id?: string | null;
    query: string;
    use_memory?: boolean;
    source?: string;
    selected_kb_ids?: number[];
    switches?: Record<string, boolean>;
  },
): ChatAskResult {
  return mutate((state) => {
    const project = projectById(state, projectId);
    const memorySettings = state.memorySettings?.[projectId] || fallbackMemorySettings(projectId);
    const sessions = state.sessions[projectId] || (state.sessions[projectId] = []);
    let session = payload.session_id ? sessions.find((item) => item.session_id === payload.session_id) : undefined;
    if (!session) {
      session = {
        session_id: `demo-sess-${Date.now()}`,
        title: payload.query.slice(0, 16) || '新对话',
        source: payload.source || 'admin',
        status: 'active',
        selected_kb_ids: payload.selected_kb_ids?.length
          ? payload.selected_kb_ids
          : getDemoKnowledgeBases(projectId)
              .filter((item) => item.is_default)
              .map((item) => item.id),
        summary: null,
        state_json: {},
        turns: [],
      };
      sessions.unshift(session);
    }

    const rewrittenQuery = `${payload.query.trim()}（演示改写）`;
    const sources = buildSources(state, projectId, payload.selected_kb_ids?.length ? payload.selected_kb_ids : session.selected_kb_ids);
    const answer = buildAnswer(project.company_name, payload.query.trim(), sources.map((item) => item.title));
    const memoryEnabled = Boolean(
      payload.use_memory && memorySettings?.capability_memory && memorySettings?.memory_scope !== 'off',
    );
    const turn: ChatSessionTurn = {
      id: nextId(session.turns.map((item) => item.id)),
      query: payload.query.trim(),
      rewritten_query: rewrittenQuery,
      answer,
      sources,
      used_memory: memoryEnabled,
      memory_snapshot: memoryEnabled ? { summary: 'demo memory hit' } : null,
      safety_flags: payload.switches || null,
      prompt_snapshot: state.promptSettings[projectId]?.prompt_template || null,
      model_name: 'demo-assistant',
      trace_id: `demo-trace-${Date.now()}`,
      created_at: nowIso(),
    };
    session.turns.push(turn);
    session.summary = answer.slice(0, 72);

    return {
      project_id: projectId,
      session_id: session.session_id,
      query: payload.query.trim(),
      query_raw: payload.query,
      rewritten_query: rewrittenQuery,
      answer,
      sources,
      use_memory: memoryEnabled,
      memory: {
        used: memoryEnabled,
        summary_hit: memoryEnabled,
        state_hit: memoryEnabled,
        preference_hit: false,
      },
      policy_basis: {
        source_mode: 'demo',
        source_count: sources.length,
        retrieval_usable: true,
      },
      prompt_snapshot: state.promptSettings[projectId]?.prompt_template || null,
      trace_id: turn.trace_id,
    };
  });
}

export function buildDemoStreamMeta(result: ChatAskResult): ChatStreamMeta {
  return {
    session_id: result.session_id,
    rewritten_query: result.rewritten_query,
    sources: result.sources,
    trace_id: result.trace_id,
    use_memory: result.memory.used,
    retrieval_usable: result.policy_basis.retrieval_usable,
  };
}

export function getDemoDatasets(projectId: number) {
  return clone(readState().datasets.filter((item) => item.project_id === projectId));
}

export function createDemoDataset(projectId: number, payload: { name: string; description?: string; status?: string }) {
  return mutate((state) => {
    const dataset: DatasetRecord = {
      id: nextId(state.datasets.map((item) => item.id)),
      project_id: projectId,
      name: payload.name,
      description: payload.description || null,
      status: payload.status || 'active',
      item_count: 0,
      updated_at: nowIso(),
    };
    state.datasets.unshift(dataset);
    return clone(dataset);
  });
}

export function getDemoDatasetItems(datasetId: number) {
  return clone(readState().datasetItems.filter((item) => item.dataset_id === datasetId));
}

export function createDemoDatasetItem(
  datasetId: number,
  payload: { query: string; ref_answer?: string; expected_knowledge_ids?: string; tags?: string },
) {
  return mutate((state) => {
    const item: DatasetItemRecord = {
      id: nextId(state.datasetItems.map((record) => record.id)),
      dataset_id: datasetId,
      query: payload.query,
      ref_answer: payload.ref_answer || null,
      expected_knowledge_ids: payload.expected_knowledge_ids || null,
      tags: payload.tags || null,
      updated_at: nowIso(),
    };
    state.datasetItems.unshift(item);
    const dataset = state.datasets.find((record) => record.id === datasetId);
    if (dataset) {
      dataset.item_count += 1;
      dataset.updated_at = nowIso();
    }
    return clone(item);
  });
}

export function getDemoSearchResult(projectId: number, query: string): SearchResponse {
  const sources = buildSources(readState(), projectId);
  const hits: SearchHit[] = sources.map((source, index) => ({
    knowledge_id: source.knowledge_id,
    kb_id: source.kb_id || 0,
    title: source.title,
    document_name: source.title,
    snippet: `${source.snippet} 用户查询：${query}`,
    score: Number((0.94 - index * 0.07).toFixed(4)),
    term_score: Number((0.73 - index * 0.05).toFixed(4)),
    vector_score: Number((0.81 - index * 0.04).toFixed(4)),
  }));

  return {
    query,
    rewritten_query: `${query}（演示检索改写）`,
    hits,
    total: hits.length,
    compilation: {
      enabled: true,
      usable: true,
      strategy: 'compiled_first',
      selected_mode: 'compiled',
      fallback_reason: null,
      page_hits: [
        {
          page_id: 9001,
          title: '示例编译页 / 高频办理材料',
          page_type: 'faq',
          score: 0.91,
          version_no: 3,
          health_status: 'healthy',
          supporting_source_count: 3,
          retrieval_priority: 40,
        },
      ],
      reference_items: [
        {
          title: '示例编译页 / 高频办理材料',
          document_name: '編譯知識頁/faq',
          snippet: '演示模式下，这里展示编译知识页沉淀后的主题摘要与可复用答案。',
          source_kind: 'compiled_page',
          compilation_page_id: 9001,
          compilation_page_type: 'faq',
          compilation_version_no: 3,
          score: 0.91,
        },
      ],
      raw_sources: [
        {
          source_type: 'file_chunk',
          source_id: 'demo-chunk-1',
          title: '示例原始来源 / 官方文件',
          score: 0.93,
          support_type: 'supports',
          source_locator: { page_no: 1, section: '办理材料' },
          quote: '需准备身份证明材料、预约信息和符合要求的证件照。',
        },
      ],
    },
  };
}

export function getDemoChatLogs(
  projectId: number,
  filters?: { sessionId?: string; queryKeyword?: string; answerKeyword?: string },
): ChatLogSummary[] {
  const sessions = readState().sessions[projectId] || [];
  return clone(
    sessions
      .map((session) => {
        const lastTurn = session.turns[session.turns.length - 1];
        return {
          session_id: session.session_id,
          title: session.title,
          source: session.source,
          query: lastTurn?.query || null,
          rewritten_query: lastTurn?.rewritten_query || null,
          answer: lastTurn?.answer || null,
          feedback: 'pending',
          trace_id: lastTurn?.trace_id || null,
          updated_at: lastTurn?.created_at || null,
        } satisfies ChatLogSummary;
      })
      .filter((item) => !filters?.sessionId || item.session_id.includes(filters.sessionId))
      .filter((item) => !filters?.queryKeyword || (item.query || '').includes(filters.queryKeyword))
      .filter((item) => !filters?.answerKeyword || (item.answer || '').includes(filters.answerKeyword)),
  );
}

export function getDemoChatLogDetail(projectId: number, sessionId: string): ChatLogDetail {
  const detail = getDemoSessionDetail(projectId, sessionId);
  const turns: ChatLogTurn[] = detail.turns.map((turn) => ({
    id: turn.id,
    query: turn.query,
    rewritten_query: turn.rewritten_query,
    answer: turn.answer,
    sources: turn.sources.map((source) => ({
      knowledge_id: source.knowledge_id,
      kb_id: source.kb_id || 0,
      title: source.title,
      document_name: source.title,
      score: source.score || 0.9,
      snippet: source.snippet || '',
    })),
    prompt_snapshot: turn.prompt_snapshot,
    model_name: turn.model_name,
    trace_id: turn.trace_id,
    created_at: turn.created_at,
  }));
  return {
    session_id: detail.session_id,
    title: detail.title,
    source: detail.source,
    status: detail.status,
    selected_kb_ids: detail.selected_kb_ids,
    turns,
  };
}

export function getDemoDedupCandidates(projectId: number, action = 'pending', kbId?: number): GovernanceDedupRecord[] {
  if (action && action !== 'pending') {
    return [];
  }
  const items = readState().knowledgeItems.filter((item) => item.project_id === projectId);
  const filtered = typeof kbId === 'number' ? items.filter((item) => item.kb_id === kbId) : items;
  if (filtered.length < 2) {
    return [];
  }
  const newest = filtered[0];
  const target = filtered[1];
  return [
    {
      id: 1,
      project_id: projectId,
      new_knowledge_id: newest.id,
      old_knowledge_id: target.id,
      score: 0.88,
      dedup_level: 'high',
      action: 'pending',
      reason: ['演示数据：标题完全相同', '演示数据：文本相似度较高'],
      comment: null,
      reviewed_by: null,
      reviewed_at: null,
      created_at: nowIso(),
      new_knowledge: {
        id: newest.id,
        kb_id: newest.kb_id,
        title: newest.title,
        document_name: newest.document_name,
        status: newest.status,
        governance_status: newest.governance_status || 'review_pending',
        updated_at: newest.updated_at,
      },
      old_knowledge: {
        id: target.id,
        kb_id: target.kb_id,
        title: target.title,
        document_name: target.document_name,
        status: target.status,
        governance_status: target.governance_status || 'active',
        updated_at: target.updated_at,
      },
    },
  ];
}

export function refreshDemoDedupCandidates(projectId: number, kbId?: number) {
  const count = readState().knowledgeItems.filter(
    (item) => item.project_id === projectId && (typeof kbId !== 'number' || item.kb_id === kbId),
  ).length;
  return { knowledge_count: count, pending_candidate_count: Math.min(count, 1) };
}

export function bulkResolveDemoDedupCandidates(
  _projectId: number,
  payload: { record_ids: number[]; action: string; comment?: string },
) {
  return {
    action: payload.action,
    resolved_count: payload.record_ids.length,
    resolved_record_ids: payload.record_ids,
  };
}

export function resolveDemoDedupCandidate(
  _projectId: number,
  payload: { record_id: number; action: string; comment?: string },
) {
  return {
    id: payload.record_id,
    action: payload.action,
    new_knowledge_id: 0,
    new_governance_status: payload.action === 'reject' ? 'active' : payload.action === 'mark_superseded' ? 'superseded' : 'duplicate',
  };
}

export function getDemoStaleTasks(projectId: number, status = 'pending', kbId?: number) {
  if (status && status !== 'pending') {
    return [];
  }
  const item = readState().knowledgeItems.find(
    (record) => record.project_id === projectId && (typeof kbId !== 'number' || record.kb_id === kbId),
  );
  if (!item) {
    return [];
  }
  return [
    {
      id: 11,
      project_id: projectId,
      knowledge_id: item.id,
      task_type: 'stale',
      status: 'pending',
      reason: '演示数据：来源内容已变更，需重新复核',
      payload: {
        rule: 'source_content_changed',
        stale_after_days: 90,
        previous_preview: '旧版办理说明：需准备身份证明材料并到窗口排队办理。',
        current_preview: '新版办理说明：需先线上预约，再携带身份证明材料按预约时间到窗口办理。',
      },
      comment: null,
      reviewed_by: null,
      reviewed_at: null,
      created_at: nowIso(),
      knowledge: {
        id: item.id,
        kb_id: item.kb_id,
        title: item.title,
        document_name: item.document_name,
        status: item.status,
        governance_status: item.governance_status || 'active',
        source_url: item.source_url || 'https://demo.internal/wiki',
        source_org: item.source_org || '示範團隊',
        review_due_at: item.review_due_at || nowIso(),
        last_verified_at: item.last_verified_at || null,
        source_snapshot_preview: '旧版办理说明：需准备身份证明材料并到窗口排队办理。',
        updated_at: item.updated_at || nowIso(),
      },
    },
  ];
}

export function refreshDemoStaleTasks(projectId: number, kbId?: number, staleAfterDays?: number) {
  const count = readState().knowledgeItems.filter(
    (item) => item.project_id === projectId && (typeof kbId !== 'number' || item.kb_id === kbId),
  ).length;
  return { checked_count: count, created_task_count: Math.min(count, 1), stale_after_days: staleAfterDays || 90 };
}

export function bulkResolveDemoStaleTasks(
  _projectId: number,
  payload: { task_ids: number[]; action: string; comment?: string; next_review_days?: number },
) {
  return {
    action: payload.action,
    resolved_count: payload.task_ids.length,
    resolved_task_ids: payload.task_ids,
  };
}

export function resolveDemoStaleTask(
  _projectId: number,
  payload: { task_id: number; action: string; comment?: string; next_review_days?: number },
) {
  return {
    id: payload.task_id,
    action: payload.action,
    knowledge_id: 0,
    new_governance_status: payload.action === 'mark_stale' ? 'stale' : 'active',
  };
}

export function getDemoConflictTasks(projectId: number, status = 'pending', kbId?: number): GovernanceConflictTaskRecord[] {
  if (status && status !== 'pending') {
    return [];
  }
  const items = readState().knowledgeItems.filter(
    (item) => item.project_id === projectId && (typeof kbId !== 'number' || item.kb_id === kbId),
  );
  if (items.length < 2) {
    return [];
  }
  const current = items[0];
  const counterpart = items[1];
  return [
    {
      id: 21,
      project_id: projectId,
      knowledge_id: current.id,
      task_type: 'conflict',
      status: 'pending',
      reason: '演示数据：同标题知识内容不一致，需人工确认',
      payload: {
        rule: 'same_title_different_content',
        current_preview: '版本 A：先网上预约，再到现场提交材料。',
        counterpart_preview: '版本 B：可直接线下取号办理，无需预约。',
      },
      comment: null,
      reviewed_by: null,
      reviewed_at: null,
      created_at: nowIso(),
      knowledge: {
        id: current.id,
        kb_id: current.kb_id,
        title: current.title,
        document_name: current.document_name,
        status: current.status,
        governance_status: current.governance_status || 'active',
        updated_at: current.updated_at,
      },
      counterpart: {
        id: counterpart.id,
        kb_id: counterpart.kb_id,
        title: counterpart.title,
        document_name: counterpart.document_name,
        status: counterpart.status,
        governance_status: counterpart.governance_status || 'active',
        updated_at: counterpart.updated_at,
      },
    },
  ];
}

export function refreshDemoConflictTasks(projectId: number, kbId?: number) {
  const count = readState().knowledgeItems.filter(
    (item) => item.project_id === projectId && (typeof kbId !== 'number' || item.kb_id === kbId),
  ).length;
  return { checked_count: count, created_task_count: Math.min(count > 1 ? 1 : 0, 1) };
}

export function bulkResolveDemoConflictTasks(
  _projectId: number,
  payload: { task_ids: number[]; action: string; comment?: string },
) {
  return {
    action: payload.action,
    resolved_count: payload.task_ids.length,
    resolved_task_ids: payload.task_ids,
  };
}

export function resolveDemoConflictTask(
  _projectId: number,
  payload: { task_id: number; action: string; comment?: string },
) {
  return {
    id: payload.task_id,
    action: payload.action,
    knowledge_id: 0,
    new_governance_status: payload.action === 'mark_conflict' ? 'conflict' : 'active',
  };
}

export function getDemoGovernanceSummary(projectId: number, kbId?: number): GovernanceSummary {
  const items = readState().knowledgeItems.filter(
    (item) => item.project_id === projectId && (typeof kbId !== 'number' || item.kb_id === kbId),
  );
  const total = items.length;
  return {
    knowledge_total_count: total,
    active_knowledge_count: Math.max(total - 2, 0),
    blocked_knowledge_count: Math.min(total, 2),
    pending_duplicate_count: total > 1 ? 1 : 0,
    pending_stale_count: total > 0 ? 1 : 0,
    pending_conflict_count: total > 1 ? 1 : 0,
    source_changed_task_count: total > 0 ? 1 : 0,
    source_fetch_failed_task_count: 0,
    governance_status_counts: {
      active: Math.max(total - 2, 0),
      review_pending: total > 1 ? 1 : 0,
      conflict: total > 2 ? 1 : 0,
    },
  };
}
