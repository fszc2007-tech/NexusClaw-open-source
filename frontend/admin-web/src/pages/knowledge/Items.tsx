import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Popconfirm, Row, Space, Statistic, Table, Tag, Typography } from 'antd';
import { message } from '@/services/notify';
import { Link, useParams } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import {
  deleteKnowledgeItem,
  fetchKnowledgeBaseDashboard,
  fetchKnowledgeItems,
  publishKnowledgeItem,
  type KnowledgeItemRecord,
} from '@/services/knowledgeApi';

function renderStatusTag(status: string) {
  const colorMap: Record<string, string> = {
    active: 'success',
    editing: 'processing',
    publishing: 'warning',
    publish_failed: 'error',
    offline: 'default',
    offline_failed: 'error',
  };
  return <Tag color={colorMap[status] || 'default'}>{status}</Tag>;
}

export default function KnowledgeItemsPage() {
  const { kbId } = useParams();
  const parsedKbId = Number(kbId);
  const { activeProject, activeProjectId } = useActiveProject();
  const [items, setItems] = useState<KnowledgeItemRecord[]>([]);
  const [dashboard, setDashboard] = useState<Record<string, number>>({
    all: 0,
    editing: 0,
    publishing: 0,
    active: 0,
    publish_failed: 0,
    offline: 0,
    offline_failed: 0,
  });
  const [loading, setLoading] = useState(false);

  const loadItems = async () => {
    if (!activeProjectId || !parsedKbId) {
      return;
    }

    try {
      setLoading(true);
      const [itemsData, dashboardData] = await Promise.all([
        fetchKnowledgeItems(activeProjectId, parsedKbId),
        fetchKnowledgeBaseDashboard(activeProjectId, parsedKbId),
      ]);
      setItems(itemsData);
      setDashboard(dashboardData);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '知识条目加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadItems();
  }, [activeProjectId, parsedKbId]);

  const columns = useMemo(
    () => [
      { title: '标题', dataIndex: 'title', key: 'title' },
      { title: '来源', dataIndex: 'source', key: 'source' },
      { title: '关键词', dataIndex: 'keywords', key: 'keywords' },
      { title: '状态', dataIndex: 'status', key: 'status' },
      { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt' },
      { title: '操作', dataIndex: 'actions', key: 'actions' },
    ],
    [],
  );

  const dataSource = items.map((item) => ({
    key: item.id,
    title: item.title,
    source: item.document_name || item.source_type || '-',
    keywords: (
      <Space size={4} wrap>
        {item.keywords?.length ? item.keywords.map((keyword) => <Tag key={keyword}>{keyword}</Tag>) : '-'}
      </Space>
    ),
    status: renderStatusTag(item.status),
    updatedAt: item.updated_at ? new Date(item.updated_at).toLocaleString() : '-',
    actions: (
      <Space size={4} wrap>
        <Link to={`/knowledge/bases/${kbId}/items/${item.id}/edit`} className="admin-inlineLink">
          编辑
        </Link>
        {item.status !== 'active' ? (
          <Button
            size="small"
            className="admin-appleButton admin-appleButton--chip"
            onClick={async () => {
              if (!activeProjectId) {
                return;
              }
              try {
                await publishKnowledgeItem(activeProjectId, parsedKbId, item.id);
                message.success('知识已发布');
                await loadItems();
              } catch (error) {
                message.error(error instanceof Error ? error.message : '知识发布失败');
              }
            }}
          >
            发布
          </Button>
        ) : null}
        <Popconfirm
          title="确认删除这条知识吗？"
          onConfirm={async () => {
            if (!activeProjectId) {
              return;
            }
            try {
              await deleteKnowledgeItem(activeProjectId, parsedKbId, item.id);
              message.success('知识已删除');
              await loadItems();
            } catch (error) {
              message.error(error instanceof Error ? error.message : '知识删除失败');
            }
          }}
        >
          <Button type="link" size="small" danger>
            删除
          </Button>
        </Popconfirm>
      </Space>
    ),
  }));

  return (
    <AdminPage
      title={`知识管理 · 知识条目（KB ${kbId}）`}
      description={`支持知识看板、单条编辑、文件 QA 结果查看与状态流转。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['编辑中', '上线中', '生效中', '失败重试']}
      extra={
        <Space>
          <Button className="admin-appleButton admin-appleButton--secondary" onClick={() => void loadItems()} disabled={!activeProjectId}>
            刷新
          </Button>
          <Button type="primary" href={`/knowledge/bases/${kbId}/items/new`} className="admin-appleButton">
            新建知识
          </Button>
        </Space>
      }
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再管理知识条目。" style={{ marginBottom: 16 }} /> : null}
      <Row gutter={[16, 16]}>
        {[
          { title: '全部知识', value: dashboard.all },
          { title: '编辑中', value: dashboard.editing },
          { title: '生效中', value: dashboard.active },
          { title: '失败中', value: (dashboard.publish_failed || 0) + (dashboard.offline_failed || 0) },
        ].map((item) => (
          <Col xs={12} lg={6} key={item.title}>
            <Card className="admin-signalCard">
              <span className="admin-signalCard__label">{item.title}</span>
              <Statistic title="" value={item.value} />
            </Card>
          </Col>
        ))}
        <Col span={24}>
          <Card className="admin-listPanel">
            <div className="admin-listToolbar admin-listToolbar--split">
              <div className="admin-listToolbar__main">
                <Typography.Title level={4} className="admin-listToolbar__title">
                  知识条目列表
                </Typography.Title>
                <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
                  管理手工知识、文件切分结果与 QA 生成内容，并在这里处理发布与删除动作。
                </Typography.Text>
              </div>
              <div className="admin-listToolbar__aside">
                <div className="admin-toolbarPill">
                  <span className="admin-toolbarPill__label">知识库</span>
                  <span className="admin-toolbarPill__value">KB {kbId}</span>
                </div>
              </div>
            </div>
            <Table rowKey="key" loading={loading} pagination={false} columns={columns} dataSource={dataSource} />
          </Card>
        </Col>
      </Row>
    </AdminPage>
  );
}
