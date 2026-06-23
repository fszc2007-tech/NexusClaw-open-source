import { Button, Card, Space, Table, Tag, Typography } from 'antd';

const columns = [
  { title: '知识ID', dataIndex: 'id', key: 'id' },
  { title: '标题', dataIndex: 'title', key: 'title' },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (value: string) => <Tag color={value === 'active' ? 'green' : 'gold'}>{value}</Tag>,
  },
  {
    title: '操作',
    key: 'action',
    render: () => (
      <Space>
        <Button size="small">编辑</Button>
        <Button size="small" type="primary">上线</Button>
      </Space>
    ),
  },
];

const dataSource = [
  { id: 101, title: '港澳通行证办理指南', status: 'draft' },
  { id: 88, title: '港澳通行证办理流程', status: 'active' },
];

export default function KnowledgePage() {
  return (
    <Card>
      <Typography.Title level={3}>知识管理</Typography.Title>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary">新建知识</Button>
        <Button>批量导入</Button>
      </Space>
      <Table rowKey="id" columns={columns} dataSource={dataSource} pagination={false} />
    </Card>
  );
}
