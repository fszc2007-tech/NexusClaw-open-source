import { Alert, Button, Card, Checkbox, Input, List, Space, Spin, Tag, Typography, Upload } from 'antd';
import { message } from '@/services/notify';
import type { UploadProps } from 'antd';
import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { isAdminDemoMode } from '@/services/client';
import {
  askDocumentQa,
  fetchDocumentQaFiles,
  fetchDocumentQaPreview,
  uploadDocumentQaFile,
  type DocumentQaBlock,
  type DocumentQaCitation,
  type DocumentQaFileRecord,
  type DocumentQaPreview,
} from '@/services/documentQaApi';

import './DocumentQA.css';

type DocumentQaTurn = {
  id: string;
  query: string;
  answer: string;
  citations: DocumentQaCitation[];
  traceId?: string | null;
  modelName?: string | null;
};

type WorkspaceEmptyProps = {
  icon: ReactNode;
  title: string;
  description: string;
  footer?: ReactNode;
};

function getParseStatusTag(status: string, parseError?: string | null) {
  if (status === 'success' || status === 'completed') {
    return <Tag color="success">解析成功</Tag>;
  }
  if (status === 'failed') {
    return <Tag color="error">{parseError ? '解析失败' : '失败'}</Tag>;
  }
  if (status === 'processing' || status === 'uploaded') {
    return <Tag color="processing">解析中</Tag>;
  }
  return <Tag>{status || '未知'}</Tag>;
}

function getChunkStatusTag(status: string) {
  if (status === 'completed') {
    return <Tag color="success">已就绪</Tag>;
  }
  if (status === 'processing') {
    return <Tag color="processing">处理中</Tag>;
  }
  if (status === 'failed') {
    return <Tag color="error">失败</Tag>;
  }
  return <Tag>{status || '未开始'}</Tag>;
}

function buildPreviewBlocks(preview: DocumentQaPreview | null): DocumentQaBlock[] {
  if (!preview) {
    return [];
  }
  if (preview.blocks?.length) {
    return preview.blocks.filter((item) => item.text?.trim());
  }
  return (preview.content || '')
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((text, index) => ({
      block_id: `fallback-${index + 1}`,
      block_type: 'paragraph',
      text,
      order_no: index + 1,
    }));
}

function renderHighlightedText(text: string, citations: DocumentQaCitation[]) {
  const target = citations
    .map((item) => item.quote?.trim())
    .find((quote) => quote && quote.length >= 4 && text.includes(quote));

  if (!target) {
    return text;
  }

  const startIndex = text.indexOf(target);
  const endIndex = startIndex + target.length;
  return (
    <>
      {text.slice(0, startIndex)}
      <mark style={{ background: 'rgba(255, 224, 138, 0.88)', padding: '0 4px', borderRadius: 6 }}>{target}</mark>
      {text.slice(endIndex)}
    </>
  );
}

