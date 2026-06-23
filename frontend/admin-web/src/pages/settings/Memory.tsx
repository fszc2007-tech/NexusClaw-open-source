import { useEffect, useState } from 'react';
import { Alert, Button, Card, Form, InputNumber, Radio, Space, Switch, Typography } from 'antd';
import { message } from '@/services/notify';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { useI18n } from '@/i18n/useI18n';
import type { MemorySettings } from '@/services/projectApi';
import { fetchMemorySettings, updateMemorySettings } from '@/services/projectApi';

export default function MemorySettingsPage() {
  const [form] = Form.useForm();
  const [existingSettings, setExistingSettings] = useState<MemorySettings | null>(null);
  const { activeProject, activeProjectId } = useActiveProject();
  const { t, tList } = useI18n();

  useEffect(() => {
    const loadSettings = async () => {
      if (!activeProjectId) {
        return;
      }

      try {
        const settings = await fetchMemorySettings(activeProjectId);
        setExistingSettings(settings);
        form.setFieldsValue({
          capability_memory: settings.capability_memory,
          memory_scope: settings.memory_scope,
          memory_ttl_days: settings.memory_ttl_days,
        });
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('memory.loadError'));
      }
    };

    void loadSettings();
  }, [activeProjectId, form, t]);

  const handleSubmit = async (values: {
    capability_memory: boolean;
    memory_scope: 'off' | 'session_only';
    memory_ttl_days: number;
  }) => {
    if (!activeProjectId) {
      return;
    }

    try {
      const savedSettings = await updateMemorySettings(activeProjectId, {
        capability_memory: values.capability_memory,
        memory_scope: values.capability_memory ? values.memory_scope : 'off',
        memory_ttl_days: values.memory_ttl_days,
        preference_memory_enabled: false,
        enabled_scene_keys_json: existingSettings?.enabled_scene_keys_json || [],
        scene_entry_mode: existingSettings?.scene_entry_mode || 'chat',
        scene_runtime_config_json: existingSettings?.scene_runtime_config_json || {},
      });
      setExistingSettings(savedSettings);
      message.success(t('memory.saveSuccess'));
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('memory.saveError'));
    }
  };

  return (
    <AdminPage
      title={t('memory.title')}
      description={t('memory.description', { projectName: activeProject?.company_name ?? t('layout.noProject') })}
      tags={tList('memory.tags')}
    >
      {!activeProjectId ? <Alert type="warning" showIcon message={t('memory.warning')} style={{ marginBottom: 16 }} /> : null}
      <div className="admin-settingsLayout">
        <Card className="admin-formPanel">
          <div className="admin-listToolbar admin-listToolbar--split">
            <div className="admin-listToolbar__main">
              <Typography.Title level={4} className="admin-listToolbar__title">
                {t('memory.cardTitle')}
              </Typography.Title>
              <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
                控制多轮记忆的启用范围、有效期和当前项目的会话上下文保留策略。
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
              capability_memory: true,
              memory_scope: 'session_only',
              memory_ttl_days: 7,
            }}
            onFinish={(values) => void handleSubmit(values)}
          >
            <Form.Item label={t('memory.enabled')} name="capability_memory" valuePropName="checked">
              <Switch checkedChildren={t('memory.enabledOn')} unCheckedChildren={t('memory.enabledOff')} />
            </Form.Item>
            <Form.Item shouldUpdate={(prev, next) => prev.capability_memory !== next.capability_memory} noStyle>
              {({ getFieldValue }) => {
                const enabled = Boolean(getFieldValue('capability_memory'));
                return (
                  <>
                    <Form.Item label={t('memory.scope')} name="memory_scope" className="admin-formItem--full">
                      <Radio.Group
                        className="admin-choiceGroup"
                        disabled={!enabled}
                        options={[
                          { label: t('memory.scopeOff'), value: 'off' },
                          { label: t('memory.scopeSessionOnly'), value: 'session_only' },
                        ]}
                      />
                    </Form.Item>
                    <Form.Item
                      label={t('memory.ttlDays')}
                      name="memory_ttl_days"
                      rules={[{ required: true, message: t('memory.ttlRequired') }]}
                    >
                      <InputNumber min={1} max={365} style={{ width: '100%' }} disabled={!enabled} />
                    </Form.Item>
                  </>
                );
              }}
            </Form.Item>
            <div className="admin-formActions">
              <Button type="primary" htmlType="submit" className="admin-appleButton" disabled={!activeProjectId}>
                {t('memory.save')}
              </Button>
              <Button className="admin-appleButton admin-appleButton--secondary" onClick={() => form.resetFields()}>
                {t('memory.reset')}
              </Button>
            </div>
          </Form>
        </Card>
        <Card className="admin-notePanel">
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            <Typography.Text className="admin-notePanel__eyebrow">Memory Policy</Typography.Text>
            <Typography.Title level={4} className="admin-notePanel__title">
              {t('memory.noticeTitle')}
            </Typography.Title>
            <Typography.Text className="admin-notePanel__description">{t('memory.noticeBody')}</Typography.Text>
            <Typography.Text type="secondary">{t('memory.noticeSecondary')}</Typography.Text>
            <div className="admin-noteMetric">
              <span className="admin-noteMetric__label">推荐范围</span>
              <span className="admin-noteMetric__value">Session Only</span>
            </div>
            <div className="admin-noteMetric">
              <span className="admin-noteMetric__label">推荐 TTL</span>
              <span className="admin-noteMetric__value">7 到 30 天</span>
            </div>
          </Space>
        </Card>
      </div>
    </AdminPage>
  );
}
