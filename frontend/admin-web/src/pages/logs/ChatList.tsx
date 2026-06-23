import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Table, Tag, Typography } from 'antd';
import { message } from '@/services/notify';
import { Link } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { fetchChatLogs, type ChatLogSummary } from '@/services/logApi';

export default function ChatLogsPage() {
  const [form] = Form.useForm();
  const [logs, setLogs] = useState<ChatLogSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const { activeProject, activeProjectId } = useActiveProject();

  const loadLogs = async (filters?: { sessionId?: string; queryKeyword?: string; answerKeyword?: string }) => {
    if (!activeProjectId) {
      return;
    }

    try {
      setLoading(true);
      setLogs(await fetchChatLogs(activeProjectId, filters));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '日志列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadLogs();
  }, [activeProjectId]);

  const columns = useMemo(
    () => [
      { title: '会话 ID', dataIndex: 'sessionId', key: 'sessionId' },
      { title: '问题', dataIndex: 'query', key: 'query' },
      { title: '来源', dataIndex: 'source', key: 'source' },
      { title: '评价', dataIndex: 'feedback', key: 'feedback' },
      { title: '操作', dataIndex: 'actions', key: 'actions' },
    ],
    [],
  );

  const dataSource = logs.map((log) => ({
    key: log.session_id,
    sessionId: log.session_id,
    query: log.query || '-',
    source: <Tag color="processing">{log.source}</Tag>,
    feedback: <Tag color={log.feedback === 'pending' ? 'default' : 'success'}>{log.feedback}</Tag>,
    actions: (
      <Space>
        <Link to={`/logs/chat/${log.session_id}`}>详情</Link>
        <Button
          type="link"
          size="small"
          onClick={async () => {
            await navigator.clipboard.writeText(log.session_id);
            message.success('会话 ID 已复制');
          }}
        >
          复制
        </Button>
      </Space>
    ),
  }));

  return (
    <AdminPage
      title="日志查询 · 历史对话日志"
      description={`按会话、问题与回答关键字查询问答全过程。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['问题改写', 'Prompt 快照', '来源知识']}
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再查询日志。" style={{ marginBottom: 16 }} /> : null}
      <Card className="admin-listPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              日志筛选
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              先按会话、问题或回答关键字缩小范围，再进入详细回放。
            </Typography.Text>
          </div>
        </div>
        <Form
          form={form}
          layout="inline"
          className="admin-filterForm"
          onFinish={(values) =>
            void loadLogs({
              sessionId: values.session_id,
              queryKeyword: values.query_keyword,
              answerKeyword: values.answer_keyword,
            })
          }
        >
          <Form.Item name="session_id">
            <Input placeholder="会话 ID" className="admin-toolbarInput admin-toolbarInput--sm" />
          </Form.Item>
          <Form.Item name="query_keyword">
            <Input placeholder="问题关键词" className="admin-toolbarInput" />
          </Form.Item>
          <Form.Item name="answer_keyword">
            <Input placeholder="回答关键词" className="admin-toolbarInput" />
          </Form.Item>
          <Form.Item>
            <Space wrap>
              <Button type="primary" htmlType="submit" className="admin-appleButton" disabled={!activeProjectId}>
                查询
              </Button>
              <Button
                className="admin-appleButton admin-appleButton--secondary"
                onClick={() => {
                  form.resetFields();
                  void loadLogs();
                }}
              >
                重置
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
      <Card title="日志列表" className="admin-listPanel" style={{ marginTop: 16 }}>
        <Table rowKey="key" loading={loading} pagination={false} columns={columns} dataSource={dataSource} />
      </Card>
    </AdminPage>
  );
}
