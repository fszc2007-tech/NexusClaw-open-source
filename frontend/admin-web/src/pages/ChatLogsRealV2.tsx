import { useEffect, useState } from 'react';
import { Alert, Card, Spin, Table, Tag, Typography } from 'antd';
import { fetchProjectSessions } from '@/services/sessionApi';

export default function ChatLogsRealV2Page() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);
  const projectId = '1';

  useEffect(() => {
    fetchProjectSessions(projectId)
      .then((res) => setData(res.data || []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card>
      <Typography.Title level={3}>会话日志（真实接口 V2）</Typography.Title>
      {loading && <Spin />}
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      {!loading && !error && (
        <Table
          rowKey="session_id"
          columns={[
            { title: '会话ID', dataIndex: 'session_id', key: 'session_id' },
            { title: '项目ID', dataIndex: 'project_id', key: 'project_id' },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              render: (value: string) => <Tag color={value === 'active' ? 'green' : 'default'}>{value}</Tag>,
            },
          ]}
          dataSource={data}
          pagination={false}
        />
      )}
    </Card>
  );
}
