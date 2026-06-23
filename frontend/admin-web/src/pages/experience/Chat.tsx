import { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Card, Col, Empty, Input, Row, Space, Tag, Typography } from 'antd';
import { message } from '@/services/notify';

import AdminPage from '@/components/AdminPage';
import { useI18n } from '@/i18n/useI18n';
import { useActiveProject } from '@/hooks/useActiveProject';
import { fetchKnowledgeBases, type KnowledgeBaseRecord } from '@/services/knowledgeApi';
import { fetchOpeningSettings, type OpeningSettings } from '@/services/projectApi';
import {
  askProjectChat,
  fetchProjectSessionDetail,
  fetchProjectSessions,
  type ChatStreamMeta,
  type ChatSessionDetail,
  type ChatSessionSummary,
  type ChatSessionTurn,
  streamProjectChat,
} from '@/services/sessionApi';

type ChatBubble = {
  key: string;
  role: 'assistant' | 'user';
  content: string;
  sources?: ChatSessionTurn['sources'];
  rewrittenQuery?: string;
  traceId?: string | null;
  usedMemory?: boolean;
  createdAt?: string | null;
};

type ChatSwitches = {
  sensitiveDetection: boolean;
  retrievalFilter: boolean;
  knowledgeTree: boolean;
};

const defaultSwitches: ChatSwitches = {
  sensitiveDetection: true,
  retrievalFilter: true,
  knowledgeTree: false,
};

function createWelcomeMessages(content: string): ChatBubble[] {
  return [
    {
      key: 'welcome',
      role: 'assistant',
      content,
    },
  ];
}

function buildMessagesFromTurns(turns: ChatSessionTurn[]): ChatBubble[] {
  return turns.flatMap((turn) => [
    {
      key: `user-${turn.id}`,
      role: 'user',
      content: turn.query,
      createdAt: turn.created_at,
    },
    {
      key: `assistant-${turn.id}`,
      role: 'assistant',
      content: turn.answer,
      sources: turn.sources,
      rewrittenQuery: turn.rewritten_query,
      traceId: turn.trace_id,
      usedMemory: turn.used_memory,
      createdAt: turn.created_at,
    },
  ]);
}

