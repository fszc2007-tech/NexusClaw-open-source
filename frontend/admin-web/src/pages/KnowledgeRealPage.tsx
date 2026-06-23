import { useEffect, useState } from 'react';
import { Alert, Button, Card, Space, Spin, Table, Tag, Typography } from 'antd';
import { useParams } from '@umijs/max';
import { fetchKnowledgeList } from '@/services/knowledgeApiReal';

export default function KnowledgeRealPage() {
  const { id = '1' } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    fetchKnowledgeList(id)
      .then((res) => setData(res.data || []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <Card>
      <Typography.Title level={3}>知识管理（真实接口）</Typography.Title>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary">新建知识</Button>
        <Button>批量导入</Button>
      </Space>
      {loading && <Spin />}
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      {!loading && !error && (
        <Table
          rowKey="id"
          columns={[
            { title: '知识ID', dataIndex: 'id', key: 'id' },
            { title: '标题', dataIndex: 'title', key: 'title' },
            { title: '知识库ID', dataIndex: 'kb_id', key: 'kb_id' },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              render: (value: string) => <Tag color={value === 'active' ? 'green' : 'gold'}>{value}</Tag>,
            },
            { title: '版本', dataIndex: 'version_no', key: 'version_no' },
          ]}
          dataSource={data}
          pagination={false}
        />
      )}
    </Card>
  );
}
