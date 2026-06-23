import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography } from 'antd';
import { message } from '@/services/notify';
import { Link } from '@umijs/max';
import AdminPage from '@/components/AdminPage';
import { createUser, fetchUsers, type UserCreatePayload, type UserRecord } from '@/services/userApi';

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '昵称', dataIndex: 'nickname', key: 'nickname' },
  { title: '系统角色', dataIndex: 'role', key: 'role' },
  { title: '状态', dataIndex: 'status', key: 'status' },
  { title: '操作', dataIndex: 'actions', key: 'actions' },
];

export default function UsersListPage() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [createVisible, setCreateVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<UserCreatePayload>();

  const loadUsers = async () => {
    try {
      setLoading(true);
      setUsers(await fetchUsers());
    } catch (error) {
      message.error(error instanceof Error ? error.message : '用户列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadUsers();
  }, []);

  const handleCreate = async (values: UserCreatePayload) => {
    try {
      setSubmitting(true);
      await createUser(values);
      message.success('用户创建成功');
      setCreateVisible(false);
      form.resetFields();
      await loadUsers();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '用户创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AdminPage
      title="用户管理"
      description="由超级管理员统一维护平台账号、系统权限、昵称与简介。"
      tags={['超级管理员专属', '系统角色']}
      extra={
        <Button type="primary" className="admin-appleButton" onClick={() => setCreateVisible(true)}>
          创建用户
        </Button>
      }
    >
      <Card className="admin-listPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              平台账号
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              统一维护后台运营账号、角色权限和启停状态。账号配置是整个平台治理链路的入口。
            </Typography.Text>
          </div>
          <div className="admin-listToolbar__aside">
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">用户数</span>
              <span className="admin-toolbarPill__value">{users.length}</span>
            </div>
          </div>
        </div>
        <Table
          rowKey="id"
          loading={loading}
          pagination={false}
          columns={columns}
          dataSource={users.map((user) => ({
            id: user.id,
            username: user.username,
            nickname: user.nickname,
            role: <Tag color={user.system_role === 'super_admin' ? 'gold' : 'blue'}>{user.system_role}</Tag>,
            status: <Tag color={user.status === 'active' ? 'success' : 'default'}>{user.status}</Tag>,
            actions: (
              <Link to={`/users/${user.id}/edit`} className="admin-inlineLink">
                编辑
              </Link>
            ),
          }))}
        />
      </Card>
      <Modal
        title="创建用户"
        className="admin-glassModal"
        open={createVisible}
        onCancel={() => setCreateVisible(false)}
        onOk={() => void form.submit()}
        confirmLoading={submitting}
        okButtonProps={{ className: 'admin-appleButton' }}
        cancelButtonProps={{ className: 'admin-appleButton admin-appleButton--secondary' }}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ system_role: 'normal_user', status: 'active' }}
          onFinish={(values) => void handleCreate(values)}
        >
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="初始密码" name="password" rules={[{ required: true, message: '请输入初始密码' }, { min: 8, message: '至少 8 位' }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item label="昵称" name="nickname">
            <Input />
          </Form.Item>
          <Form.Item label="简介" name="profile">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item label="系统角色" name="system_role">
            <Select
              options={[
                { label: '超级管理员', value: 'super_admin' },
                { label: '普通成员', value: 'normal_user' },
              ]}
            />
          </Form.Item>
          <Form.Item label="状态" name="status">
            <Select
              options={[
                { label: '启用', value: 'active' },
                { label: '停用', value: 'disabled' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </AdminPage>
  );
}
