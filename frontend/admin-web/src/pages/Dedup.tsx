import { Button, Card, Space, Table, Tag, Typography } from 'antd';

const columns = [
  { title: '新知识ID', dataIndex: 'newKnowledgeId', key: 'newKnowledgeId' },
  { title: '旧知识ID', dataIndex: 'oldKnowledgeId', key: 'oldKnowledgeId' },
  { title: '相似度', dataIndex: 'score', key: 'score' },
  {
    title: '等级',
    dataIndex: 'level',
    key: 'level',
    render: (value: string) => <Tag color={value === 'high' ? 'red' : 'gold'}>{value}</Tag>,
  },
  {
    title: '操作',
    key: 'action',
    render: () => (
      <Space>
        <Button size="small" type="primary">替换旧知识</Button>
        <Button size="small">不替换</Button>
      </Space>
    ),
  },
];

const dataSource = [
  { newKnowledgeId: 101, oldKnowledgeId: 88, score: 0.94, level: 'high' },
];

export default function DedupPage() {
  return (
    <Card>
      <Typography.Title level={3}>知识查重处理</Typography.Title>
      <Table rowKey="newKnowledgeId" columns={columns} dataSource={dataSource} pagination={false} />
    </Card>
  );
}