function formatFileSize(fileSize: number) {
  if (!Number.isFinite(fileSize) || fileSize <= 0) {
    return '--';
  }
  if (fileSize < 1024) {
    return `${fileSize} B`;
  }
  if (fileSize < 1024 * 1024) {
    return `${(fileSize / 1024).toFixed(1)} KB`;
  }
  if (fileSize < 1024 * 1024 * 1024) {
    return `${(fileSize / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${(fileSize / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return '刚刚上传';
  }
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function WorkspaceEmpty({ icon, title, description, footer }: WorkspaceEmptyProps) {
  return (
    <div className="doc-qa-empty">
      <div className="doc-qa-empty__icon">{icon}</div>
      <Typography.Title level={5} className="doc-qa-empty__title">
        {title}
      </Typography.Title>
      <Typography.Paragraph className="doc-qa-empty__description">{description}</Typography.Paragraph>
      {footer ? <div className="doc-qa-empty__footer">{footer}</div> : null}
    </div>
  );
}

export default function DocumentQAPage() {
  const { activeProject, activeProjectId } = useActiveProject();
  const [files, setFiles] = useState<DocumentQaFileRecord[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [preview, setPreview] = useState<DocumentQaPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [overwriteSameName, setOverwriteSameName] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [turns, setTurns] = useState<DocumentQaTurn[]>([]);
  const [highlightedCitations, setHighlightedCitations] = useState<DocumentQaCitation[]>([]);
  const [activeCitationBlockId, setActiveCitationBlockId] = useState<string | null>(null);
  const previewBlockRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const previewBlocks = useMemo(() => buildPreviewBlocks(preview), [preview]);
  const selectedFile = useMemo(
    () => files.find((item) => item.id === selectedFileId) ?? null,
    [files, selectedFileId],
  );
  const suggestedQuestions = useMemo(
    () => ['请总结这份文档的核心结论', '列出其中提到的办理材料或条件', '有哪些时间节点、限制或风险提醒'],
    [],
  );
  const fileSummary = useMemo(() => {
    const ready = files.filter(
      (item) =>
        ['success', 'completed'].includes(item.parse_status) &&
        !['processing', 'failed'].includes(item.chunk_status),
    ).length;
    const processing = files.filter((item) =>
      ['uploaded', 'processing', 'pending'].includes(item.parse_status) || item.chunk_status === 'processing',
    ).length;
    const failed = files.filter((item) => item.parse_status === 'failed' || item.chunk_status === 'failed').length;

    return { ready, processing, failed };
  }, [files]);
  const previewMeta = useMemo(
    () =>
      [
        selectedFile ? formatFileSize(selectedFile.file_size) : null,
        preview?.parser_name ?? null,
        previewBlocks.length > 0 ? `${previewBlocks.length} 个片段` : null,
        highlightedCitations.length > 0 ? `${highlightedCitations.length} 处命中` : null,
      ].filter(Boolean),
    [highlightedCitations.length, preview?.parser_name, previewBlocks.length, selectedFile],
  );

  const loadFiles = async (projectId: number) => {
    try {
      setFilesLoading(true);
      const result = await fetchDocumentQaFiles(projectId);
      setFiles(result);
      setSelectedFileId((current) => {
        if (current && result.some((item) => item.id === current)) {
          return current;
        }
        return result[0]?.id ?? null;
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : '文档列表加载失败');
      setFiles([]);
      setSelectedFileId(null);
    } finally {
      setFilesLoading(false);
    }
  };

  const loadPreview = async (projectId: number, fileId: number) => {
    try {
      setPreviewLoading(true);
      setPreviewError(null);
      const result = await fetchDocumentQaPreview(projectId, fileId);
      setPreview(result);
    } catch (error) {
      const nextError = error instanceof Error ? error.message : '文档预览加载失败';
      setPreview(null);
      setPreviewError(nextError);
    } finally {
      setPreviewLoading(false);
    }
  };

  useEffect(() => {
    setFiles([]);
    setPreview(null);
    setPreviewError(null);
    setSelectedFileId(null);
    setTurns([]);
    setHighlightedCitations([]);
    setQuestion('');
    setActiveCitationBlockId(null);

    if (!activeProjectId) {
      return;
    }

    void loadFiles(activeProjectId);
  }, [activeProjectId]);

  useEffect(() => {
    if (!activeProjectId || !selectedFileId) {
      setPreview(null);
      setPreviewError(null);
      return;
    }

    setTurns([]);
    setHighlightedCitations([]);
    setQuestion('');
    setActiveCitationBlockId(null);
    void loadPreview(activeProjectId, selectedFileId);
  }, [activeProjectId, selectedFileId]);

  useEffect(() => {
    const hasPending = files.some((item) => ['uploaded', 'processing', 'pending'].includes(item.parse_status));
    if (!activeProjectId || !hasPending) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadFiles(activeProjectId);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [activeProjectId, files]);

  useEffect(() => {
    if (!activeCitationBlockId) {
      return;
    }
    previewBlockRefs.current[activeCitationBlockId]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [activeCitationBlockId]);

  const handleUpload: UploadProps['customRequest'] = async (options) => {
    if (!activeProjectId) {
      message.warning('请先选择项目');
      return;
    }

    const file = options.file as File;
    try {
      setUploading(true);
      const result = await uploadDocumentQaFile(activeProjectId, file, overwriteSameName);
      options.onSuccess?.(result);
      message.success(`已上传 ${result.file_name}`);
      await loadFiles(activeProjectId);
      setSelectedFileId(result.id);
    } catch (error) {
      const nextError = error instanceof Error ? error.message : '上传失败';
      options.onError?.(new Error(nextError));
      message.error(nextError);
    } finally {
      setUploading(false);
    }
  };

  const handleAsk = async () => {
    if (!activeProjectId || !selectedFileId) {
      message.warning('请先选择一份文档');
      return;
    }

    const nextQuestion = question.trim();
    if (!nextQuestion) {
      message.warning('请输入问题');
      return;
    }

    try {
      setAsking(true);
      const result = await askDocumentQa(activeProjectId, {
        file_id: selectedFileId,
        query: nextQuestion,
      });
      const nextTurn: DocumentQaTurn = {
        id: `${Date.now()}`,
        query: nextQuestion,
        answer: result.answer,
        citations: result.citations || [],
        traceId: result.trace_id,
        modelName: result.model_name,
      };
      setTurns((current) => [nextTurn, ...current]);
      setHighlightedCitations(result.citations || []);
      setQuestion('');
      setActiveCitationBlockId(result.citations?.[0]?.block_id || null);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '文档问答失败');
    } finally {
      setAsking(false);
    }
  };

  return (
    <AdminPage
      title="体验广场 · 文档问答"
      description="把上传、定位、追问收拢到同一块文档工作台里，围绕单篇文档完成解析、阅读和引用式问答。"
      tags={['真实接口', '单文档问答', '原文定位']}
      extra={
        activeProject ? (
          <div className="doc-qa-hero__project">
            <span className="doc-qa-hero__label">当前项目</span>
            <strong className="doc-qa-hero__name">{activeProject.company_name}</strong>
          </div>
        ) : null
      }
    >
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {isAdminDemoMode() ? (
          <Alert
            type="warning"
            showIcon
            message="当前页面已切到真实接口模式"
            description="即使工作台其它页面仍在演示数据模式，这里也只读取真实接口。若接口不可用，请确认后端服务已经启动。"
          />
        ) : null}

        {!activeProjectId ? (
          <Alert type="info" showIcon message="请先在右上角选择项目，再进入文档问答。" />
        ) : (
          <div className="doc-qa">
            <div className="doc-qa__sidebar">
              <Card className="doc-qa__panel doc-qa__panel--upload">
                <div className="doc-qa__panel-head">
                  <div>
                    <div className="doc-qa__eyebrow">Document Intake</div>
                    <Typography.Title level={4} className="doc-qa__panel-title">
                      上传与解析控制台
                    </Typography.Title>
                    <Typography.Paragraph className="doc-qa__panel-description">
                      先把文档接入系统，再从可问答的文档里挑一份进入深读。
                    </Typography.Paragraph>
                  </div>
                  <Checkbox
                    checked={overwriteSameName}
                    onChange={(event) => setOverwriteSameName(event.target.checked)}
                    className="doc-qa__overwrite"
                  >
                    覆盖同名文件
                  </Checkbox>
                </div>

                <div className="doc-qa__metrics">
                  <div className="doc-qa__metric">
                    <span className="doc-qa__metric-label">文档总数</span>
                    <strong className="doc-qa__metric-value">{files.length}</strong>
                  </div>
                  <div className="doc-qa__metric">
                    <span className="doc-qa__metric-label">可问答</span>
                    <strong className="doc-qa__metric-value">{fileSummary.ready}</strong>
                  </div>
                  <div className="doc-qa__metric">
                    <span className="doc-qa__metric-label">处理中</span>
                    <strong className="doc-qa__metric-value">{fileSummary.processing}</strong>
                  </div>
                  <div className="doc-qa__metric">
                    <span className="doc-qa__metric-label">异常</span>
                    <strong className="doc-qa__metric-value">{fileSummary.failed}</strong>
                  </div>
                </div>

                <Upload.Dragger
                  className="doc-qa__uploader"
                  accept=".pdf,.doc,.docx,.txt,.md,.csv,.html,.htm,.xlsx,.xlsm,.pptx,.pptm,.png,.jpg,.jpeg,.webp"
                  customRequest={handleUpload}
                  showUploadList={false}
                  disabled={!activeProjectId || uploading}
                >
                  <div className="doc-qa__uploader-badge">
                    DOC
                  </div>
                  <Typography.Title level={4} className="doc-qa__uploader-title">
                    {uploading ? '正在上传与建档' : '拖拽上传文档'}
                  </Typography.Title>
                  <Typography.Paragraph className="doc-qa__uploader-description">
                    适合 PDF、DOCX、TXT、Markdown 等已接入解析格式，上传后会自动刷新解析状态。
                  </Typography.Paragraph>
                  <div className="doc-qa__uploader-note">点击选择文件，或直接拖到这里</div>
                </Upload.Dragger>
              </Card>

              <Card className="doc-qa__panel">
                <div className="doc-qa__panel-head">
                  <div>
                    <div className="doc-qa__eyebrow">Library Shelf</div>
                    <Typography.Title level={4} className="doc-qa__panel-title">
                      文档列表
                    </Typography.Title>
                    <Typography.Paragraph className="doc-qa__panel-description">
                      选择一份文档后，右侧会同步切换原文预览与问答上下文。
                    </Typography.Paragraph>
                  </div>
                  <div className="doc-qa__panel-chip">{filesLoading ? <Spin size="small" /> : `${files.length} 份`}</div>
                </div>

                {files.length === 0 ? (
                  <WorkspaceEmpty
                    icon="DOC"
                    title="还没有可浏览的文档"
                    description="先上传第一份材料，解析完成后这里会显示文档名称、状态和更新时间。"
                  />
                ) : (
                  <div className="doc-qa__file-list">
                    {files.map((record) => {
                      const isSelected = selectedFileId === record.id;
                      return (
                        <button
                          key={record.id}
                          type="button"
                          className={`doc-qa__file-item${isSelected ? ' is-active' : ''}`}
                          onClick={() => setSelectedFileId(record.id)}
                        >
                          <div className="doc-qa__file-header">
                            <div>
                              <div className="doc-qa__file-name">{record.file_name}</div>
                              <div className="doc-qa__file-meta">
                                {formatDateTime(record.updated_at)} · {formatFileSize(record.file_size)}
                              </div>
                            </div>
                            {isSelected ? <div className="doc-qa__file-active-dot" /> : null}
                          </div>
                          <Space wrap size={[8, 8]} className="doc-qa__file-tags">
                            {getParseStatusTag(record.parse_status, record.parse_error)}
                            {getChunkStatusTag(record.chunk_status)}
                          </Space>
                        </button>
                      );
                    })}
                  </div>
                )}
              </Card>
            </div>

            <div className="doc-qa__content">
              <Card className="doc-qa__panel">
                <div className="doc-qa__panel-head">
                  <div>
                    <div className="doc-qa__eyebrow">Reading Surface</div>
                    <Typography.Title level={4} className="doc-qa__panel-title">
                      原文预览与定位
                    </Typography.Title>
                    <Typography.Paragraph className="doc-qa__panel-description">
                      命中引用会在原文片段中高亮，点击回答下方引用即可跳转到对应位置。
                    </Typography.Paragraph>
                  </div>
                  <Space wrap size={[8, 8]} className="doc-qa__meta-list">
                    {selectedFile ? <Tag color="blue">{selectedFile.file_name}</Tag> : null}
                    {previewMeta.map((item) => (
                      <Tag key={String(item)}>{item}</Tag>
                    ))}
                  </Space>
                </div>

                <div className="doc-qa__preview-surface">
                  {previewLoading ? (
                    <div className="doc-qa__loading">
                      <Spin />
                    </div>
                  ) : previewError ? (
                    <Alert type="error" showIcon message={previewError} />
                  ) : !selectedFileId ? (
                    <WorkspaceEmpty
                      icon="RAW"
                      title="等待选择一份文档"
                      description="从左侧文档列表选中目标文件后，这里会展开片段化预览，并支持引用定位。"
                    />
                  ) : previewBlocks.length === 0 ? (
                    <WorkspaceEmpty
                      icon="ERR"
                      title="当前文档暂无可展示预览"
                      description="解析可能尚未完成，或文档暂时没有可渲染的块级内容。"
                    />
                  ) : (
                    <div className="doc-qa__preview-scroll">
                      <div className="doc-qa__preview-stack">
                        {previewBlocks.map((block) => {
                          const citationsForRender = highlightedCitations.filter(
                            (item) =>
                              item.block_id === block.block_id ||
                              (item.quote && item.quote.length >= 4 && block.text.includes(item.quote)),
                          );
                          const isActive = activeCitationBlockId === block.block_id;
                          const labelParts = [
                            block.page_no ? `P${block.page_no}` : null,
                            block.sheet_name ? String(block.sheet_name) : null,
                            block.slide_no ? `Slide ${block.slide_no}` : null,
                          ].filter(Boolean);

                          return (
                            <div
                              key={block.block_id}
                              ref={(node) => {
                                previewBlockRefs.current[block.block_id] = node;
                              }}
                              className={`doc-qa__preview-block${isActive ? ' is-active' : ''}${
                                !isActive && citationsForRender.length > 0 ? ' is-hit' : ''
                              }`}
                            >
                              <div className="doc-qa__preview-block-head">
                                <div className="doc-qa__preview-block-index">#{block.order_no}</div>
                                <Space wrap size={[8, 8]}>
                                  <Tag>{block.block_type}</Tag>
                                  {labelParts.length > 0 ? <Tag color="blue">{labelParts.join(' · ')}</Tag> : null}
                                  {block.section_title ? <Tag color="purple">{block.section_title}</Tag> : null}
                                </Space>
                              </div>
                              <Typography.Paragraph className="doc-qa__preview-block-text">
                                {renderHighlightedText(block.text, citationsForRender)}
                              </Typography.Paragraph>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </Card>

              <Card className="doc-qa__panel">
                <div className="doc-qa__panel-head">
                  <div>
                    <div className="doc-qa__eyebrow">Grounded Answering</div>
                    <Typography.Title level={4} className="doc-qa__panel-title">
                      文档问答区
                    </Typography.Title>
                    <Typography.Paragraph className="doc-qa__panel-description">
                      所有回答都只围绕当前选中文档生成，并附带可回跳的引用片段。
                    </Typography.Paragraph>
                  </div>
                  <div className="doc-qa__ask-summary">
                    <div className="doc-qa__panel-chip">{turns.length} 轮提问</div>
                    <div className="doc-qa__panel-chip">{highlightedCitations.length} 处高亮</div>
                  </div>
                </div>

                <div className="doc-qa__conversation-shell">
                  <div className="doc-qa__conversation">
                    {turns.length === 0 ? (
                      <WorkspaceEmpty
                        icon="QA"
                        title="先问一个与文档直接相关的问题"
                        description="例如总结重点、提取办理条件、确认材料清单，系统会把回答和命中原文一起呈现。"
                        footer={
                          <div className="doc-qa__suggestions">
                            {suggestedQuestions.map((item) => (
                              <Button key={item} className="doc-qa__suggestion admin-appleButton admin-appleButton--chip" onClick={() => setQuestion(item)}>
                                {item}
                              </Button>
                            ))}
                          </div>
                        }
                      />
                    ) : (
                      <List
                        dataSource={turns}
                        renderItem={(turn) => (
                          <List.Item className="doc-qa__turn">
                            <div className="doc-qa__question-card">
                              <div className="doc-qa__bubble-label">Question</div>
                              <Typography.Paragraph className="doc-qa__question-text">{turn.query}</Typography.Paragraph>
                            </div>
                            <div className="doc-qa__answer-card">
                              <div className="doc-qa__bubble-label doc-qa__bubble-label--answer">Answer</div>
                              <Typography.Paragraph className="doc-qa__answer-text">{turn.answer}</Typography.Paragraph>
                              {turn.citations.length > 0 ? (
                                <div className="doc-qa__citation-list">
                                  {turn.citations.map((citation, index) => (
                                    <Button
                                      key={`${turn.id}-${citation.block_id || index}`}
                                      size="small"
                                      className="doc-qa__citation admin-appleButton admin-appleButton--chip"
                                      onClick={() => {
                                        setHighlightedCitations(turn.citations);
                                        setActiveCitationBlockId(citation.block_id || null);
                                      }}
                                    >
                                      {citation.page_no ? `P${citation.page_no}` : `命中 ${index + 1}`}：
                                      {citation.quote.slice(0, 24)}
                                    </Button>
                                  ))}
                                </div>
                              ) : null}
                              {turn.traceId || turn.modelName ? (
                                <Space wrap size={[8, 8]}>
                                  {turn.modelName ? (
                                    <Tag color="blue">
                                      {turn.modelName}
                                    </Tag>
                                  ) : null}
                                  {turn.traceId ? <Tag>trace: {turn.traceId}</Tag> : null}
                                </Space>
                              ) : null}
                            </div>
                          </List.Item>
                        )}
                      />
                    )}
                  </div>

                  <div className="doc-qa__composer">
                    <div className="doc-qa__composer-head">
                      <div>
                        <div className="doc-qa__composer-title">提问框</div>
                        <div className="doc-qa__composer-subtitle">
                          {selectedFile ? `当前文档：${selectedFile.file_name}` : '请先从左侧选择一份文档'}
                        </div>
                      </div>
                    </div>
                    <Input.TextArea
                      value={question}
                      onChange={(event) => setQuestion(event.target.value)}
                      autoSize={{ minRows: 4, maxRows: 7 }}
                      placeholder={selectedFile ? `针对《${selectedFile.file_name}》输入问题` : '请先选择文档'}
                      disabled={!selectedFileId || asking}
                      onPressEnter={(event) => {
                        if (!event.shiftKey) {
                          event.preventDefault();
                          void handleAsk();
                        }
                      }}
                    />
                    <div className="doc-qa__composer-footer">
                      <Typography.Text type="secondary">
                        当前回答仅基于所选文档，不会混入其它文档内容。
                      </Typography.Text>
                      <Button type="primary" className="admin-appleButton" onClick={() => void handleAsk()} loading={asking} disabled={!selectedFileId}>
                        提交问题
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )}
      </Space>
    </AdminPage>
  );
}
