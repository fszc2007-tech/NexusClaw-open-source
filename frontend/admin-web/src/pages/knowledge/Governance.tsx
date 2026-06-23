import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Popconfirm, Row, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { TableRowSelection } from 'antd/es/table/interface';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { useI18n } from '@/i18n/useI18n';
import {
  bulkResolveGovernanceConflictTasks,
  bulkResolveGovernanceDedupCandidates,
  bulkResolveGovernanceStaleTasks,
  fetchGovernanceConflictTasks,
  fetchGovernanceDedupCandidates,
  fetchGovernanceSummary,
  fetchGovernanceStaleTasks,
  refreshGovernanceConflictTasks,
  refreshGovernanceDedupCandidates,
  refreshGovernanceStaleTasks,
  resolveGovernanceConflictTask,
  resolveGovernanceDedupCandidate,
  resolveGovernanceStaleTask,
  type GovernanceConflictTaskRecord,
  type GovernanceDedupRecord,
  type GovernanceSummary,
  type GovernanceStaleTaskRecord,
} from '@/services/knowledgeApi';
import { message } from '@/services/notify';

type QueueType = 'duplicate' | 'stale' | 'conflict';

function renderLevel(level: string) {
  const colorMap: Record<string, string> = {
    high: 'error',
    medium: 'warning',
    low: 'default',
  };
  return <Tag color={colorMap[level] || 'default'}>{level}</Tag>;
}

function renderGovernanceStatus(status?: string) {
  const colorMap: Record<string, string> = {
    active: 'success',
    review_pending: 'warning',
    duplicate: 'error',
    superseded: 'default',
    stale: 'error',
    conflict: 'error',
  };
  return <Tag color={colorMap[status || ''] || 'default'}>{status || '-'}</Tag>;
}

function renderPreviewBlock(label: string, value?: string | null) {
  return (
    <Space direction="vertical" size={2}>
      <Typography.Text type="secondary">{label}</Typography.Text>
      <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
        {value || '-'}
      </Typography.Paragraph>
    </Space>
  );
}

