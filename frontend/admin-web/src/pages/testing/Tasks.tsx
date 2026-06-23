import { Button, Card, Space, Table, Tag, Typography } from 'antd';
import { Link } from '@umijs/max';
import AdminPage from '@/components/AdminPage';

const columns = [
  { title: '任务名称', dataIndex: 'name', key: 'name' },
  { title: '任务类型', dataIndex: 'type', key: 'type' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '操作', dataIndex: 'actions', key: 'actions' },
];

export default function TestingTasksPage() {
  return (
    <AdminPage
      title="测试管理 · 测试任务"
      description="对问答结果、检索结果与参考答案进行自动化批量测试和评估。"
      tags={['自动评测', '机跑答案', '检索评测']}
      extra={<Button type="primary" className="admin-appleButton">新建测试任务</Button>}
    >
      <Card className="admin-listPanel">
        <div className="admin-listToolbar">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              测试任务
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              用于回归评测检索结果、生成答案和参考答案一致性。
            </Typography.Text>
          </div>
        </div>
        <Table
          rowKey="name"
          pagination={false}
          columns={columns}
          dataSource={[
            {
              name: '四月检索效果测试',
              type: 'retrieval_only',
              status: <Tag color="processing">运行中</Tag>,
              actions: (
                <Space>
                  <Link to="/testing/tasks/1">详情</Link>
                  <a>重跑</a>
                </Space>
              ),
            },
            {
              name: '参考答案一致性测试',
              type: 'compare_ref',
              status: <Tag color="success">成功</Tag>,
              actions: (
                <Space>
                  <Link to="/testing/tasks/2">详情</Link>
                  <a>删除</a>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </AdminPage>
  );
}
