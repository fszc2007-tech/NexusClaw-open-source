import { useEffect, useState } from 'react';
import { Alert, Card, Spin, Table, Typography } from 'antd';
import { fetchProjects } from '@/services/api';

export default function ProjectsRealPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    fetchProjects()
      .then((res) => setData(res.data || []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card>
      <Typography.Title level={3}>项目管理（真实接口）</Typography.Title>
      {loading && <Spin />}
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      {!loading && !error && (
        <Table
          rowKey="id"
          columns={[
            { title: '项目ID', dataIndex: 'project_key', key: 'project_key' },
            { title: '项目名称', dataIndex: 'name', key: 'name' },
            { title: '状态', dataIndex: 'status', key: 'status' },
          ]}
          dataSource={data}
          pagination={false}
        />
      )}
    </Card>
  );
}
