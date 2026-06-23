import { useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Table, Tag, Typography } from 'antd';
import { checkDedup } from '@/services/knowledgeApi';

export default function DedupRealPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<any[]>([]);
  const [form] = Form.useForm();
  const projectId = '1';

  const onFinish = async (values: { title: string; keywords?: string; content: string }) => {
    setLoading(true);
    setError(null);
    try {
      const res = await checkDedup(projectId, {
        title: values.title,
        keywords: values.keywords ? values.keywords.split(',').map((item) => item.trim()).filter(Boolean) : [],
        content: values.content,
      });
      setRows(res.data?.candidates || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '查重失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <Typography.Title level={3}>知识查重（真实接口）</Typography.Title>
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入标题' }]}>
          <Input />
        </Form.Item>
        <Form.Item label="关键词（逗号分隔）" name="keywords">
          <Input />
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
          { title: '候选知识ID', dataIndex: 'knowledge_id', key: 'knowledge_id' },
          { title: '标题', dataIndex: 'title', key: 'title' },
          { title: '相似度', dataIndex: 'score', key: 'score' },
          {
            title: '原因',
            dataIndex: 'reason',
            key: 'reason',
            render: (value: string[]) => <Space wrap>{(value || []).map((item) => <Tag key={item}>{item}</Tag>)}</Space>,
          },
        ]}
        dataSource={rows}
        pagination={false}
      />
    </Card>
  );
}