export default function ExperienceChatPage() {
  const { activeProject, activeProjectId } = useActiveProject();
  const { t, tList } = useI18n();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseRecord[]>([]);
  const [openingSettings, setOpeningSettings] = useState<OpeningSettings | null>(null);
  const [selectedKbIds, setSelectedKbIds] = useState<number[]>([]);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSessionDetail | null>(null);
  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [query, setQuery] = useState('');
  const [sending, setSending] = useState(false);
  const [switches, setSwitches] = useState<ChatSwitches>(defaultSwitches);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending]);

  const fallbackSuggestedQueries = tList('experience.suggestedQueries');
  const suggestedQueries = useMemo(() => {
    const configured = openingSettings?.recommended_questions?.filter(Boolean) || [];
    return (configured.length ? configured : fallbackSuggestedQueries).slice(0, 6);
  }, [fallbackSuggestedQueries, openingSettings?.recommended_questions]);

  const resetConversation = (projectName?: string | null) => {
    setCurrentSession(null);
    setMessages(createWelcomeMessages(t('experience.welcome', { projectName: projectName || 'NexusClaw' })));
    setQuery('');
  };

  const loadKnowledgeBases = async (projectId: number) => {
    try {
      const result = await fetchKnowledgeBases(projectId);
      setKnowledgeBases(result);
      setSelectedKbIds((previous) => {
        if (previous.length > 0) {
          return previous;
        }
        const defaults = result.filter((item) => item.is_default).map((item) => item.id);
        return defaults.length > 0 ? defaults : result.slice(0, 1).map((item) => item.id);
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('experience.knowledgeLoadError'));
    }
  };

  const loadSessions = async (projectId: number) => {
    try {
      const result = await fetchProjectSessions(String(projectId));
      setSessions(result.data || []);
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('experience.sessionsLoadError'));
    }
  };

  useEffect(() => {
    if (!activeProjectId) {
      setKnowledgeBases([]);
      setOpeningSettings(null);
      setSessions([]);
      setSelectedKbIds([]);
      resetConversation(activeProject?.company_name);
      return;
    }

    resetConversation(activeProject?.company_name);
    setOpeningSettings(null);
    setSelectedKbIds([]);
    setSwitches(defaultSwitches);
    void loadKnowledgeBases(activeProjectId);
    void loadSessions(activeProjectId);
  }, [activeProject?.company_name, activeProjectId, t]);

  useEffect(() => {
    if (!activeProjectId) {
      return;
    }

    const loadOpeningSettings = async () => {
      try {
        const result = await fetchOpeningSettings(activeProjectId);
        setOpeningSettings(result);
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('experience.recommendedQuestionsLoadError'));
        setOpeningSettings(null);
      }
    };

    void loadOpeningSettings();
  }, [activeProjectId, t]);

  useEffect(() => {
    if (currentSession || messages.length !== 1 || messages[0]?.role !== 'assistant') {
      return;
    }
    const nextWelcomeMessage = t('experience.welcome', { projectName: activeProject?.company_name || 'NexusClaw' });
    if (messages[0]?.content === nextWelcomeMessage) {
      return;
    }
    setMessages(createWelcomeMessages(nextWelcomeMessage));
  }, [activeProject?.company_name, currentSession, messages, t]);

  const activeSessionTitle = useMemo(() => {
    if (currentSession?.title) {
      return currentSession.title;
    }
    return currentSession?.session_id
      ? sessions.find((item) => item.session_id === currentSession.session_id)?.title || t('experience.currentSession')
      : t('experience.newSession');
  }, [currentSession, sessions, t]);

  const handleStartNewConversation = () => {
    resetConversation(activeProject?.company_name);
    const defaults = knowledgeBases.filter((item) => item.is_default).map((item) => item.id);
    setSelectedKbIds(defaults.length > 0 ? defaults : knowledgeBases.slice(0, 1).map((item) => item.id));
  };

  const syncSessionAfterReply = async (projectId: number, sessionId: string) => {
    const [detail, sessionResult] = await Promise.all([
      fetchProjectSessionDetail(projectId, sessionId),
      fetchProjectSessions(String(projectId)),
    ]);
    setCurrentSession(detail);
    setMessages(buildMessagesFromTurns(detail.turns));
    setSessions(sessionResult.data || []);
  };

  const applyMeta = (meta: ChatStreamMeta) => {
    setCurrentSession((previous) => ({
      session_id: meta.session_id,
      title: previous?.title || activeSessionTitle || t('experience.currentSession'),
      source: previous?.source || 'admin',
      status: previous?.status || 'active',
      selected_kb_ids: selectedKbIds,
      summary: previous?.summary || null,
      state_json: previous?.state_json || {},
      turns: previous?.turns || [],
    }));
  };

  const fallbackAsk = async (projectId: number, content: string) => {
    const result = await askProjectChat(projectId, {
      session_id: currentSession?.session_id,
      query: content,
      use_memory: true,
      source: 'admin',
      selected_kb_ids: selectedKbIds,
      switches: {
        sensitive_detection: switches.sensitiveDetection,
        retrieval_filter: switches.retrievalFilter,
        retrieval_guard: switches.retrievalFilter,
        knowledge_tree: switches.knowledgeTree,
      },
    });

    setMessages((previous) =>
      previous.map((item) =>
        item.key === 'assistant-pending'
          ? {
              ...item,
              key: `assistant-${Date.now()}`,
              content: result.answer || t('experience.noAnswer'),
              sources: result.sources,
              rewrittenQuery: result.rewritten_query,
              traceId: result.trace_id,
              usedMemory: result.memory?.used,
            }
          : item,
      ),
    );
    await syncSessionAfterReply(projectId, result.session_id);
  };

  const handleSend = async (presetQuery?: string) => {
    if (!activeProjectId || sending) {
      return;
    }

    const content = (presetQuery ?? query).trim();
    if (!content) {
      return;
    }

    const userMessage: ChatBubble = {
      key: `user-${Date.now()}`,
      role: 'user',
      content,
    };
    const assistantPlaceholder: ChatBubble = {
      key: 'assistant-pending',
      role: 'assistant',
      content: t('experience.pendingAnswer'),
    };

    setMessages((previous) => [...previous, userMessage, assistantPlaceholder]);
    setQuery('');
    setSending(true);

    try {
      let streamedSessionId = currentSession?.session_id || '';
      let streamFailed = false;

      try {
        await streamProjectChat(
          activeProjectId,
          {
            session_id: currentSession?.session_id,
            query: content,
            use_memory: true,
            source: 'admin',
            selected_kb_ids: selectedKbIds,
            switches: {
              sensitive_detection: switches.sensitiveDetection,
              retrieval_filter: switches.retrievalFilter,
              retrieval_guard: switches.retrievalFilter,
              knowledge_tree: switches.knowledgeTree,
            },
          },
          {
            onMeta: (meta) => {
              streamedSessionId = meta.session_id;
              applyMeta(meta);
              setMessages((previous) =>
                previous.map((item) =>
                  item.key === 'assistant-pending'
                    ? {
                        ...item,
                        content: '',
                        rewrittenQuery: meta.rewritten_query,
                        traceId: meta.trace_id,
                        usedMemory: meta.use_memory,
                        sources: meta.sources,
                      }
                    : item,
                ),
              );
            },
            onDelta: (chunk) => {
              setMessages((previous) =>
                previous.map((item) =>
                  item.key === 'assistant-pending'
                    ? {
                        ...item,
                        content: `${item.content === t('experience.pendingAnswer') ? '' : item.content}${chunk}`,
                      }
                    : item,
                ),
              );
            },
            onDone: (payload) => {
              streamedSessionId = payload.session_id || streamedSessionId;
              setMessages((previous) =>
                previous.map((item) =>
                  item.key === 'assistant-pending'
                    ? {
                        ...item,
                        key: `assistant-${Date.now()}`,
                        content: item.content || payload.answer || t('experience.noAnswer'),
                        sources: payload.sources,
                        traceId: payload.trace_id,
                      }
                    : item,
                ),
              );
            },
            onError: (errorMessage) => {
              streamFailed = true;
              throw new Error(errorMessage);
            },
          },
        );
      } catch (streamError) {
        streamFailed = true;
        setMessages((previous) => previous.filter((item) => item.key !== 'assistant-pending'));
        await fallbackAsk(activeProjectId, content);
        if (streamError instanceof Error) {
          message.warning(t('experience.streamFallbackWarning', { message: streamError.message }));
        }
      }

      if (!streamFailed && streamedSessionId) {
        await syncSessionAfterReply(activeProjectId, streamedSessionId);
      }
    } catch (error) {
      setMessages((previous) => previous.filter((item) => item.key !== 'assistant-pending'));
      message.error(error instanceof Error ? error.message : t('experience.sendFailed'));
    } finally {
      setSending(false);
    }
  };

  return (
    <AdminPage
      title={t('experience.title')}
      description={t('experience.description', { projectName: activeProject?.company_name ?? t('layout.noProject') })}
      hideHero
    >
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Button onClick={handleStartNewConversation} disabled={!activeProjectId}>
          {t('experience.newConversation')}
        </Button>
      </div>
      {!activeProjectId ? <Alert type="warning" showIcon message={t('experience.warning')} style={{ marginBottom: 16 }} /> : null}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={24}>
          <Card
            title={t('experience.workspaceTitle')}
            extra={
              <Space size={8}>
                <Typography.Text type="secondary">{activeSessionTitle}</Typography.Text>
                {currentSession?.session_id ? <Tag color="processing">{currentSession.session_id}</Tag> : <Tag>{t('experience.notStarted')}</Tag>}
              </Space>
            }
            variant="borderless"
            styles={{
              header: {
                paddingInline: 4,
                borderBottom: 'none',
                background: 'transparent',
              },
              body: { padding: 4 },
            }}
            style={{
              background: 'transparent',
              boxShadow: 'none',
            }}
          >
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <div
                style={{
                  minHeight: 460,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 16,
                  paddingBottom: 8,
                  paddingInline: 4,
                }}
              >
                {messages.length === 0 ? <Empty description={t('experience.emptyConversation')} /> : null}
                {messages.map((item) => {
                  const isUser = item.role === 'user';
                  return (
                    <div key={item.key} style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
                      <div
                        style={{
                          width: 'min(100%, 720px)',
                          maxWidth: '92%',
                          padding: 16,
                          borderRadius: 16,
                          background: isUser ? '#1677ff' : '#fafafa',
                          border: isUser ? 'none' : '1px solid #f0f0f0',
                          boxShadow: isUser ? '0 8px 20px rgba(22, 119, 255, 0.18)' : '0 6px 18px rgba(15, 23, 42, 0.04)',
                        }}
                      >
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: 600,
                            color: isUser ? 'rgba(255,255,255,0.85)' : '#8c8c8c',
                            marginBottom: 8,
                          }}
                        >
                          {isUser ? t('experience.user') : t('experience.assistant')}
                        </div>
                        <div
                          style={{
                            fontSize: 15,
                            lineHeight: 1.75,
                            whiteSpace: 'pre-wrap',
                            color: isUser ? '#fff' : '#1f1f1f',
                          }}
                        >
                          {item.content}
                        </div>
                        {!isUser && item.rewrittenQuery ? (
                          <div style={{ marginTop: 12 }}>
                            <Typography.Text type="secondary">{t('experience.rewrittenQuery', { value: item.rewrittenQuery })}</Typography.Text>
                          </div>
                        ) : null}
                        {!isUser && item.sources?.length ? (
                          <div style={{ marginTop: 14 }}>
                            <div
                              style={{
                                fontSize: 13,
                                fontWeight: 600,
                                color: '#8c8c8c',
                                marginBottom: 10,
                              }}
                            >
                              {t('experience.sourcesTitle')}
                            </div>
                            <div
                              style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 10,
                              }}
                            >
                              {item.sources.map((source, index) => {
                                const matchedBase = knowledgeBases.find((kb) => kb.id === source.kb_id);
                                return (
                                  <div
                                    key={`${item.key}-${source.knowledge_id}`}
                                    style={{
                                      borderRadius: 14,
                                      border: '1px solid #e8edf5',
                                      background: '#fff',
                                      padding: 12,
                                      boxShadow: '0 4px 14px rgba(15, 23, 42, 0.04)',
                                    }}
                                  >
                                    <Space
                                      align="start"
                                      style={{ width: '100%', justifyContent: 'space-between', marginBottom: 6 }}
                                    >
                                      <Space size={8} align="start">
                                        <div
                                          style={{
                                            width: 22,
                                            height: 22,
                                            borderRadius: 999,
                                            background: '#e6f4ff',
                                            color: '#1677ff',
                                            fontSize: 13,
                                            fontWeight: 700,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            flex: '0 0 auto',
                                          }}
                                        >
                                          {index + 1}
                                        </div>
                                        <div>
                                          <Typography.Text strong style={{ color: '#1f1f1f' }}>
                                            {source.title}
                                          </Typography.Text>
                                          <div style={{ marginTop: 6 }}>
                                            <Space wrap size={[6, 6]}>
                                              <Tag color="blue">{matchedBase?.name || t('experience.knowledgeBaseSource')}</Tag>
                                              {typeof source.score === 'number' ? <Tag>{source.score.toFixed(2)}</Tag> : null}
                                            </Space>
                                          </div>
                                        </div>
                                      </Space>
                                    </Space>
                                    <Typography.Paragraph
                                      type="secondary"
                                      style={{
                                        marginBottom: 0,
                                        marginTop: 4,
                                        whiteSpace: 'pre-wrap',
                                      }}
                                    >
                                      {source.snippet || t('experience.sourceSnippetFallback')}
                                    </Typography.Paragraph>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              <Card
                size="small"
                style={{
                  borderRadius: 18,
                  background: 'linear-gradient(180deg, rgba(250,250,250,0.94) 0%, rgba(255,255,255,0.98) 100%)',
                  position: 'sticky',
                  bottom: 0,
                  boxShadow: '0 -12px 30px rgba(15, 23, 42, 0.05)',
                  border: '1px solid #f0f0f0',
                }}
                styles={{ body: { padding: 16 } }}
              >
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  {messages.length === 1 && suggestedQueries.length ? (
                    <div className="admin-chatComposer__suggestions">
                      <Typography.Text type="secondary">{t('experience.recommendedAsk')}</Typography.Text>
                      <Space wrap size={[8, 8]} style={{ width: '100%', marginTop: 10 }}>
                        {suggestedQueries.map((item) => (
                          <Button key={item} size="small" className="admin-appleButton admin-appleButton--chip" onClick={() => void handleSend(item)}>
                            {item}
                          </Button>
                        ))}
                      </Space>
                    </div>
                  ) : null}
                  <Typography.Text strong>{t('experience.followUpTitle')}</Typography.Text>
                  <div className="admin-chatComposer">
                    <Input.TextArea
                      value={query}
                      autoSize={{ minRows: 3, maxRows: 5 }}
                      className="admin-chatComposer__input"
                      placeholder={t('experience.inputPlaceholder')}
                      onChange={(event) => setQuery(event.target.value)}
                      onPressEnter={(event) => {
                        if (!event.shiftKey) {
                          event.preventDefault();
                          void handleSend();
                        }
                      }}
                    />
                  </div>
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Typography.Text type="secondary">
                      {t('experience.footerNote')}
                    </Typography.Text>
                    <Button type="primary" className="admin-appleButton" onClick={() => void handleSend()} loading={sending} disabled={!activeProjectId}>
                      {t('experience.sendQuestion')}
                    </Button>
                  </Space>
                </Space>
              </Card>
            </Space>
          </Card>
        </Col>
      </Row>
    </AdminPage>
  );
}
