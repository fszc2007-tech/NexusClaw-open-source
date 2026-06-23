import { Card, Table, Typography } from 'antd';

const columns = [
  { title: '会话ID', dataIndex: 'sessionId', key: 'sessionId' },
  { title: '问题', dataIndex: 'query', key: 'query' },
  { title: '回答', dataIndex: 'answer', key: 'answer' },
  { title: '时间', dataIndex: 'createdAt', key: 'createdAt' },
];

const dataSource = [
  {
    key: 1,
    sessionId: 'sess_001',
    query: '港澳通行证怎么办理？',
    answer: '这是问答服务层占位回答，后续将接入多轮改写、检索、重排与大模型生成。',
    createdAt: '2026-04-03 10:00:00',
  },
];

export default function ChatLogsRealPage() {
  return (
    <Card>
      <Typography.Title level={3}>会话日志（真实接口预备页）</Typography.Title>
      <Table rowKey="key" columns={columns} dataSource={dataSource} pagination={false} />
    </Card>
  );
}
