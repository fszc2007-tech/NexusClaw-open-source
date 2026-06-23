import { useEffect, useState } from 'react';
import { Alert, Card, Descriptions, List, Space, Tag, Typography } from 'antd';
import { message } from '@/services/notify';
import { useParams } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { fetchChatLogDetail, type ChatLogDetail } from '@/services/logApi';

export default function ChatLogDetailPage() {
  const { id } = useParams();
  const { activeProject, activeProjectId } = useActiveProject();
  const [detail, setDetail] = useState<ChatLogDetail | null>(null);

  useEffect(() => {
    const loadDetail = async () => {
      if (!activeProjectId || !id) {
        return;
      }

      try {
        setDetail(await fetchChatLogDetail(activeProjectId, id));
      } catch (error) {
        message.error(error instanceof Error ? error.message : '日志详情加载失败');
      }
    };

    void loadDetail();
  }, [activeProjectId, id]);

  return (
    <AdminPage
      title={`日志查询 · 对话详情（#${id}）`}
      description={`查看单条问答的原始问题、改写结果、Prompt 快照、回答与引用来源。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['单条回放', '链路追踪']}
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再查看日志详情。" style={{ marginBottom: 16 }} /> : null}
      <Card className="admin-listPanel">
        <div className="admin-listToolbar">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              会话概览
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              先确认会话来源、状态和命中的知识范围，再逐轮检查改写、 Prompt 和答案引用链路。
            </Typography.Text>
          </div>
        </div>
        <div className="admin-detailGrid">
          <div className="admin-detailStat">
            <span className="admin-detailStat__label">会话 ID</span>
            <Typography.Title level={3} className="admin-detailStat__value">
              {detail?.session_id || '-'}
            </Typography.Title>
            <span className="admin-detailStat__hint">用于关联整段对话及下游日志分析。</span>
          </div>
          <div className="admin-detailStat">
            <span className="admin-detailStat__label">来源</span>
            <Typography.Title level={3} className="admin-detailStat__value">
              {detail?.source || '-'}
            </Typography.Title>
            <span className="admin-detailStat__hint">标识本次问答来自门户、后台体验区或其他入口。</span>
          </div>
          <div className="admin-detailStat">
            <span className="admin-detailStat__label">会话标题</span>
            <Typography.Title level={3} className="admin-detailStat__value">
              {detail?.title || '-'}
            </Typography.Title>
            <span className="admin-detailStat__hint">若标题为空，通常表示本轮未做会话摘要生成。</span>
          </div>
          <div className="admin-detailStat">
            <span className="admin-detailStat__label">状态</span>
            <div className="admin-detailStat__tagWrap">
              <Tag color="processing">{detail?.status || '-'}</Tag>
            </div>
            <span className="admin-detailStat__hint">当前展示的是日志记录状态，不直接代表内容质量。</span>
          </div>
          <div className="admin-detailMeta">
            <Descriptions column={2}>
              <Descriptions.Item label="选中知识库">
                <Space wrap>
                  {detail?.selected_kb_ids?.length
                    ? detail.selected_kb_ids.map((kb) => <Tag key={kb}>KB {kb}</Tag>)
                    : <Tag>全部知识库</Tag>}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="轮次数">{detail?.turns?.length || 0}</Descriptions.Item>
            </Descriptions>
          </div>
        </div>
      </Card>
      <Card className="admin-listPanel" style={{ marginTop: 16 }}>
        <div className="admin-listToolbar">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              问答回放
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              每轮展示原始问题、改写结果、Prompt 快照、最终答案和引用知识，便于逐段追踪异常。
            </Typography.Text>
          </div>
        </div>
        <List
          className="admin-logReplay"
          dataSource={detail?.turns || []}
          renderItem={(turn) => (
            <List.Item>
              <div className="admin-logTurn">
                <Descriptions column={1} bordered size="small">
                  <Descriptions.Item label="原始问题">{turn.query || '-'}</Descriptions.Item>
                  <Descriptions.Item label="改写问题">{turn.rewritten_query || '-'}</Descriptions.Item>
                  <Descriptions.Item label="模型">{turn.model_name || '-'}</Descriptions.Item>
                  <Descriptions.Item label="Trace ID">{turn.trace_id || '-'}</Descriptions.Item>
                </Descriptions>
                <Card size="small" title="Prompt 快照" className="admin-logTurn__block">
                  <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                    {turn.prompt_snapshot || '暂无 Prompt 快照'}
                  </Typography.Paragraph>
                </Card>
                <Card size="small" title="回答与引用来源" className="admin-logTurn__block">
                  <Typography.Paragraph>{turn.answer || '暂无回答'}</Typography.Paragraph>
                  <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    来源知识：{turn.sources.length ? turn.sources.map((source) => source.title).join('、') : '无'}
                  </Typography.Paragraph>
                </Card>
              </div>
            </List.Item>
          )}
        />
      </Card>
    </AdminPage>
  );
}
