import { useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Table, Tag, Typography } from 'antd';
import { useParams } from '@umijs/max';
import { checkKnowledgeDedup } from '@/services/knowledgeApiReal';

export default function DedupRealPage() {
  const { id = '1' } = useParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any[]>([]);

  const handleCheck = async (values: { title: string; keywords: string; content: string }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await checkKnowledgeDedup(id, {
        title: values.title,
        keywords: values.keywords ? values.keywords.split(',').map((s) => s.trim()).filter(Boolean) : [],
        content: values.content,
      });
      setData(res.data?.candidates || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '请求失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <Typography.Title level={3}>知识查重（真实接口）</Typography.Title>
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      <Form layout="vertical" onFinish={handleCheck}>
        <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入标题' }]}>
          <Input />
        </Form.Item>
        <Form.Item label="关键词（逗号分隔）" name="keywords">
          <Input placeholder="港澳通行证, 办理" />
        </Form.Item>
        <Form.Item label="内容" name="content" rules={[{ required: true, message: '请输入内容' }]}>
          <Input.TextArea rows={6} />
        </Form.Item>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" htmlType="submit" loading={loading}>开始查重</Button>
        </Space>
      </Form>
      <Table
        rowKey="knowledge_id"
        columns={[
          { title: '旧知识ID', dataIndex: 'knowledge_id', key: 'knowledge_id' },
          { title: '标题', dataIndex: 'title', key: 'title' },
          { title: '相似度', dataIndex: 'score', key: 'score' },
          {
            title: '原因',
            dataIndex: 'reason',
            key: 'reason',
            render: (value: string[]) => (value || []).map((item) => <Tag key={item}>{item}</Tag>),
          },
        ]}
        dataSource={data}
        pagination={false}
      />
    </Card>
  );
}
