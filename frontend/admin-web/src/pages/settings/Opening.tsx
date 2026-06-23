import { useEffect } from 'react';
import { Alert, Button, Card, Form, Input, Radio, Space, Switch, Typography } from 'antd';
import { message } from '@/services/notify';

import AdminPage from '@/components/AdminPage';
import { useI18n } from '@/i18n/useI18n';
import { useActiveProject } from '@/hooks/useActiveProject';
import { fetchOpeningSettings, updateOpeningSettings } from '@/services/projectApi';

export default function OpeningSettingsPage() {
  const [form] = Form.useForm();
  const { activeProject, activeProjectId } = useActiveProject();
  const { t, tList } = useI18n();

  useEffect(() => {
    const loadSettings = async () => {
      if (!activeProjectId) {
        return;
      }

      try {
        const settings = await fetchOpeningSettings(activeProjectId);
        form.setFieldsValue({
          mode: settings.mode,
          opening_text: settings.opening_text,
          recommended_questions: settings.recommended_questions.join('\n'),
          hot_questions: settings.hot_questions.join('\n'),
          hot_policies: settings.hot_policies.join('\n'),
          enabled: settings.enabled,
        });
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('opening.loadError'));
      }
    };

    void loadSettings();
  }, [activeProjectId, form, t]);

  const handleSubmit = async (values: {
    mode: 'text' | 'card';
    opening_text?: string;
    recommended_questions?: string;
    hot_questions?: string;
    hot_policies?: string;
    enabled: boolean;
  }) => {
    if (!activeProjectId) {
      return;
    }

    try {
      await updateOpeningSettings(activeProjectId, {
        mode: values.mode,
        opening_text: values.opening_text,
        recommended_questions: values.recommended_questions?.split('\n').map((item) => item.trim()).filter(Boolean) || [],
        hot_questions: values.hot_questions?.split('\n').map((item) => item.trim()).filter(Boolean) || [],
        hot_policies: values.hot_policies?.split('\n').map((item) => item.trim()).filter(Boolean) || [],
        enabled: values.enabled,
      });
      message.success(t('opening.saveSuccess'));
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('opening.saveError'));
    }
  };

  return (
    <AdminPage
      title={t('opening.title')}
      description={t('opening.description', { projectName: activeProject?.company_name ?? t('layout.noProject') })}
      tags={tList('opening.tags')}
    >
      {!activeProjectId ? <Alert type="warning" showIcon message={t('opening.warning')} style={{ marginBottom: 16 }} /> : null}
      <div className="admin-settingsLayout">
        <Card className="admin-formPanel">
          <div className="admin-listToolbar admin-listToolbar--split">
            <div className="admin-listToolbar__main">
              <Typography.Title level={4} className="admin-listToolbar__title">
                首屏内容配置
              </Typography.Title>
              <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
                控制门户默认欢迎语、推荐问题和热点内容，决定用户首次进入时的引导方式。
              </Typography.Text>
            </div>
            <div className="admin-listToolbar__aside">
              <div className="admin-toolbarPill">
                <span className="admin-toolbarPill__label">当前项目</span>
                <span className="admin-toolbarPill__value">{activeProject?.company_name ?? t('layout.noProject')}</span>
              </div>
            </div>
          </div>
          <Form form={form} layout="vertical" className="admin-form" initialValues={{ mode: 'card', enabled: true }} onFinish={(values) => void handleSubmit(values)}>
            <div className="admin-formGrid">
              <Form.Item label={t('opening.mode')} name="mode" className="admin-formItem--full">
                <Radio.Group
                  className="admin-choiceGroup"
                  options={[
                    { label: t('opening.modeText'), value: 'text' },
                    { label: t('opening.modeCard'), value: 'card' },
                  ]}
                />
              </Form.Item>
              <Form.Item label={t('opening.text')} name="opening_text" className="admin-formItem--full">
                <Input.TextArea rows={4} placeholder={t('opening.textPlaceholder')} />
              </Form.Item>
              <Form.Item label={t('opening.recommendedQuestions')} name="recommended_questions" className="admin-formItem--full">
                <Input.TextArea rows={3} placeholder={t('opening.recommendedQuestionsPlaceholder')} />
              </Form.Item>
              <Form.Item label={t('opening.hotQuestions')} name="hot_questions" className="admin-formItem--full">
                <Input.TextArea rows={3} placeholder={t('opening.hotQuestionsPlaceholder')} />
              </Form.Item>
              <Form.Item label={t('opening.hotPolicies')} name="hot_policies" className="admin-formItem--full">
                <Input.TextArea rows={3} placeholder={t('opening.hotPoliciesPlaceholder')} />
              </Form.Item>
              <Form.Item label={t('opening.enabled')} name="enabled" valuePropName="checked">
                <Switch checkedChildren={t('opening.enabledOn')} unCheckedChildren={t('opening.enabledOff')} />
              </Form.Item>
            </div>
            <div className="admin-formActions">
              <Button type="primary" htmlType="submit" className="admin-appleButton" disabled={!activeProjectId}>
                {t('opening.save')}
              </Button>
              <Button className="admin-appleButton admin-appleButton--secondary" onClick={() => form.resetFields()}>
                {t('opening.reset')}
              </Button>
            </div>
          </Form>
        </Card>
        <Card className="admin-notePanel">
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            <Typography.Text className="admin-notePanel__eyebrow">Opening Rules</Typography.Text>
            <Typography.Title level={4} className="admin-notePanel__title">
              首屏建议
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-notePanel__description">
              推荐问题和热点项尽量短句化，减少首屏阅读负担，避免把门户首页做成说明文档。
            </Typography.Text>
            <div className="admin-noteMetric">
              <span className="admin-noteMetric__label">推荐问题</span>
              <span className="admin-noteMetric__value">建议 3 到 5 条</span>
            </div>
            <div className="admin-noteMetric">
              <span className="admin-noteMetric__label">热点内容</span>
              <span className="admin-noteMetric__value">优先高频事项与政策入口</span>
            </div>
            <div className="admin-noteMetric">
              <span className="admin-noteMetric__label">展示模式</span>
              <span className="admin-noteMetric__value">卡片模式更适合 PC 首屏</span>
            </div>
          </Space>
        </Card>
      </div>
    </AdminPage>
  );
}
