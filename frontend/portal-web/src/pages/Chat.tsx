import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react';
import { Button, Input, Select, Typography } from 'antd';
import { message } from '@/services/notify';
import type { InputRef } from 'antd';

import { useI18n } from '@/i18n/useI18n';
import { streamAskQuestion, type ChatAskResponse, type ScenePayload, type SuggestedAction } from '@/services/chatApi';
import { API_BASE_URL } from '@/services/client';
import { fetchOpeningSettings, fetchProjects, type OpeningSettings, type ProjectRecord } from '@/services/projectApi';
import { executeSceneAction } from '@/services/sceneApi';

type SourceChip = {
  key: string;
  title: string;
  meta?: string | null;
  snippet?: string;
};

type AttachmentPreview = {
  id: string;
  file: File;
  url: string;
};

type ChatEntry =
  | {
      id: string;
      type: 'message';
      role: 'assistant' | 'user';
      content: string;
      sources: SourceChip[];
      suggestedActions?: SuggestedAction[];
      generated?: boolean;
    }
  | {
      id: string;
      type: 'thinking';
    };

function createId(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function createWelcomeMessage(content: string): ChatEntry {
  return {
    id: createId('assistant'),
    type: 'message',
    role: 'assistant',
    content,
    sources: [],
  };
}

const LEGACY_TAX_DEMO_PATTERN = /IR1249|IRC3111A|税务|稅務|地址變更|地址变更|收稅單|收税单|業務地址|业务地址/i;

function containsLegacyTaxDemoText(value?: string | null) {
  return Boolean(value && LEGACY_TAX_DEMO_PATTERN.test(value));
}

function mapSourcesToChips(sources: ChatAskResponse['sources'] = []): SourceChip[] {
  return sources.map((source, index) => ({
    key: `${source.knowledge_id}-${index}`,
    title: source.title,
    meta: source.document_name || null,
    snippet: source.snippet,
  }));
}

function renderRichText(text: string) {
  const segments = text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return segments.map((segment, index) => {
    if (segment.startsWith('**') && segment.endsWith('**')) {
      return <strong key={`${segment}-${index}`}>{segment.slice(2, -2)}</strong>;
    }
    return <span key={`${segment}-${index}`}>{segment}</span>;
  });
}

function renderMarkdownLine(text: string, lineKey: string) {
  const headingMatch = text.match(/^(#{1,3})\s+(.+)$/);
  if (headingMatch) {
    return (
      <div
        key={lineKey}
        className={`nexus-chat-bubble__line nexus-chat-bubble__line--heading nexus-chat-bubble__line--heading-${headingMatch[1].length}`}
      >
        {renderRichText(headingMatch[2])}
      </div>
    );
  }

  const lineClassName = text.match(/^(\d+\.|[-*])\s/)
    ? 'nexus-chat-bubble__line nexus-chat-bubble__line--list'
    : 'nexus-chat-bubble__line';

  return (
    <div key={lineKey} className={lineClassName}>
      {renderRichText(text)}
    </div>
  );
}

function renderSceneValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '未填寫';
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  if (Array.isArray(value)) {
    return value.join('、');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function getSceneFieldLabel(scene: ScenePayload, key: string) {
  return scene.panels.summary?.field_labels?.[key] || key;
}

function getSceneFieldOptions(scene: ScenePayload, key: string) {
  return scene.panels.summary?.field_options?.[key] || [];
}

function getSceneOptionLabel(scene: ScenePayload, key: string, value: unknown) {
  const options = getSceneFieldOptions(scene, key);
  const match = options.find((option) => option.value === String(value));
  return match?.label || null;
}

function renderSceneFieldValue(scene: ScenePayload, key: string, value: unknown) {
  const displayValue = scene.panels.summary?.display_payload?.[key];
  if (displayValue !== null && displayValue !== undefined && displayValue !== '') {
    return renderSceneValue(displayValue);
  }
  const optionLabel = getSceneOptionLabel(scene, key, value);
  return optionLabel || renderSceneValue(value);
}

function getSceneOrderedFields(scene: ScenePayload) {
  const payload = scene.panels.summary?.payload || {};
  const visibleFields = scene.panels.summary?.visible_fields || [];
  if (visibleFields.length) {
    return visibleFields;
  }
  return [...new Set([...scene.missing_fields, ...Object.keys(payload)])];
}

function resolveSceneAssetUrl(url?: string | null) {
  if (!url) {
    return null;
  }
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  if (url.startsWith('/api/v1/projects/')) {
    return url.replace('/api/v1/projects/', `${API_BASE_URL}/portal/projects/`);
  }
  return `${API_BASE_URL}${url.replace(/^\/api\/v1/, '')}`;
}

function buildMailtoUrl(to: string, subject: string, body: string) {
  const params = new URLSearchParams({
    subject,
    body,
  });
  return `mailto:${encodeURIComponent(to)}?${params.toString()}`;
}

function getSceneStateLabel(scene: ScenePayload) {
  const mapping: Record<string, string> = {
    COLLECT_FORM: '資料收集中',
    REVIEW_FORM: '等待確認資料',
    REQUIRE_SIGNATURE_CONFIRMATION: '等待簽署確認',
    REVIEW_MAIL: '等待確認郵件',
    SHOW_SUBMISSION_GUIDE: '查看提交指引',
    DONE: '已完成',
    FAILED: '處理失敗',
  };
  return mapping[scene.state] || scene.state;
}

function getSceneRouteLabel(scene: ScenePayload) {
  if (scene.route_key === 'ir1249') {
    return 'IR1249';
  }
  if (scene.route_key === 'irc3111a') {
    return 'IRC3111A';
  }
  return '待判斷';
}

function getSceneMailModeLabel(scene: ScenePayload) {
  if (scene.mail_delivery_mode === 'send_enabled') {
    return '可真實發信';
  }
  if (scene.mail_delivery_mode === 'draft_only') {
    return '僅郵件預覽';
  }
  return '提交模式待定';
}

function getSceneFieldExample(field: string) {
  const examples: Record<string, string> = {
    effective_date: '例如：2026-05-01',
    new_address: '例如：香港九龍觀塘道 88 號 10 樓 A 室',
    old_address: '例如：香港九龍觀塘道 66 號 8 樓',
    applicant_type: '可直接點選下方類別',
    reference_id: '例如：A123456(7)',
    individual_file_no: '例如：12345678',
    property_tax_location: '例如：香港九龍旺角彌敦道 8 號 12 樓',
    property_tax_file_no: '例如：PT1234567',
    daytime_phone: '例如：91234567',
    signer_name: '例如：CHAN TAI MAN',
    business_registration_no: '例如：12345678-000-01-26-0',
    business_name: '例如：ABC Trading Company',
    profits_tax_file_no: '例如：PTX1234567',
    employer_return_file_no: '例如：ER1234567',
    designation: '例如：董事 / 負責人',
    signer_identity_no: '例如：A123456(7)',
    telephone_no: '例如：23456789',
  };
  return examples[field] || '請直接輸入相關資料';
}

function ThinkingCard({ phase, thinkingStages, processNodes, inProgressLabel }: { phase: number; thinkingStages: string[]; processNodes: string[]; inProgressLabel: string }) {
  return (
    <div className="nexus-chat-row nexus-chat-row--assistant">
      <div className="nexus-thinking-card">
        <div className="nexus-thinking-card__header">
          <span className="nexus-thinking-card__scanner" />
          <span className="nexus-thinking-card__label">{thinkingStages[phase]}</span>
          <span className="nexus-thinking-card__badge">{inProgressLabel}</span>
        </div>
        <div className="nexus-thinking-card__line">
          <span className="nexus-thinking-card__lineGlow" />
        </div>
        <div className="nexus-thinking-card__nodes">
          {processNodes.map((node, index) => (
            <div
              key={node}
              className={`nexus-thinking-card__node ${index <= phase ? 'is-active' : ''}`}
            >
              <span className="nexus-thinking-card__nodeDot" />
              <span>{node}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ComposerGlyph({ type }: { type: 'image' | 'send' | 'close' }) {
  if (type === 'image') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4.5" y="5.5" width="15" height="13" rx="4" />
        <path d="M8.5 14.5 11.2 11.8a1.2 1.2 0 0 1 1.7 0l1.4 1.4 1.1-1.1a1.2 1.2 0 0 1 1.7 0l2.4 2.4" />
        <circle cx="9.2" cy="9.6" r="1.3" />
      </svg>
    );
  }

  if (type === 'close') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m8 8 8 8M16 8l-8 8" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6.5 12H16.5" />
      <path d="m12.5 8 4 4-4 4" />
    </svg>
  );
}

function SceneCollectorCard(
  {
    scene,
    disabled,
    onQuickReply,
  }: {
    scene: ScenePayload;
    disabled: boolean;
    onQuickReply: (value: string) => void;
  },
) {
  const payload = scene.panels.summary?.payload || {};
  const fieldLabels = scene.panels.summary?.field_labels || {};
  const orderedFields = getSceneOrderedFields(scene);
  const recommendedFields = new Set(scene.panels.summary?.recommended_fields || []);
  const requiredOrderedFields = orderedFields.filter((field) => !recommendedFields.has(field));
  const completedCount = requiredOrderedFields.filter((field) => {
    const value = payload[field];
    return value !== null && value !== undefined && value !== '';
  }).length;
  const activeField = scene.missing_fields[0] || null;
  const progress = requiredOrderedFields.length ? Math.max((completedCount / requiredOrderedFields.length) * 100, completedCount ? 12 : 6) : 0;
  const applicantTypeOptions = getSceneFieldOptions(scene, 'applicant_type');
  const currentApplicantType = String(payload.applicant_type || '');

  return (
    <div className="portal-scene-collector">
      <div className="portal-scene-collector__header">
        <div>
          <div className="portal-scene-collector__eyebrow">資訊收集器</div>
          <div className="portal-scene-collector__title">
            正在填寫 {scene.panels.route_overview?.form_no || getSceneRouteLabel(scene)}
          </div>
        </div>
        <div className="portal-scene-collector__count">
          {completedCount}/{requiredOrderedFields.length || orderedFields.length}
        </div>
      </div>

      <div className="portal-scene-collector__progress">
        <div className="portal-scene-collector__progressBar" style={{ width: `${progress}%` }} />
      </div>

      {scene.panels.route_overview ? (
        <div className="portal-scene-collector__modeCard">
          <div className="portal-scene-collector__modeLabel">當前辦理方式</div>
          <div className="portal-scene-collector__modeTitle">{scene.panels.route_overview.title}</div>
          <div className="portal-scene-collector__modeDesc">{scene.panels.route_overview.description}</div>
        </div>
      ) : null}

      {scene.route_key === 'ir1249' && applicantTypeOptions.length ? (
        <div className="portal-scene-collector__selector">
          <div className="portal-scene-collector__selectorLabel">申請人類別</div>
          <div className="portal-scene-collector__selectorGrid">
            {applicantTypeOptions.map((option) => {
              const active = currentApplicantType === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={disabled}
                  className={`portal-scene-collector__selectorChip ${active ? 'is-active' : ''}`}
                  onClick={() => onQuickReply(option.value)}
                >
                  <span className="portal-scene-collector__selectorChipTitle">{option.label}</span>
                  {option.description ? (
                    <span className="portal-scene-collector__selectorChipDesc">{option.description}</span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {activeField ? (
        <div className="portal-scene-collector__prompt">
          <div className="portal-scene-collector__promptLabel">當前只需提供</div>
          <div className="portal-scene-collector__promptTitle">{fieldLabels[activeField] || activeField}</div>
          <div className="portal-scene-collector__promptHint">{getSceneFieldExample(activeField)}</div>
        </div>
      ) : null}

      <div className="portal-scene-collector__grid">
        {orderedFields.map((field, index) => {
          const value = payload[field];
          const completed = value !== null && value !== undefined && value !== '';
          const active = activeField === field;
          const stateClass = completed ? 'is-complete' : active ? 'is-active' : 'is-pending';
          return (
            <div key={field} className={`portal-scene-collector__item ${stateClass}`}>
              <div className="portal-scene-collector__itemBadge">
                {completed ? '✓' : index + 1}
              </div>
              <div className="portal-scene-collector__itemBody">
                <div className="portal-scene-collector__itemLabel">
                  {fieldLabels[field] || field}
                  {recommendedFields.has(field) ? (
                    <span className="portal-scene-collector__itemTag">建議補充</span>
                  ) : null}
                </div>
                <div className="portal-scene-collector__itemValue">
                  {completed ? renderSceneFieldValue(scene, field, value) : active ? '等待本輪輸入' : recommendedFields.has(field) ? '選填，但建議補充' : '稍後繼續'}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SceneReviewCard(
  {
    scene,
    sceneActionLoading,
    onAction,
  }: {
    scene: ScenePayload;
    sceneActionLoading: string | null;
    onAction: (actionName: string) => void;
  },
) {
  const payload = scene.panels.summary?.payload || {};
  const orderedFields = getSceneOrderedFields(scene);
  const entries = orderedFields
    .filter((field) => payload[field] !== null && payload[field] !== undefined && payload[field] !== '')
    .map((field) => [field, payload[field]] as const);
  const previewPdfUrl = resolveSceneAssetUrl(scene.panels.pdf_preview?.preview_url);
  const finalPdfUrl = resolveSceneAssetUrl(scene.panels.pdf_preview?.final_url) || previewPdfUrl;
  const mailPreview = scene.panels.mail_preview;
  const localMailtoUrl = mailPreview
    ? buildMailtoUrl(mailPreview.to, mailPreview.subject, mailPreview.body)
    : null;

  return (
    <div className="portal-scene-review">
      <div className="portal-scene-review__eyebrow">辦理確認卡</div>
      <div className="portal-scene-review__title">
        {scene.panels.route_overview?.title || '資料確認'}
        {scene.panels.route_overview?.form_no ? ` · ${scene.panels.route_overview.form_no}` : ''}
      </div>
      <div className="portal-scene-review__desc">
        {scene.summary || '請確認以下資料是否正確。確認後再繼續下一步。'}
      </div>

      {entries.length ? (
        <div className="portal-scene-review__grid">
          {entries.map(([key, value]) => (
            <div key={key} className="portal-scene-review__item">
              <div className="portal-scene-review__label">{getSceneFieldLabel(scene, key)}</div>
              <div className="portal-scene-review__value">{renderSceneFieldValue(scene, key, value)}</div>
            </div>
          ))}
        </div>
      ) : null}

      {previewPdfUrl ? (
        <div className="portal-scene-review__section">
          <div className="portal-scene-review__sectionHeader">
            <div className="portal-scene-review__sectionTitle">PDF 預覽</div>
            <div className="portal-scene-review__sectionActions">
              <a
                href={previewPdfUrl}
                target="_blank"
                rel="noreferrer"
                className="portal-scene-review__sectionLink"
              >
                打開 PDF
              </a>
              {finalPdfUrl ? (
                <a
                  href={finalPdfUrl}
                  target="_blank"
                  rel="noreferrer"
                  download
                  className="portal-scene-review__sectionLink"
                >
                  下載 PDF
                </a>
              ) : null}
            </div>
          </div>
          <object
            aria-label="scene-pdf-preview-inline"
            data={previewPdfUrl}
            type="application/pdf"
            className="portal-scene-review__iframe"
          >
            <div className="portal-scene-review__pdfFallback">
              當前聊天框內無法直接預覽 PDF，請點擊上方「打開 PDF」查看。
            </div>
          </object>
        </div>
      ) : null}

      {mailPreview ? (
        <div className="portal-scene-review__section">
          <div className="portal-scene-review__sectionHeader">
            <div className="portal-scene-review__sectionTitle">郵件預覽</div>
          </div>
          <div className="portal-scene-review__mail">
            <div>To: {mailPreview.to}</div>
            <div>Subject: {mailPreview.subject}</div>
            <div className="portal-scene-review__mailBody">{mailPreview.body}</div>
          </div>
          {finalPdfUrl ? (
            <div className="portal-scene-review__mailHint">
              已打開本地郵箱後，請記得手動附上上方下載的 PDF。
            </div>
          ) : null}
        </div>
      ) : null}

      {scene.next_actions.length || localMailtoUrl ? (
        <div className="portal-scene-review__actions">
          {scene.next_actions.map((action) => (
            <Button
              key={action.name}
              type={action.name === 'send_mail' ? 'primary' : 'default'}
              loading={sceneActionLoading === action.name}
              onClick={() => onAction(action.name)}
            >
              {action.label}
            </Button>
          ))}
          {localMailtoUrl ? (
            <Button href={localMailtoUrl} type="primary">
              本地郵箱發送
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default function ChatPage() {
  const { locale, localeOptions, setLocale, t, tList } = useI18n();
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [projectLoadError, setProjectLoadError] = useState<string | null>(null);
  const [projectReloadToken, setProjectReloadToken] = useState(0);
  const [openingSettingsByProject, setOpeningSettingsByProject] = useState<Record<number, OpeningSettings>>({});
  const [activeProjectId, setActiveProjectId] = useState<number>();
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [thinkingPhase, setThinkingPhase] = useState(0);
  const [contextHint, setContextHint] = useState<string | null>(null);
  const [queryMode] = useState<'enhanced' | 'precision'>('enhanced');
  const [currentScene, setCurrentScene] = useState<ScenePayload | null>(null);
  const [sceneActionLoading, setSceneActionLoading] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<AttachmentPreview[]>([]);
  const [messages, setMessages] = useState<ChatEntry[]>([createWelcomeMessage(t('chat.welcomeWithoutProject'))]);
  const inputRef = useRef<InputRef>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const attachmentsRef = useRef<AttachmentPreview[]>([]);
  const streamEndRef = useRef<HTMLDivElement | null>(null);
  const thinkingStages = tList('chat.thinkingStages');
  const processNodes = tList('chat.processNodes');
  const fallbackSampleQuestions = tList('chat.sampleQuestions');
  const useTraditionalChinese = locale === 'zh-Hant';
  const useEnglish = locale === 'en';
  const buildWelcomeMessage = (projectName?: string | null, openingText?: string | null) =>
    createWelcomeMessage(
      openingText?.trim() && !containsLegacyTaxDemoText(openingText)
        ? openingText
        : projectName
          ? t('chat.welcomeWithProject', { projectName })
          : t('chat.welcomeWithoutProject'),
    );

  const retryProjectLoad = () => {
    setProjectReloadToken((current) => current + 1);
  };

  useEffect(() => {
    let cancelled = false;

    const loadProjects = async () => {
      setProjectsLoading(true);
      setProjectLoadError(null);

      try {
        let items: ProjectRecord[] = [];

        for (let attempt = 0; attempt < 3; attempt += 1) {
          try {
            items = await fetchProjects();
            break;
          } catch (error) {
            if (attempt === 2) {
              throw error;
            }
            await new Promise((resolve) => window.setTimeout(resolve, 1200 * (attempt + 1)));
          }
        }

        if (cancelled) {
          return;
        }

        setProjects(items);
        if (items[0]) {
          setActiveProjectId(items[0].id);
          setMessages([buildWelcomeMessage(items[0].company_name)]);
        } else {
          setActiveProjectId(undefined);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        const errorMessage = error instanceof Error ? error.message : t('chat.projectsLoadError');
        setProjectLoadError(errorMessage);
        message.error(errorMessage);
      } finally {
        if (!cancelled) {
          setProjectsLoading(false);
        }
      }
    };

    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, [projectReloadToken, t]);

  useEffect(() => {
    const hasThinking = messages.some((item) => item.type === 'thinking');
    if (!hasThinking) {
      setThinkingPhase(0);
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setThinkingPhase((current) => (current + 1) % thinkingStages.length);
    }, 1200);

    return () => window.clearInterval(intervalId);
  }, [messages, thinkingStages.length]);

  useEffect(() => {
    streamEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, loading, currentScene, sceneActionLoading]);

  useEffect(() => {
    attachmentsRef.current = attachments;
  }, [attachments]);

  useEffect(
    () => () => {
      attachmentsRef.current.forEach((item) => URL.revokeObjectURL(item.url));
    },
    [],
  );

  const activeProject = useMemo(
    () => projects.find((project) => project.id === activeProjectId),
    [projects, activeProjectId],
  );
  const activeOpeningSettings = activeProjectId ? openingSettingsByProject[activeProjectId] : undefined;
  const sampleQuestions = useMemo(() => {
    const configured = activeOpeningSettings?.recommended_questions?.filter(Boolean) || [];
    const sanitized = configured.filter((question) => !containsLegacyTaxDemoText(question));
    const preferred = sanitized.length ? sanitized : fallbackSampleQuestions;
    return [...new Set(preferred)].slice(0, 6);
  }, [activeOpeningSettings?.recommended_questions, fallbackSampleQuestions]);
  const projectOptions = useMemo(
    () =>
      projects.map((project) => ({
        value: project.id,
        label: `${project.company_name} (${project.project_key})`,
      })),
    [projects],
  );

  const currentScenePrimaryField = currentScene?.missing_fields?.[0];
  const currentScenePrimaryLabel = currentScene && currentScenePrimaryField
    ? getSceneFieldLabel(currentScene, currentScenePrimaryField)
    : null;
  const currentScenePrimaryExample = currentScenePrimaryField ? getSceneFieldExample(currentScenePrimaryField) : null;
  const currentScenePrimaryOptions = useMemo(() => {
    if (!currentScene || !currentScenePrimaryField) {
      return [];
    }
    return getSceneFieldOptions(currentScene, currentScenePrimaryField);
  }, [currentScene, currentScenePrimaryField]);
  const composerPlaceholder = currentScenePrimaryLabel
    ? `請先輸入${currentScenePrimaryLabel}，${currentScenePrimaryExample}`
    : t('chat.inputPlaceholder');
  const showInlineReviewCard = Boolean(currentScene && currentScene.state !== 'COLLECT_FORM');
  const statusItems = useMemo(
    () => [
      activeProjectId ? t('chat.statusKnowledgeReady') : t('chat.statusKnowledgePending'),
      contextHint || (activeProjectId ? t('chat.statusContextReady') : t('chat.statusContextPending')),
      queryMode === 'precision' ? t('chat.statusPrecision') : t('chat.statusEnhanced'),
      attachments.length ? t('chat.attachmentsReady') : t('chat.attachmentsEmpty'),
    ],
    [activeProjectId, attachments.length, contextHint, queryMode, t],
  );

  useEffect(() => {
    if (!activeProjectId || openingSettingsByProject[activeProjectId]) {
      return;
    }

    const loadOpeningSettings = async () => {
      try {
        const settings = await fetchOpeningSettings(activeProjectId);
        setOpeningSettingsByProject((current) => ({ ...current, [activeProjectId]: settings }));
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('chat.requestFailed'));
      }
    };

    void loadOpeningSettings();
  }, [activeProjectId, openingSettingsByProject, t]);

  const sendQuestion = async (presetQuestion?: string) => {
    if (!activeProjectId) {
      message.warning(t('chat.selectProjectWarning'));
      return;
    }

    const question = (presetQuestion ?? input).trim();
    if (!question || loading) {
      return;
    }

    const userMessageId = createId('user');
    const assistantMessageId = createId('assistant');

    setInput('');
    setMessages((current) => [
      ...current,
      {
        id: userMessageId,
        type: 'message',
        role: 'user',
        content: question,
        sources: [],
      },
      {
        id: assistantMessageId,
        type: 'thinking',
      },
    ]);

    try {
      setLoading(true);
      await streamAskQuestion(
        activeProjectId,
        {
          session_id: sessionId,
          query: question,
          use_memory: true,
          source: 'portal',
          switches: {
            sensitiveDetection: true,
            retrievalFilter: queryMode === 'precision',
            knowledgeTree: false,
          },
        },
          {
            onMeta: (payload) => {
              setSessionId(payload.session_id);
              setContextHint(payload.use_memory ? t('chat.memoryOn') : t('chat.memoryOff'));
              setCurrentScene(payload.scene ?? null);
            },
          onDelta: (content) => {
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantMessageId
                  ? {
                      id: assistantMessageId,
                      type: 'message',
                      role: 'assistant',
                      content: `${item.type === 'message' ? item.content : ''}${content}`,
                      sources: [],
                      suggestedActions: [],
                      generated: true,
                    }
                  : item,
              ),
            );
          },
          onDone: (payload) => {
            setCurrentScene(payload.scene ?? null);
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantMessageId
                  ? {
                      id: assistantMessageId,
                      type: 'message',
                      role: 'assistant',
                      content: payload.answer,
                      sources: mapSourcesToChips(payload.sources),
                      suggestedActions: payload.suggested_actions || [],
                      generated: true,
                    }
                  : item,
              ),
            );
          },
          onError: (errorMessage) => {
            setMessages((current) =>
              current.map((item) =>
                item.id === assistantMessageId
                  ? {
                      id: assistantMessageId,
                      type: 'message',
                      role: 'assistant',
                      content: errorMessage,
                      sources: [],
                      suggestedActions: [],
                    }
                  : item,
              ),
            );
          },
        },
      );
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : t('chat.requestFailed');
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantMessageId
            ? {
                id: assistantMessageId,
                type: 'message',
                role: 'assistant',
                content: errorMessage,
                sources: [],
                suggestedActions: [],
              }
            : item,
        ),
      );
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleProjectChange = (projectId: number) => {
    const nextProject = projects.find((item) => item.id === projectId);
    const nextOpeningSettings = openingSettingsByProject[projectId];
    setActiveProjectId(projectId);
    setSessionId(undefined);
    setContextHint(null);
    setCurrentScene(null);
    setMessages([buildWelcomeMessage(nextProject?.company_name, nextOpeningSettings?.opening_text)]);
  };

  const openImagePicker = () => {
    if (!activeProjectId || loading) {
      return;
    }
    fileInputRef.current?.click();
  };

  const handleAttachmentChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []).filter((file) => file.type.startsWith('image/'));
    if (!files.length) {
      return;
    }

    const nextItems = files.slice(0, 4).map((file) => ({
      id: createId('attachment'),
      file,
      url: URL.createObjectURL(file),
    }));

    setAttachments((current) => {
      current.forEach((item) => URL.revokeObjectURL(item.url));
      return nextItems;
    });
    message.info(t('chat.attachPreviewOnly'));
    event.target.value = '';
  };

  const removeAttachment = (attachmentId: string) => {
    setAttachments((current) => {
      const target = current.find((item) => item.id === attachmentId);
      if (target) {
        URL.revokeObjectURL(target.url);
      }
      return current.filter((item) => item.id !== attachmentId);
    });
  };

  const hasConversation = messages.some((item) => item.type === 'message' && item.role === 'user');
  const renderedMessages = messages;

  const handleSceneAction = async (actionName: string) => {
    if (!activeProjectId || !currentScene) {
      return;
    }
    try {
      setSceneActionLoading(actionName);
      const action = currentScene.next_actions.find((item) => item.name === actionName);
      const result = await executeSceneAction(activeProjectId, currentScene.case_id, actionName, {
        confirmationToken: action?.confirmation_token || null,
      });
      setCurrentScene(result.scene);
      setMessages((current) => [
        ...current,
        {
          id: createId('assistant'),
          type: 'message',
          role: 'assistant',
          content: result.message,
          sources: [],
          suggestedActions: [],
        },
      ]);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '場景動作執行失敗';
      message.error(errorMessage);
    } finally {
      setSceneActionLoading(null);
    }
  };

  useEffect(() => {
    if (hasConversation) {
      return;
    }
    const nextWelcomeEntry = buildWelcomeMessage(
      activeProject?.company_name,
      activeOpeningSettings?.opening_text,
    );
    if (messages.length === 1 && messages[0]?.type === 'message' && messages[0].content === nextWelcomeEntry.content) {
      return;
    }
    setMessages([nextWelcomeEntry]);
  }, [activeOpeningSettings?.opening_text, activeProject?.company_name, buildWelcomeMessage, hasConversation, messages]);

  return (
    <div className="portal-shell portal-shell--phoneChat">
      <section className="portal-chat-phone">
        <header className="portal-chat-phone__header">
          <div className="portal-chat-phone__headerTop">
            <div className="portal-chat-phone__titleGroup">
              <span className="portal-chat-phone__avatar" aria-hidden="true" />
              <div>
                <div className="portal-chat-phone__title">{t('chat.assistantName')}</div>
                <div className="portal-chat-phone__subtitle">{contextHint || t('chat.panelHint')}</div>
              </div>
            </div>
            <div className="portal-chat-phone__controls">
              <div className="portal-chat-phone__controlShell portal-chat-phone__controlShell--project">
                <Select
                  className="portal-chat-phone__projectSelect"
                  placeholder={t('chat.projectPlaceholder')}
                  value={activeProjectId}
                  options={projectOptions}
                  loading={projectsLoading}
                  notFoundContent={projectsLoading ? t('chat.projectsLoading') : t('chat.projectsEmpty')}
                  onChange={handleProjectChange}
                />
              </div>
              <div className="portal-chat-phone__controlShell portal-chat-phone__controlShell--locale">
                <Select
                  className="portal-chat-phone__localeSelect"
                  value={locale}
                  options={localeOptions}
                  onChange={setLocale}
                  placeholder={t('chat.languagePlaceholder')}
                />
              </div>
            </div>
          </div>
          {projectLoadError ? (
            <div className="portal-chat-phone__projectLoadError">
              <Typography.Text type="danger">{projectLoadError}</Typography.Text>
              <Button size="small" onClick={retryProjectLoad} loading={projectsLoading}>
                {t('chat.retryLoadProjects')}
              </Button>
            </div>
          ) : null}
          <div className="portal-chat-phone__statusRibbon">
            <span className="portal-chat-phone__statusRibbonLabel">{t('chat.statusRibbonPrefix')}</span>
            <div className="portal-chat-phone__statusRibbonItems">
              {statusItems.map((item) => (
                <span key={item} className="portal-chat-phone__statusPill">
                  {item}
                </span>
              ))}
            </div>
          </div>
        </header>

        <div className={`portal-chat-phone__body${hasConversation ? '' : ' portal-chat-phone__body--empty'}`}>
          <div className={`portal-chat-stream portal-chat-stream--phone${hasConversation ? '' : ' portal-chat-stream--empty'}`}>
            {renderedMessages.length ? (
              renderedMessages.map((item) => {
                if (item.type === 'thinking') {
                  return <ThinkingCard key={item.id} phase={thinkingPhase} thinkingStages={thinkingStages} processNodes={processNodes} inProgressLabel={t('chat.inProgress')} />;
                }

                const lines = item.content.split('\n');

                return (
                  <div
                    key={item.id}
                    className={`nexus-chat-row ${
                      item.role === 'user' ? 'nexus-chat-row--user' : 'nexus-chat-row--assistant'
                    }`}
                  >
                    <div
                      className={`nexus-chat-bubble ${
                        item.role === 'user' ? 'nexus-chat-bubble--user' : 'nexus-chat-bubble--assistant'
                      }`}
                    >
                      {item.role === 'assistant' ? (
                        <div className="nexus-chat-bubble__assistantHead">
                          <div className="nexus-chat-bubble__assistantIdentity">
                            <span className="nexus-chat-bubble__assistantIcon" />
                            <div>
                              <Typography.Text className="nexus-chat-bubble__assistantName">
                                {t('chat.assistantName')}
                              </Typography.Text>
                              <Typography.Text className="nexus-chat-bubble__assistantState">
                                {item.generated ? t('chat.generatedByKnowledge') : t('chat.systemWelcome')}
                              </Typography.Text>
                            </div>
                          </div>
                        </div>
                      ) : null}

                      <div className="nexus-chat-bubble__body">
                        {lines.map((line, index) => {
                          const normalized = line.trim();
                          if (!normalized) {
                            return <div key={`${item.id}-space-${index}`} className="nexus-chat-bubble__spacer" />;
                          }
                          return renderMarkdownLine(normalized, `${item.id}-line-${index}`);
                        })}
                      </div>

                      {item.role === 'assistant' && item.sources.length ? (
                        <div className="nexus-chat-bubble__sources">
                          {item.sources.map((source) => (
                            <button
                              key={source.key}
                              type="button"
                              className="nexus-chat-bubble__sourceChip"
                              title={source.snippet || source.title}
                              onClick={() => void sendQuestion(source.title)}
                            >
                              <span className="nexus-chat-bubble__sourceChipTitle">{source.title}</span>
                              {source.meta ? (
                                <span className="nexus-chat-bubble__sourceChipMeta">{source.meta}</span>
                              ) : null}
                            </button>
                          ))}
                        </div>
                      ) : null}

                      {item.role === 'assistant' && item.suggestedActions?.length ? (
                        <div className="nexus-chat-bubble__actions">
                          {item.suggestedActions.map((action) => (
                            <button
                              key={action.key}
                              type="button"
                              className="nexus-chat-bubble__actionChip"
                              onClick={() => void sendQuestion(action.prompt)}
                            >
                              {action.label}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                );
              })
            ) : null}

            {showInlineReviewCard && currentScene ? (
              <div className="portal-chat-phone__scene">
                <SceneReviewCard
                  scene={currentScene}
                  sceneActionLoading={sceneActionLoading}
                  onAction={(actionName) => void handleSceneAction(actionName)}
                />
              </div>
            ) : null}

            <div ref={streamEndRef} />
          </div>
        </div>

        <footer className="portal-chat-phone__composer">
          {!hasConversation && sampleQuestions.length ? (
            <div className="portal-chat-emptyState portal-chat-emptyState--phone">
              <span className="portal-chat-emptyState__hint">{t('chat.emptyHint')}</span>
              <div className="portal-chat-emptyState__samples">
                {sampleQuestions.map((sample) => (
                  <button
                    key={`empty-${sample}`}
                    type="button"
                    className="portal-chat-emptyState__sample"
                    onClick={() => void sendQuestion(sample)}
                  >
                    {sample}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {currentScenePrimaryLabel ? (
            <div className="portal-chat-phone__helper">
              {`當前請填寫：${currentScenePrimaryLabel}${currentScenePrimaryExample ? ` · ${currentScenePrimaryExample}` : ''}`}
            </div>
          ) : null}

          {currentScenePrimaryOptions.length ? (
            <div className="portal-chat-phone__quickReplies">
              {currentScenePrimaryOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className="portal-chat-phone__quickReply"
                  disabled={loading}
                  onClick={() => void sendQuestion(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          ) : null}

          {currentScene?.next_actions?.length && !showInlineReviewCard ? (
            <div className="portal-chat-phone__quickReplies">
              {currentScene.next_actions.map((action) => (
                <button
                  key={action.name}
                  type="button"
                  className="portal-chat-phone__quickReply portal-chat-phone__quickReply--action"
                  disabled={sceneActionLoading === action.name}
                  onClick={() => void handleSceneAction(action.name)}
                >
                  {action.label}
                </button>
              ))}
            </div>
          ) : null}

          {attachments.length ? (
            <div className="portal-chat-composer__attachments">
              {attachments.map((attachment) => (
                <div key={attachment.id} className="portal-chat-composer__attachmentTile">
                  <img src={attachment.url} alt={attachment.file.name} className="portal-chat-composer__attachmentImage" />
                  <button
                    type="button"
                    className="portal-chat-composer__attachmentRemove"
                    onClick={() => removeAttachment(attachment.id)}
                    aria-label={t('chat.attachmentsClear')}
                    title={t('chat.attachmentsClear')}
                  >
                    <ComposerGlyph type="close" />
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={handleAttachmentChange}
          />

          <div className="portal-chat-composer portal-chat-composer--phone">
            <div className="portal-chat-composer__actions">
              <button
                type="button"
                className="portal-chat-composer__iconButton"
                disabled={loading || !activeProjectId}
                onClick={openImagePicker}
                title={t('chat.attachImage')}
                aria-label={t('chat.attachImage')}
              >
                <ComposerGlyph type="image" />
              </button>
            </div>
            <div className="portal-chat-composer__inputShell">
              <Input
                ref={inputRef}
                value={input}
                disabled={loading || !activeProjectId}
                className="portal-chat-composer__input"
                placeholder={composerPlaceholder}
                onChange={(event) => setInput(event.target.value)}
                onPressEnter={(event) => {
                  event.preventDefault();
                  void sendQuestion();
                }}
              />
            </div>
            <Button
              type="primary"
              className="portal-chat-sendButton"
              loading={loading}
              disabled={!activeProjectId}
              onClick={() => void sendQuestion()}
            >
              <span className="portal-chat-sendButton__label">{t('chat.send')}</span>
              <span className="portal-chat-sendButton__icon" aria-hidden="true">
                <ComposerGlyph type="send" />
              </span>
            </Button>
          </div>
        </footer>
      </section>
    </div>
  );
}
