import { useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Input, Row, Space, Table, Tag, Typography } from 'antd';
import { message } from '@/services/notify';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { searchKnowledge, type CompilationPageHit, type SearchHit, type SearchResponse } from '@/services/searchApi';

const columns = [
  { title: '标题', dataIndex: 'title', key: 'title' },
  { title: '来源文件', dataIndex: 'sourceFile', key: 'sourceFile' },
  { title: '融合分', dataIndex: 'score', key: 'score' },
  { title: 'Term', dataIndex: 'termScore', key: 'termScore' },
  { title: 'Vector', dataIndex: 'vectorScore', key: 'vectorScore' },
];

export default function ExperienceSearchPage() {
  const { activeProject, activeProjectId } = useActiveProject();
  const [loading, setLoading] = useState(false);
  const [rewrittenQuery, setRewrittenQuery] = useState<string | null>(null);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [compilation, setCompilation] = useState<SearchResponse['compilation'] | null>(null);

  const dataSource = useMemo(
    () =>
      hits.map((item) => ({
        key: item.knowledge_id,
        title: item.title,
        sourceFile: item.document_name || '人工知识',
        score: <Tag color="processing">{item.score.toFixed(4)}</Tag>,
        termScore: <Tag>{Number(item.term_score || 0).toFixed(4)}</Tag>,
        vectorScore: <Tag color="purple">{Number(item.vector_score || 0).toFixed(4)}</Tag>,
      })),
    [hits],
  );

  const compilationRows = useMemo(
    () =>
      (compilation?.page_hits || []).map((item: CompilationPageHit) => ({
        key: item.page_id,
        title: item.title,
        pageType: <Tag color="geekblue">{item.page_type}</Tag>,
        score: <Tag color={item.score >= 0.82 ? 'success' : 'warning'}>{item.score.toFixed(4)}</Tag>,
        sources: <Tag>{item.supporting_source_count}</Tag>,
        health: (
          <Tag color={item.health_status === 'healthy' ? 'success' : item.health_status === 'warning' ? 'warning' : 'error'}>
            {item.health_status}
          </Tag>
        ),
      })),
    [compilation],
  );

  const handleSearch = async (query: string) => {
    const normalizedQuery = query.trim();
    if (!normalizedQuery || !activeProjectId) {
      return;
    }
    try {
      setLoading(true);
      const result = await searchKnowledge(activeProjectId, { query: normalizedQuery });
      setHits(result.hits);
      setRewrittenQuery(result.rewritten_query);
      setCompilation(result.compilation);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '检索失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AdminPage
      title="体验广场 · 知识检索"
      description={`支持后台同时观察原始检索与知识编译命中。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['Top10 检索', '融合排序', '知识编译命中']}
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再体验知识检索。" style={{ marginBottom: 16 }} /> : null}
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card className="admin-listPanel">
            <div className="admin-listToolbar admin-listToolbar--split">
              <div className="admin-listToolbar__main">
                <Typography.Title level={4} className="admin-listToolbar__title">
                  搜索面板
                </Typography.Title>
                <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
                  输入真实问题，观察改写后的 query、原始检索得分，以及知识编译页是否能够稳定命中。
                </Typography.Text>
              </div>
              <div className="admin-listToolbar__aside">
                <div className="admin-toolbarPill">
                  <span className="admin-toolbarPill__label">当前项目</span>
                  <span className="admin-toolbarPill__value">{activeProject?.company_name ?? '未选择'}</span>
                </div>
              </div>
            </div>
            <Input.Search
              className="admin-searchInput"
              enterButton={<Button type="primary" className="admin-appleButton">搜索</Button>}
              loading={loading}
              placeholder="输入问题，例如：港澳通行证怎么办理"
              onSearch={(value) => void handleSearch(value)}
            />
          </Card>
        </Col>
        <Col xs={24} lg={15}>
          <Card className="admin-listPanel">
            <div className="admin-listToolbar">
              <div className="admin-listToolbar__main">
                <Typography.Title level={4} className="admin-listToolbar__title">
                  Top10 检索结果
                </Typography.Title>
                <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
                  用于检查 raw retrieval 是否覆盖正确知识，并确认融合排序把最相关结果顶到了前面。
                </Typography.Text>
              </div>
              <div className="admin-listToolbar__aside">
                <div className="admin-toolbarPill">
                  <span className="admin-toolbarPill__label">命中数</span>
                  <span className="admin-toolbarPill__value">{hits.length}</span>
                </div>
              </div>
            </div>
            <Table rowKey="key" loading={loading} pagination={false} columns={columns} dataSource={dataSource} />
          </Card>
          <Card className="admin-listPanel" style={{ marginTop: 16 }}>
            <div className="admin-listToolbar">
              <div className="admin-listToolbar__main">
                <Typography.Title level={4} className="admin-listToolbar__title">
                  知识编译命中
                </Typography.Title>
                <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
                  这里用于观察编译知识页是否可直接复用，以及为什么会 fallback 到原始检索。
                </Typography.Text>
              </div>
              <div className="admin-listToolbar__aside">
                <Space size={8} wrap>
                  <Tag color={compilation?.enabled ? 'processing' : 'default'}>{compilation?.enabled ? 'enabled' : 'disabled'}</Tag>
                  <Tag color={compilation?.usable ? 'success' : 'warning'}>{compilation?.usable ? 'usable' : 'fallback'}</Tag>
                  {compilation?.strategy ? <Tag color="geekblue">{compilation.strategy}</Tag> : null}
                </Space>
              </div>
            </div>
            <Table
              rowKey="key"
              loading={loading}
              pagination={false}
              columns={[
                { title: '编译页标题', dataIndex: 'title', key: 'title' },
                { title: '类型', dataIndex: 'pageType', key: 'pageType' },
                { title: '评分', dataIndex: 'score', key: 'score' },
                { title: '来源数', dataIndex: 'sources', key: 'sources' },
                { title: '健康度', dataIndex: 'health', key: 'health' },
              ]}
              dataSource={compilationRows}
              locale={{ emptyText: '当前查询没有命中可用的编译知识页。' }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={9}>
          <Card className="admin-notePanel">
            <Typography.Text className="admin-notePanel__eyebrow">Search Debug</Typography.Text>
            <Typography.Title level={4} className="admin-notePanel__title">
              检索调试助手
            </Typography.Title>
            {rewrittenQuery ? (
              <Typography.Paragraph>
                改写后问题：<Typography.Text code>{rewrittenQuery}</Typography.Text>
              </Typography.Paragraph>
            ) : null}
            {compilation ? (
              <>
                <Typography.Paragraph>
                  编译策略：<Typography.Text code>{compilation.strategy}</Typography.Text>
                </Typography.Paragraph>
                <Typography.Paragraph>
                  选择模式：<Typography.Text code>{compilation.selected_mode}</Typography.Text>
                </Typography.Paragraph>
                <Typography.Paragraph>
                  fallback 原因：<Typography.Text code>{compilation.fallback_reason || 'none'}</Typography.Text>
                </Typography.Paragraph>
              </>
            ) : null}
            <Typography.Paragraph>
              这里先用于单独观察 raw retrieval 与 compiled knowledge 的协同效果，重点看两者是否在高频问题上形成稳定复用。
            </Typography.Paragraph>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              下一步可继续接入“基于当前命中直接生成回答”“人工相关性标注”“编译页质量巡检”。
            </Typography.Paragraph>
          </Card>
          <Card className="admin-notePanel" style={{ marginTop: 16 }}>
            <Typography.Text className="admin-notePanel__eyebrow">Top Snapshot</Typography.Text>
            <Typography.Title level={4} className="admin-notePanel__title">
              编译页 / Raw 对照
            </Typography.Title>
            <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
              {compilation?.reference_items?.[0]?.snippet ||
                hits[0]?.snippet ||
                '搜索后这里会展示编译页摘要或最优原始候选，便于快速判断当前查询更适合走哪条链路。'}
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>
    </AdminPage>
  );
}
