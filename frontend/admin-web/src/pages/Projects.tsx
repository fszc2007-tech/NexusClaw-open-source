import { Card, Table, Typography } from 'antd';

const columns = [
  { title: '项目ID', dataIndex: 'projectKey', key: 'projectKey' },
  { title: '项目名称', dataIndex: 'name', key: 'name' },
  { title: '状态', dataIndex: 'status', key: 'status' },
];

const dataSource = [
  { key: 1, projectKey: 'nexusclaw', name: 'NexusClaw', status: 'active' },
];

export default function ProjectsPage() {
  return (
    <Card>
      <Typography.Title level={3}>项目管理</Typography.Title>
      <Table rowKey="key" columns={columns} dataSource={dataSource} pagination={false} />
    </Card>
  );
}
