import { useEffect } from 'react';
import { Button, Card, Checkbox, Form, Input, Space, Typography } from 'antd';
import { message } from '@/services/notify';
import { Link, useNavigate, useParams } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { fetchProject, updateProject } from '@/services/projectApi';
import { setStoredProjectId } from '@/services/projectStore';

const capabilityOptions = ['多轮问答', '敏感检测', '政务相关校验', '知识树'];

function normalizeCapabilities(values: string[]) {
  return {
    multi_turn: values.includes('多轮问答'),
    sensitive_detection: values.includes('敏感检测'),
    gov_domain_check: values.includes('政务相关校验'),
    knowledge_tree: values.includes('知识树'),
  };
}

export default function ProjectEditPage() {
  const { id } = useParams();
  const [form] = Form.useForm();
  const navigate = useNavigate();

  useEffect(() => {
    const loadProject = async () => {
      if (!id) {
        return;
      }

      try {
        const project = await fetchProject(Number(id));
        setStoredProjectId(project.id);
        form.setFieldsValue({
          project_key: project.project_key,
          company_name: project.company_name,
          description: project.description,
          logo_url: project.logo_url,
          capabilities: capabilityOptions.filter((option) => {
            if (option === '多轮问答') {
              return project.capabilities.multi_turn;
            }
            if (option === '敏感检测') {
              return project.capabilities.sensitive_detection;
            }
            if (option === '政务相关校验') {
              return project.capabilities.gov_domain_check;
            }
            return project.capabilities.knowledge_tree;
          }),
        });
      } catch (error) {
        message.error(error instanceof Error ? error.message : '项目详情加载失败');
      }
    };

    void loadProject();
  }, [form, id]);

  const handleSubmit = async (values: {
    company_name: string;
    description?: string;
    logo_url?: string;
    capabilities?: string[];
  }) => {
    if (!id) {
      return;
    }

    try {
      await updateProject(Number(id), {
        company_name: values.company_name,
        description: values.description,
        logo_url: values.logo_url,
        capabilities: normalizeCapabilities(values.capabilities || []),
      });
      setStoredProjectId(Number(id));
      message.success('项目已更新');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '项目更新失败');
    }
  };

  return (
    <AdminPage
      title={`项目管理 · 编辑项目（#${id}）`}
      description="编辑公司名称、简介、项目能力和项目 logo，后续这里也会承接项目级门户配置跳转。"
      tags={['项目配置', '能力开关']}
    >
      <Card className="admin-formPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              项目基础配置
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              管理项目名称、品牌信息和能力开关。这里决定后续知识库、门户和治理能力的默认边界。
            </Typography.Text>
          </div>
          <div className="admin-listToolbar__aside">
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">项目编号</span>
              <span className="admin-toolbarPill__value">#{id}</span>
            </div>
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">后续入口</span>
              <span className="admin-toolbarPill__value">成员 / 设置</span>
            </div>
          </div>
        </div>
        <Form form={form} layout="vertical" className="admin-form" onFinish={(values) => void handleSubmit(values)}>
          <div className="admin-formGrid">
            <Form.Item label="项目 ID" name="project_key">
            <Input disabled />
            </Form.Item>
            <Form.Item label="公司名称" name="company_name" rules={[{ required: true, message: '请输入公司名称' }]}>
              <Input placeholder="请输入公司或部门名称" />
            </Form.Item>
            <Form.Item label="项目简介" name="description" className="admin-formItem--full">
              <Input.TextArea rows={4} placeholder="描述这个项目的服务对象、知识范围或业务边界" />
            </Form.Item>
            <Form.Item label="项目 Logo" name="logo_url" className="admin-formItem--full">
              <Input placeholder="请输入 logo 地址" />
            </Form.Item>
            <Form.Item label="项目能力" name="capabilities" className="admin-formItem--full">
              <Checkbox.Group options={capabilityOptions} className="admin-choiceGroup" />
            </Form.Item>
          </div>
          <Typography.Text type="secondary" className="admin-formHint">
            能力开关会直接影响对话、多轮记忆、政务校验和知识树模块的可用范围。
          </Typography.Text>
          <div className="admin-formActions">
            <Button type="primary" htmlType="submit" className="admin-appleButton">
              保存变更
            </Button>
            <Button className="admin-appleButton admin-appleButton--secondary" onClick={() => navigate('/projects')}>
              返回列表
            </Button>
            <Link to={`/projects/${id}/members`} className="admin-inlineLink">
              查看成员
            </Link>
          </div>
        </Form>
      </Card>
    </AdminPage>
  );
}
