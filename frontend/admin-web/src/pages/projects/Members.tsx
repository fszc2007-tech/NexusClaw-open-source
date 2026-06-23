import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography } from 'antd';
import { message } from '@/services/notify';
import { useParams } from '@umijs/max';
import AdminPage from '@/components/AdminPage';
import {
  addProjectMembers,
  deleteProjectMember,
  fetchProjectMembers,
  updateProjectMember,
  type ProjectMemberRecord,
} from '@/services/projectMemberApi';

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username' },
  { title: '昵称', dataIndex: 'nickname', key: 'nickname' },
  { title: '项目角色', dataIndex: 'role', key: 'role' },
  { title: '操作', dataIndex: 'actions', key: 'actions' },
];

export default function ProjectMembersPage() {
  const { id } = useParams();
  const projectId = Number(id);
  const [members, setMembers] = useState<ProjectMemberRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [createVisible, setCreateVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<{ usernames: string; project_role: 'project_admin' | 'project_member' }>();

  const loadMembers = async () => {
    if (!projectId) {
      return;
    }
    try {
      setLoading(true);
      setMembers(await fetchProjectMembers(projectId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '项目成员加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMembers();
  }, [projectId]);

  const handleCreate = async (values: { usernames: string; project_role: 'project_admin' | 'project_member' }) => {
    try {
      setSubmitting(true);
      const usernames = values.usernames
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean);
      await addProjectMembers(projectId, {
        usernames,
        project_role: values.project_role,
      });
      message.success('成员已添加');
      setCreateVisible(false);
      form.resetFields();
      await loadMembers();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '成员添加失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRoleChange = async (member: ProjectMemberRecord, nextRole: 'project_admin' | 'project_member') => {
    try {
      await updateProjectMember(projectId, member.id, { project_role: nextRole });
      message.success('成员角色已更新');
      await loadMembers();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '成员角色更新失败');
    }
  };

  const handleDelete = async (memberId: number) => {
    try {
      await deleteProjectMember(projectId, memberId);
      message.success('成员已移出项目');
      await loadMembers();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '移出成员失败');
    }
  };

  return (
    <AdminPage
      title={`项目管理 · 项目成员（#${id}）`}
      description="维护项目成员与项目管理员角色，后续会接入批量添加、最多 5 位项目管理员等业务约束。"
      tags={['项目管理员', '项目成员']}
      extra={
        <Button type="primary" className="admin-appleButton" onClick={() => setCreateVisible(true)}>
          添加成员
        </Button>
      }
    >
      <Card className="admin-listPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              项目成员列表
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              维护项目管理员与普通成员。当前仍使用用户名录入，后续可升级为搜索型用户选择器。
            </Typography.Text>
          </div>
          <div className="admin-listToolbar__aside">
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">成员数</span>
              <span className="admin-toolbarPill__value">{members.length}</span>
            </div>
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">项目编号</span>
              <span className="admin-toolbarPill__value">#{id}</span>
            </div>
          </div>
        </div>
        <Table
          rowKey="id"
          loading={loading}
          pagination={false}
          columns={columns}
          dataSource={members.map((member) => ({
            id: member.id,
            username: member.username,
            nickname: member.nickname,
            role: <Tag color={member.project_role === 'project_admin' ? 'gold' : 'blue'}>{member.project_role}</Tag>,
            actions: (
              <Space>
                {member.project_role === 'project_admin' ? (
                  <Button
                    size="small"
                    className="admin-appleButton admin-appleButton--chip"
                    onClick={() => void handleRoleChange(member, 'project_member')}
                  >
                    设为项目成员
                  </Button>
                ) : (
                  <Button
                    size="small"
                    className="admin-appleButton admin-appleButton--chip"
                    onClick={() => void handleRoleChange(member, 'project_admin')}
                  >
                    设为项目管理员
                  </Button>
                )}
                <Popconfirm title="确认移出该成员？" onConfirm={() => void handleDelete(member.id)}>
                  <Button size="small" danger type="link">
                    移出项目
                  </Button>
                </Popconfirm>
              </Space>
            ),
          }))}
        />
      </Card>
      <Modal
        title="添加项目成员"
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
          initialValues={{ project_role: 'project_member' }}
          onFinish={(values) => void handleCreate(values)}
        >
          <Form.Item
            label="用户名"
            name="usernames"
            rules={[{ required: true, message: '请输入一个或多个用户名' }]}
            extra="支持换行或逗号分隔多个用户名"
          >
            <Input.TextArea rows={4} placeholder={'例如：admin_user\nproject_user_a'} />
          </Form.Item>
          <Form.Item label="项目角色" name="project_role">
            <Select
              options={[
                { label: '项目成员', value: 'project_member' },
                { label: '项目管理员', value: 'project_admin' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </AdminPage>
  );
}
