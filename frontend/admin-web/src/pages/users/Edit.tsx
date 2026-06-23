import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Popconfirm, Radio, Select, Space, Typography } from 'antd';
import { message } from '@/services/notify';
import { useNavigate, useParams } from '@umijs/max';
import AdminPage from '@/components/AdminPage';
import { deleteUser, fetchUser, updateUser } from '@/services/userApi';

export default function UserEditPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) {
      return;
    }

    const loadUser = async () => {
      try {
        setLoading(true);
        const user = await fetchUser(Number(id));
        form.setFieldsValue({
          username: user.username,
          nickname: user.nickname,
          profile: user.profile,
          system_role: user.system_role,
          status: user.status,
        });
      } catch (error) {
        message.error(error instanceof Error ? error.message : '用户详情加载失败');
      } finally {
        setLoading(false);
      }
    };

    void loadUser();
  }, [form, id]);

  const handleSubmit = async (values: {
    username: string;
    nickname?: string;
    profile?: string;
    password?: string;
    system_role: 'super_admin' | 'normal_user';
    status: 'active' | 'disabled';
  }) => {
    if (!id) {
      return;
    }

    try {
      setSubmitting(true);
      await updateUser(Number(id), {
        ...values,
        password: values.password?.trim() ? values.password : undefined,
      });
      message.success('用户已更新');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '用户更新失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!id) {
      return;
    }

    try {
      await deleteUser(Number(id));
      message.success('用户已删除');
      navigate('/users');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '用户删除失败');
    }
  };

  return (
    <AdminPage
      title={`用户管理 · 编辑用户（#${id}）`}
      description="编辑系统账号、昵称、简介和系统权限。"
      tags={['账号设置', '系统权限']}
    >
      <Card className="admin-formPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              账号资料与权限
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              管理昵称、简介、角色和账号状态。密码修改保持单独显式触发，避免误更新。
            </Typography.Text>
          </div>
          <div className="admin-listToolbar__aside">
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">用户编号</span>
              <span className="admin-toolbarPill__value">#{id}</span>
            </div>
          </div>
        </div>
        <Form
          form={form}
          layout="vertical"
          className="admin-form"
          initialValues={{ system_role: 'normal_user', status: 'active' }}
          onFinish={(values) => void handleSubmit(values)}
        >
          <div className="admin-formGrid">
            <Form.Item label="用户名" name="username">
              <Input />
            </Form.Item>
            <Form.Item label="昵称" name="nickname">
              <Input />
            </Form.Item>
            <Form.Item label="简介" name="profile" className="admin-formItem--full">
              <Input.TextArea rows={4} placeholder="描述该账号的职责范围或团队身份" />
            </Form.Item>
            <Form.Item label="重置密码" name="password" extra="留空则保持原密码不变" className="admin-formItem--full">
              <Input.Password />
            </Form.Item>
            <Form.Item label="系统权限" name="system_role" className="admin-formItem--full">
              <Radio.Group
                className="admin-choiceGroup"
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
          </div>
          <Typography.Text type="secondary" className="admin-formHint">
            超级管理员拥有全局配置权限；普通成员建议只承担项目内运营和内容治理职责。
          </Typography.Text>
          <div className="admin-formActions">
            <Button type="primary" htmlType="submit" className="admin-appleButton" loading={submitting || loading}>
              保存
            </Button>
            <Popconfirm title="确认删除这个用户？" onConfirm={() => void handleDelete()}>
              <Button danger className="admin-appleButton admin-appleButton--secondary">
                删除用户
              </Button>
            </Popconfirm>
          </div>
        </Form>
      </Card>
    </AdminPage>
  );
}
