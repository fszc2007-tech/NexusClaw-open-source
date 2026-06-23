import { useEffect, useState } from 'react';
import { Alert, Card, List, Spin, Tag, Typography } from 'antd';
import { fetchSessions } from '@/services/api';

export default function HistoryRealPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const projectId = '1';

  useEffect(() => {
    fetchSessions(projectId)
      .then((res) => setSessions(res.data || []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card>
      <Typography.Title level={3}>历史会话（真实接口）</Typography.Title>
      {loading && <Spin />}
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      {!loading && !error && (
        <List
          dataSource={sessions}
          renderItem={(item) => (
            <List.Item>
              <div style={{ width: '100%' }}>
                <Typography.Text strong>{item.session_id}</Typography.Text>
                <div style={{ marginTop: 8 }}>
                  <Tag color="blue">project: {item.project_id}</Tag>
                  <Tag color="green">{item.status}</Tag>
                </div>
              </div>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