export default function KnowledgeGovernancePage() {
  const { activeProject, activeProjectId } = useActiveProject();
  const { t, tList } = useI18n();
  const [queueType, setQueueType] = useState<QueueType>('duplicate');
  const [summary, setSummary] = useState<GovernanceSummary | null>(null);
  const [duplicateRows, setDuplicateRows] = useState<GovernanceDedupRecord[]>([]);
  const [staleRows, setStaleRows] = useState<GovernanceStaleTaskRecord[]>([]);
  const [conflictRows, setConflictRows] = useState<GovernanceConflictTaskRecord[]>([]);
  const [selectedDuplicateIds, setSelectedDuplicateIds] = useState<number[]>([]);
  const [selectedStaleIds, setSelectedStaleIds] = useState<number[]>([]);
  const [selectedConflictIds, setSelectedConflictIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);

  const loadSummary = async () => {
    if (!activeProjectId) {
      setSummary(null);
      return;
    }
    const data = await fetchGovernanceSummary(activeProjectId);
    setSummary(data);
  };

  const loadRows = async (type: QueueType) => {
    if (!activeProjectId) {
      return;
    }
    try {
      setLoading(true);
      await loadSummary();
      if (type === 'duplicate') {
        const data = await fetchGovernanceDedupCandidates(activeProjectId);
        setDuplicateRows(data);
      } else if (type === 'stale') {
        const data = await fetchGovernanceStaleTasks(activeProjectId);
        setStaleRows(data);
      } else {
        const data = await fetchGovernanceConflictTasks(activeProjectId);
        setConflictRows(data);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('knowledgeGovernance.loadError'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRows(queueType);
  }, [activeProjectId, queueType]);

  useEffect(() => {
    setSelectedDuplicateIds([]);
    setSelectedStaleIds([]);
    setSelectedConflictIds([]);
  }, [queueType, activeProjectId]);

  const handleRefresh = async () => {
    if (!activeProjectId) {
      return;
    }
    try {
      setLoading(true);
      if (queueType === 'duplicate') {
        await refreshGovernanceDedupCandidates(activeProjectId);
        message.success(t('knowledgeGovernance.refreshSuccess'));
      } else if (queueType === 'stale') {
        await refreshGovernanceStaleTasks(activeProjectId);
        message.success(t('knowledgeGovernance.staleRefreshSuccess'));
      } else {
        await refreshGovernanceConflictTasks(activeProjectId);
        message.success(t('knowledgeGovernance.conflictRefreshSuccess'));
      }
      await loadRows(queueType);
    } catch (error) {
      const fallbackKey =
        queueType === 'duplicate'
          ? 'knowledgeGovernance.refreshError'
          : queueType === 'stale'
            ? 'knowledgeGovernance.staleRefreshError'
            : 'knowledgeGovernance.conflictRefreshError';
      message.error(error instanceof Error ? error.message : t(fallbackKey));
      setLoading(false);
    }
  };

  const handleResolveDuplicate = async (recordId: number, action: string) => {
    if (!activeProjectId) {
      return;
    }
    try {
      await resolveGovernanceDedupCandidate(activeProjectId, { record_id: recordId, action });
      message.success(t('knowledgeGovernance.resolveSuccess'));
      await loadRows('duplicate');
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('knowledgeGovernance.resolveError'));
    }
  };

  const handleResolveStale = async (taskId: number, action: string) => {
    if (!activeProjectId) {
      return;
    }
    try {
      await resolveGovernanceStaleTask(activeProjectId, {
        task_id: taskId,
        action,
      });
      message.success(t('knowledgeGovernance.staleResolveSuccess'));
      await loadRows('stale');
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('knowledgeGovernance.staleResolveError'));
    }
  };

  const handleResolveConflict = async (taskId: number, action: string) => {
    if (!activeProjectId) {
      return;
    }
    try {
      await resolveGovernanceConflictTask(activeProjectId, {
        task_id: taskId,
        action,
      });
      message.success(t('knowledgeGovernance.conflictResolveSuccess'));
      await loadRows('conflict');
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('knowledgeGovernance.conflictResolveError'));
    }
  };

  const handleBulkResolveDuplicate = async (action: string) => {
    if (!activeProjectId || !selectedDuplicateIds.length) {
      return;
    }
    try {
      await bulkResolveGovernanceDedupCandidates(activeProjectId, {
        record_ids: selectedDuplicateIds,
        action,
      });
      setSelectedDuplicateIds([]);
      message.success(t('knowledgeGovernance.bulkResolveSuccess'));
      await loadRows('duplicate');
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('knowledgeGovernance.bulkResolveError'));
    }
  };

  const handleBulkResolveStale = async (action: string) => {
    if (!activeProjectId || !selectedStaleIds.length) {
      return;
    }
    try {
      await bulkResolveGovernanceStaleTasks(activeProjectId, {
        task_ids: selectedStaleIds,
        action,
      });
      setSelectedStaleIds([]);
      message.success(t('knowledgeGovernance.bulkResolveSuccess'));
      await loadRows('stale');
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('knowledgeGovernance.bulkResolveError'));
    }
  };

  const handleBulkResolveConflict = async (action: string) => {
    if (!activeProjectId || !selectedConflictIds.length) {
      return;
    }
    try {
      await bulkResolveGovernanceConflictTasks(activeProjectId, {
        task_ids: selectedConflictIds,
        action,
      });
      setSelectedConflictIds([]);
      message.success(t('knowledgeGovernance.bulkResolveSuccess'));
      await loadRows('conflict');
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('knowledgeGovernance.bulkResolveError'));
    }
  };

  const duplicateRowSelection = useMemo<TableRowSelection<GovernanceDedupRecord>>(
    () => ({
      selectedRowKeys: selectedDuplicateIds,
      onChange: (keys) => setSelectedDuplicateIds(keys.map((key) => Number(key))),
    }),
    [selectedDuplicateIds],
  );

  const staleRowSelection = useMemo<TableRowSelection<GovernanceStaleTaskRecord>>(
    () => ({
      selectedRowKeys: selectedStaleIds,
      onChange: (keys) => setSelectedStaleIds(keys.map((key) => Number(key))),
    }),
    [selectedStaleIds],
  );

  const conflictRowSelection = useMemo<TableRowSelection<GovernanceConflictTaskRecord>>(
    () => ({
      selectedRowKeys: selectedConflictIds,
      onChange: (keys) => setSelectedConflictIds(keys.map((key) => Number(key))),
    }),
    [selectedConflictIds],
  );

  const summaryCards = useMemo(
    () => [
      {
        key: 'pending_duplicate_count',
        label: t('knowledgeGovernance.summary.pendingDuplicate'),
        value: summary?.pending_duplicate_count ?? 0,
        hint: t('knowledgeGovernance.summary.pendingDuplicateHint'),
      },
      {
        key: 'pending_stale_count',
        label: t('knowledgeGovernance.summary.pendingStale'),
        value: summary?.pending_stale_count ?? 0,
        hint: t('knowledgeGovernance.summary.pendingStaleHint'),
      },
      {
        key: 'pending_conflict_count',
        label: t('knowledgeGovernance.summary.pendingConflict'),
        value: summary?.pending_conflict_count ?? 0,
        hint: t('knowledgeGovernance.summary.pendingConflictHint'),
      },
      {
        key: 'blocked_knowledge_count',
        label: t('knowledgeGovernance.summary.blockedKnowledge'),
        value: summary?.blocked_knowledge_count ?? 0,
        hint: t('knowledgeGovernance.summary.blockedKnowledgeHint'),
      },
      {
        key: 'source_changed_task_count',
        label: t('knowledgeGovernance.summary.sourceChanged'),
        value: summary?.source_changed_task_count ?? 0,
        hint: t('knowledgeGovernance.summary.sourceChangedHint'),
      },
      {
        key: 'active_knowledge_count',
        label: t('knowledgeGovernance.summary.activeKnowledge'),
        value: summary?.active_knowledge_count ?? 0,
        hint: t('knowledgeGovernance.summary.activeKnowledgeHint'),
      },
    ],
    [summary, t],
  );

  const selectedCount =
    queueType === 'duplicate' ? selectedDuplicateIds.length : queueType === 'stale' ? selectedStaleIds.length : selectedConflictIds.length;

  const renderBulkActions = () => {
    if (queueType === 'duplicate') {
      return (
        <Space wrap>
          <Typography.Text type="secondary">
            {t('knowledgeGovernance.bulkSelected', { count: selectedDuplicateIds.length })}
          </Typography.Text>
          <Button size="small" disabled={!selectedDuplicateIds.length} onClick={() => void handleBulkResolveDuplicate('confirm_duplicate')}>
            {t('knowledgeGovernance.actions.confirmDuplicate')}
          </Button>
          <Button size="small" disabled={!selectedDuplicateIds.length} onClick={() => void handleBulkResolveDuplicate('mark_superseded')}>
            {t('knowledgeGovernance.actions.markSuperseded')}
          </Button>
          <Button size="small" disabled={!selectedDuplicateIds.length} onClick={() => void handleBulkResolveDuplicate('reject')}>
            {t('knowledgeGovernance.actions.reject')}
          </Button>
        </Space>
      );
    }
    if (queueType === 'stale') {
      return (
        <Space wrap>
          <Typography.Text type="secondary">
            {t('knowledgeGovernance.bulkSelected', { count: selectedStaleIds.length })}
          </Typography.Text>
          <Button size="small" disabled={!selectedStaleIds.length} onClick={() => void handleBulkResolveStale('mark_stale')}>
            {t('knowledgeGovernance.actions.markStale')}
          </Button>
          <Button size="small" disabled={!selectedStaleIds.length} onClick={() => void handleBulkResolveStale('revalidate')}>
            {t('knowledgeGovernance.actions.revalidate')}
          </Button>
        </Space>
      );
    }
    return (
      <Space wrap>
        <Typography.Text type="secondary">
          {t('knowledgeGovernance.bulkSelected', { count: selectedConflictIds.length })}
        </Typography.Text>
        <Button size="small" disabled={!selectedConflictIds.length} onClick={() => void handleBulkResolveConflict('mark_conflict')}>
          {t('knowledgeGovernance.actions.markConflict')}
        </Button>
        <Button size="small" disabled={!selectedConflictIds.length} onClick={() => void handleBulkResolveConflict('reject')}>
          {t('knowledgeGovernance.actions.reject')}
        </Button>
      </Space>
    );
  };

  const duplicateColumns = useMemo<ColumnsType<GovernanceDedupRecord>>(
    () => [
      {
        title: t('knowledgeGovernance.columns.newKnowledge'),
        dataIndex: 'new_knowledge',
        key: 'new_knowledge',
        render: (value: GovernanceDedupRecord['new_knowledge']) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{value.title}</Typography.Text>
            <Typography.Text type="secondary">
              #{value.id} · KB {value.kb_id} · {value.document_name || '-'}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: t('knowledgeGovernance.columns.oldKnowledge'),
        dataIndex: 'old_knowledge',
        key: 'old_knowledge',
        render: (value: GovernanceDedupRecord['old_knowledge']) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{value.title}</Typography.Text>
            <Typography.Text type="secondary">
              #{value.id} · KB {value.kb_id} · {value.document_name || '-'}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: t('knowledgeGovernance.columns.score'),
        dataIndex: 'score',
        key: 'score',
        width: 100,
      },
      {
        title: t('knowledgeGovernance.columns.level'),
        dataIndex: 'dedup_level',
        key: 'dedup_level',
        width: 100,
        render: (value: string) => renderLevel(value),
      },
      {
        title: t('knowledgeGovernance.columns.reason'),
        dataIndex: 'reason',
        key: 'reason',
        render: (value: string[]) => (
          <Space wrap>
            {(value || []).map((item) => (
              <Tag key={item}>{item}</Tag>
            ))}
          </Space>
        ),
      },
      {
        title: t('knowledgeGovernance.columns.createdAt'),
        dataIndex: 'created_at',
        key: 'created_at',
        width: 180,
        render: (value?: string | null) => (value ? new Date(value).toLocaleString() : '-'),
      },
      {
        title: t('knowledgeGovernance.columns.actions'),
        key: 'actions',
        width: 240,
        render: (_, record) => (
          <Space wrap>
            <Popconfirm
              title={t('knowledgeGovernance.confirm.confirmDuplicate')}
              onConfirm={() => void handleResolveDuplicate(record.id, 'confirm_duplicate')}
            >
              <Button type="link" size="small">
                {t('knowledgeGovernance.actions.confirmDuplicate')}
              </Button>
            </Popconfirm>
            <Popconfirm
              title={t('knowledgeGovernance.confirm.markSuperseded')}
              onConfirm={() => void handleResolveDuplicate(record.id, 'mark_superseded')}
            >
              <Button type="link" size="small">
                {t('knowledgeGovernance.actions.markSuperseded')}
              </Button>
            </Popconfirm>
            <Popconfirm title={t('knowledgeGovernance.confirm.reject')} onConfirm={() => void handleResolveDuplicate(record.id, 'reject')}>
              <Button type="link" size="small">
                {t('knowledgeGovernance.actions.reject')}
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [t],
  );

  const staleColumns = useMemo<ColumnsType<GovernanceStaleTaskRecord>>(
    () => [
      {
        title: t('knowledgeGovernance.columns.knowledge'),
        dataIndex: 'knowledge',
        key: 'knowledge',
        render: (value: GovernanceStaleTaskRecord['knowledge']) => (
          <Space direction="vertical" size={0}>
            <Space wrap>
              <Typography.Text strong>{value.title}</Typography.Text>
              {renderGovernanceStatus(value.governance_status)}
            </Space>
            <Typography.Text type="secondary">
              #{value.id} · KB {value.kb_id} · {value.document_name || '-'}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: t('knowledgeGovernance.columns.source'),
        dataIndex: 'knowledge',
        key: 'source',
        render: (value: GovernanceStaleTaskRecord['knowledge']) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{value.source_org || '-'}</Typography.Text>
            <Typography.Text type="secondary">{value.source_url || '-'}</Typography.Text>
          </Space>
        ),
      },
      {
        title: t('knowledgeGovernance.columns.owner'),
        dataIndex: 'knowledge',
        key: 'owner',
        width: 100,
        render: (value: GovernanceStaleTaskRecord['knowledge']) => value.owner_user_id || '-',
      },
      {
        title: t('knowledgeGovernance.columns.taskReason'),
        dataIndex: 'reason',
        key: 'reason',
      },
      {
        title: t('knowledgeGovernance.columns.preview'),
        dataIndex: 'payload',
        key: 'payload',
        width: 360,
        render: (value: GovernanceStaleTaskRecord['payload'], record) => {
          const previousPreview = typeof value?.previous_preview === 'string' ? value.previous_preview : record.knowledge.source_snapshot_preview;
          const currentPreview = typeof value?.current_preview === 'string' ? value.current_preview : undefined;
          if (!previousPreview && !currentPreview) {
            return '-';
          }
          return (
            <Space direction="vertical" size={8}>
              {renderPreviewBlock(t('knowledgeGovernance.preview.previous'), previousPreview)}
              {currentPreview ? renderPreviewBlock(t('knowledgeGovernance.preview.current'), currentPreview) : null}
            </Space>
          );
        },
      },
      {
        title: t('knowledgeGovernance.columns.reviewDueAt'),
        dataIndex: ['knowledge', 'review_due_at'],
        key: 'review_due_at',
        width: 180,
        render: (value?: string | null) => (value ? new Date(value).toLocaleString() : '-'),
      },
      {
        title: t('knowledgeGovernance.columns.lastVerifiedAt'),
        dataIndex: ['knowledge', 'last_verified_at'],
        key: 'last_verified_at',
        width: 180,
        render: (value?: string | null) => (value ? new Date(value).toLocaleString() : '-'),
      },
      {
        title: t('knowledgeGovernance.columns.sourceLastCheckedAt'),
        dataIndex: ['knowledge', 'source_last_checked_at'],
        key: 'source_last_checked_at',
        width: 180,
        render: (value?: string | null) => (value ? new Date(value).toLocaleString() : '-'),
      },
      {
        title: t('knowledgeGovernance.columns.actions'),
        key: 'actions',
        width: 220,
        render: (_, record) => (
          <Space wrap>
            <Popconfirm title={t('knowledgeGovernance.confirm.markStale')} onConfirm={() => void handleResolveStale(record.id, 'mark_stale')}>
              <Button type="link" size="small">
                {t('knowledgeGovernance.actions.markStale')}
              </Button>
            </Popconfirm>
            <Popconfirm title={t('knowledgeGovernance.confirm.revalidate')} onConfirm={() => void handleResolveStale(record.id, 'revalidate')}>
              <Button type="link" size="small">
                {t('knowledgeGovernance.actions.revalidate')}
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [t],
  );

  const conflictColumns = useMemo<ColumnsType<GovernanceConflictTaskRecord>>(
    () => [
      {
        title: t('knowledgeGovernance.columns.knowledge'),
        dataIndex: 'knowledge',
        key: 'knowledge',
        render: (value: GovernanceConflictTaskRecord['knowledge']) => (
          <Space direction="vertical" size={0}>
            <Space wrap>
              <Typography.Text strong>{value.title}</Typography.Text>
              {renderGovernanceStatus(value.governance_status)}
            </Space>
            <Typography.Text type="secondary">
              #{value.id} · KB {value.kb_id} · {value.document_name || '-'}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: t('knowledgeGovernance.columns.counterpart'),
        dataIndex: 'counterpart',
        key: 'counterpart',
        render: (value: GovernanceConflictTaskRecord['counterpart']) =>
          value ? (
            <Space direction="vertical" size={0}>
              <Space wrap>
                <Typography.Text>{value.title}</Typography.Text>
                {renderGovernanceStatus(value.governance_status)}
              </Space>
              <Typography.Text type="secondary">
                #{value.id} · KB {value.kb_id} · {value.document_name || '-'}
              </Typography.Text>
            </Space>
          ) : (
            '-'
          ),
      },
      {
        title: t('knowledgeGovernance.columns.taskReason'),
        dataIndex: 'reason',
        key: 'reason',
      },
      {
        title: t('knowledgeGovernance.columns.preview'),
        dataIndex: 'payload',
        key: 'payload',
        width: 360,
        render: (value: GovernanceConflictTaskRecord['payload']) => (
          <Space direction="vertical" size={8}>
            {renderPreviewBlock(
              t('knowledgeGovernance.preview.current'),
              typeof value?.current_preview === 'string' ? value.current_preview : undefined,
            )}
            {renderPreviewBlock(
              t('knowledgeGovernance.preview.counterpart'),
              typeof value?.counterpart_preview === 'string' ? value.counterpart_preview : undefined,
            )}
          </Space>
        ),
      },
      {
        title: t('knowledgeGovernance.columns.createdAt'),
        dataIndex: 'created_at',
        key: 'created_at',
        width: 180,
        render: (value?: string | null) => (value ? new Date(value).toLocaleString() : '-'),
      },
      {
        title: t('knowledgeGovernance.columns.actions'),
        key: 'actions',
        width: 220,
        render: (_, record) => (
          <Space wrap>
            <Popconfirm title={t('knowledgeGovernance.confirm.markConflict')} onConfirm={() => void handleResolveConflict(record.id, 'mark_conflict')}>
              <Button type="link" size="small">
                {t('knowledgeGovernance.actions.markConflict')}
              </Button>
            </Popconfirm>
            <Popconfirm title={t('knowledgeGovernance.confirm.rejectConflict')} onConfirm={() => void handleResolveConflict(record.id, 'reject')}>
              <Button type="link" size="small">
                {t('knowledgeGovernance.actions.reject')}
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [t],
  );

  return (
    <AdminPage
      title={t('knowledgeGovernance.title')}
      description={t('knowledgeGovernance.description', { projectName: activeProject?.company_name ?? t('layout.noProject') })}
      tags={tList('knowledgeGovernance.tags')}
      extra={
        <Space>
          <Button type={queueType === 'duplicate' ? 'primary' : 'default'} onClick={() => setQueueType('duplicate')}>
            {t('knowledgeGovernance.queue.duplicate')}
          </Button>
          <Button type={queueType === 'stale' ? 'primary' : 'default'} onClick={() => setQueueType('stale')}>
            {t('knowledgeGovernance.queue.stale')}
          </Button>
          <Button type={queueType === 'conflict' ? 'primary' : 'default'} onClick={() => setQueueType('conflict')}>
            {t('knowledgeGovernance.queue.conflict')}
          </Button>
          <Button onClick={() => void handleRefresh()} disabled={!activeProjectId} loading={loading}>
            {t('knowledgeGovernance.refreshButton')}
          </Button>
        </Space>
      }
    >
      {!activeProjectId ? (
        <Alert type="warning" showIcon message={t('knowledgeGovernance.warning')} style={{ marginBottom: 16 }} />
      ) : null}
      <Row gutter={[16, 16]}>
        {summaryCards.map((item) => (
          <Col xs={24} sm={12} xl={8} key={item.key}>
            <Card className="admin-listPanel">
              <div className="admin-detailStat">
                <span className="admin-detailStat__label">{item.label}</span>
                <Typography.Title level={3} className="admin-detailStat__value">
                  {item.value}
                </Typography.Title>
                <span className="admin-detailStat__hint">{item.hint}</span>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
      <Card
        className="admin-listPanel"
        title={t('knowledgeGovernance.queueTitle')}
        extra={
          <Space wrap>
            <Typography.Text type="secondary">
              {t('knowledgeGovernance.currentQueue')}: {t(`knowledgeGovernance.queue.${queueType}`)}
            </Typography.Text>
            <Typography.Text type="secondary">
              {t('knowledgeGovernance.bulkSelected', { count: selectedCount })}
            </Typography.Text>
          </Space>
        }
      >
        <div style={{ marginBottom: 16 }}>{renderBulkActions()}</div>
        {queueType === 'duplicate' ? (
          <Table
            rowKey="id"
            loading={loading}
            columns={duplicateColumns}
            dataSource={duplicateRows}
            rowSelection={duplicateRowSelection}
            pagination={false}
            locale={{ emptyText: t('knowledgeGovernance.empty') }}
          />
        ) : queueType === 'stale' ? (
          <Table
            rowKey="id"
            loading={loading}
            columns={staleColumns}
            dataSource={staleRows}
            rowSelection={staleRowSelection}
            pagination={false}
            locale={{ emptyText: t('knowledgeGovernance.emptyStale') }}
          />
        ) : (
          <Table
            rowKey="id"
            loading={loading}
            columns={conflictColumns}
            dataSource={conflictRows}
            rowSelection={conflictRowSelection}
            pagination={false}
            locale={{ emptyText: t('knowledgeGovernance.emptyConflict') }}
          />
        )}
      </Card>
    </AdminPage>
  );
}
