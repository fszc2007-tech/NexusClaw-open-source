import { useEffect } from 'react';
import { Alert, Button, Card, Form, Input, List, Space, Typography } from 'antd';
import { message } from '@/services/notify';

import AdminPage from '@/components/AdminPage';
import { useI18n } from '@/i18n/useI18n';
import { useActiveProject } from '@/hooks/useActiveProject';
import { fetchPromptSettings, updatePromptSettings } from '@/services/projectApi';

export default function PromptSettingsPage() {
  const [form] = Form.useForm();
  const { activeProject, activeProjectId } = useActiveProject();
  const { t, tList } = useI18n();

  useEffect(() => {
    const loadPrompt = async () => {
      if (!activeProjectId) {
        return;
      }

      try {
        const settings = await fetchPromptSettings(activeProjectId);
        form.setFieldsValue({
          prompt_template: settings.prompt_template,
        });
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('prompt.loadError'));
      }
    };

    void loadPrompt();
  }, [activeProjectId, form, t]);

  const handleSubmit = async (values: { prompt_template: string }) => {
    if (!activeProjectId) {
      return;
    }

    try {
      await updatePromptSettings(activeProjectId, values);
      message.success(t('prompt.saveSuccess'));
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('prompt.saveError'));
    }
  };

  return (
    <AdminPage
      title={t('prompt.title')}
      description={t('prompt.description', { projectName: activeProject?.company_name ?? t('layout.noProject') })}
      tags={tList('prompt.tags')}
    >
      {!activeProjectId ? <Alert type="warning" showIcon message={t('prompt.warning')} style={{ marginBottom: 16 }} /> : null}
      <div className="admin-settingsLayout">
        <Card className="admin-formPanel">
          <div className="admin-listToolbar admin-listToolbar--split">
            <div className="admin-listToolbar__main">
              <Typography.Title level={4} className="admin-listToolbar__title">
                {t('prompt.cardTitle')}
              </Typography.Title>
              <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
                管理项目主 Prompt 模板，控制系统角色、上下文拼接方式和回答边界。
              </Typography.Text>
            </div>
            <div className="admin-listToolbar__aside">
              <div className="admin-toolbarPill">
                <span className="admin-toolbarPill__label">当前项目</span>
                <span className="admin-toolbarPill__value">{activeProject?.company_name ?? t('layout.noProject')}</span>
              </div>
            </div>
          </div>
          <Form
            form={form}
            layout="vertical"
            className="admin-form"
            initialValues={{
              prompt_template: '你是一个专业的政务问答助手。\n参考资料：{qa}\n历史对话：{history}\n用户问题：{query}',
            }}
            onFinish={(values) => void handleSubmit(values)}
          >
            <Form.Item
              label={t('prompt.templateLabel')}
              name="prompt_template"
              rules={[{ required: true, message: t('prompt.templateRequired') }]}
              className="admin-formItem--full"
            >
              <Input.TextArea rows={12} />
            </Form.Item>
            <Form.Item label={t('prompt.versionNote')} className="admin-formItem--full">
              <Input placeholder={t('prompt.versionPlaceholder')} />
            </Form.Item>
            <div className="admin-formActions">
              <Button type="primary" htmlType="submit" className="admin-appleButton" disabled={!activeProjectId}>
                {t('prompt.save')}
              </Button>
              <Button className="admin-appleButton admin-appleButton--secondary" onClick={() => form.resetFields()}>
                {t('prompt.reset')}
              </Button>
            </div>
          </Form>
        </Card>
        <Card className="admin-notePanel">
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            <Typography.Text className="admin-notePanel__eyebrow">Prompt Variables</Typography.Text>
            <Typography.Title level={4} className="admin-notePanel__title">
              {t('prompt.variablesTitle')}
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-notePanel__description">
              保持变量占位符稳定，避免模板升级时把检索证据、会话历史或用户问题拼接链路打断。
            </Typography.Text>
          </Space>
          <List
            className="admin-noteList"
            dataSource={tList('prompt.variables')}
            renderItem={(item) => <List.Item>{item}</List.Item>}
          />
        </Card>
      </div>
    </AdminPage>
  );
}
