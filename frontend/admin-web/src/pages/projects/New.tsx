import { Button, Card, Checkbox, Form, Input, Typography } from 'antd';
import { message } from '@/services/notify';
import { useNavigate } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { createProject } from '@/services/projectApi';
import { setStoredProjectId } from '@/services/projectStore';

const capabilityOptions = ['多轮问答', '敏感检测', '政务相关校验', '知识树'];

function parseCapabilities(selected: string[]) {
  return {
    multi_turn: selected.includes('多轮问答'),
    sensitive_detection: selected.includes('敏感检测'),
    gov_domain_check: selected.includes('政务相关校验'),
    knowledge_tree: selected.includes('知识树'),
  };
}

export default function ProjectNewPage() {
  const [form] = Form.useForm();
  const navigate = useNavigate();

  const handleSubmit = async (values: {
    project_key: string;
    company_name: string;
    description?: string;
    logo_url?: string;
    capabilities?: string[];
  }) => {
    try {
      const project = await createProject({
        project_key: values.project_key,
        company_name: values.company_name,
        description: values.description,
        logo_url: values.logo_url,
        capabilities: parseCapabilities(values.capabilities || []),
      });
      setStoredProjectId(project.id);
      message.success('项目创建成功');
      navigate(`/projects/${project.id}/edit`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '项目创建失败');
    }
  };

  return (
    <AdminPage
      title="项目管理 · 新建项目"
      description="创建新项目并配置项目能力、管理员、简介与项目 logo。"
      tags={['项目初始化', '能力配置']}
    >
      <Card className="admin-formPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              新项目初始化
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              先创建租户项目，再逐步进入成员、知识库、开场语和 Prompt 配置。
            </Typography.Text>
          </div>
          <div className="admin-listToolbar__aside">
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">默认能力</span>
              <span className="admin-toolbarPill__value">多轮 / 敏感 / 校验</span>
            </div>
          </div>
        </div>
        <Form
          form={form}
          layout="vertical"
          className="admin-form"
          initialValues={{ capabilities: ['多轮问答', '敏感检测', '政务相关校验'] }}
          onFinish={(values) => void handleSubmit(values)}
        >
          <div className="admin-formGrid">
            <Form.Item label="项目 ID" name="project_key" rules={[{ required: true, message: '请输入项目 ID' }]}>
              <Input placeholder="例如：nexus_gov" />
            </Form.Item>
            <Form.Item label="公司名称" name="company_name" rules={[{ required: true, message: '请输入公司名称' }]}>
              <Input placeholder="请输入公司或部门名称" />
            </Form.Item>
            <Form.Item label="项目简介" name="description" className="admin-formItem--full">
              <Input.TextArea rows={4} placeholder="说明该项目面向的场景、人群和知识范围" />
            </Form.Item>
            <Form.Item label="项目 Logo" name="logo_url" className="admin-formItem--full">
              <Input placeholder="请输入 logo 地址" />
            </Form.Item>
            <Form.Item label="项目能力" name="capabilities" className="admin-formItem--full">
              <Checkbox.Group options={capabilityOptions} className="admin-choiceGroup" />
            </Form.Item>
          </div>
          <Typography.Text type="secondary" className="admin-formHint">
            创建完成后会自动进入该项目的编辑页，方便继续补充成员、知识与门户配置。
          </Typography.Text>
          <div className="admin-formActions">
            <Button type="primary" htmlType="submit" className="admin-appleButton">
              创建项目
            </Button>
            <Button className="admin-appleButton admin-appleButton--secondary" onClick={() => form.resetFields()}>
              重置
            </Button>
          </div>
        </Form>
      </Card>
    </AdminPage>
  );
}
