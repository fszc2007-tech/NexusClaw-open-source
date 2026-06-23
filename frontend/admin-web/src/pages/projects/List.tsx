import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Space, Table, Tag, Typography } from 'antd';
import { message } from '@/services/notify';
import { Link } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { getStoredUser } from '@/services/authStore';
import { fetchProjects, type ProjectRecord } from '@/services/projectApi';
import { setStoredProjectId } from '@/services/projectStore';

export default function ProjectsListPage() {
  const currentUser = getStoredUser();
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadProjects = async () => {
      try {
        setLoading(true);
        setProjects(await fetchProjects());
      } catch (error) {
        message.error(error instanceof Error ? error.message : '项目列表加载失败');
      } finally {
        setLoading(false);
      }
    };

    void loadProjects();
  }, []);

  const columns = useMemo(
    () => [
      { title: '项目 ID', dataIndex: 'projectKey', key: 'projectKey' },
      { title: '公司名称', dataIndex: 'companyName', key: 'companyName' },
      { title: '项目能力', dataIndex: 'capabilities', key: 'capabilities' },
      { title: '状态', dataIndex: 'status', key: 'status' },
      { title: '操作', dataIndex: 'actions', key: 'actions' },
    ],
    [],
  );

  const dataSource = projects.map((project) => ({
    key: project.id,
    projectKey: project.project_key,
    companyName: project.company_name,
    capabilities: (
      <Space wrap>
        {project.capabilities.multi_turn ? <Tag color="blue">多轮问答</Tag> : null}
        {project.capabilities.sensitive_detection ? <Tag color="purple">敏感检测</Tag> : null}
        {project.capabilities.gov_domain_check ? <Tag color="cyan">政务校验</Tag> : null}
        {project.capabilities.knowledge_tree ? <Tag color="green">知识树</Tag> : null}
      </Space>
    ),
    status: <Tag color={project.status === 'active' ? 'success' : 'default'}>{project.status}</Tag>,
    actions: (
      <Space>
        <Button
          size="small"
          className="admin-appleButton admin-appleButton--chip"
          onClick={() => {
            setStoredProjectId(project.id);
            message.success(`已切换到项目：${project.company_name}`);
          }}
        >
          设为当前项目
        </Button>
        <Link to={`/projects/${project.id}/edit`} className="admin-inlineLink">
          编辑
        </Link>
        <Link to={`/projects/${project.id}/members`} className="admin-inlineLink">
          成员
        </Link>
      </Space>
    ),
  }));

  return (
    <AdminPage
      title="项目管理"
      description="管理项目、项目能力、项目成员和项目级配置，是后台治理的主入口。"
      tags={['项目能力', '项目成员', '项目隔离']}
      extra={
        currentUser?.system_role === 'super_admin' ? (
          <Button type="primary" href="/projects/new" className="admin-appleButton">
            新建项目
          </Button>
        ) : null
      }
    >
      <Card className="admin-listPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              项目列表
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              统一管理租户项目、能力开关和成员入口。先切换当前项目，再进入知识、日志和测试模块。
            </Typography.Text>
          </div>
          <div className="admin-listToolbar__aside">
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">项目数</span>
              <span className="admin-toolbarPill__value">{projects.length}</span>
            </div>
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">当前角色</span>
              <span className="admin-toolbarPill__value">{currentUser?.system_role ?? '访客'}</span>
            </div>
          </div>
        </div>
        <Table rowKey="key" loading={loading} pagination={false} columns={columns} dataSource={dataSource} />
      </Card>
    </AdminPage>
  );
}
