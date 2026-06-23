import { useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Typography } from 'antd';
import { message } from '@/services/notify';
import { useNavigate, useParams } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { useI18n } from '@/i18n/useI18n';
import {
  createKnowledgeItem,
  fetchKnowledgeItem,
  publishKnowledgeItem,
  updateKnowledgeItem,
} from '@/services/knowledgeApi';

function parseKeywords(value?: string) {
  return (value || '')
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function KnowledgeEditorPage() {
  const { kbId, id } = useParams();
  const isEditing = Boolean(id);
  const parsedKbId = Number(kbId);
  const parsedId = Number(id);
  const navigate = useNavigate();
  const { activeProject, activeProjectId } = useActiveProject();
  const { t } = useI18n();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const loadDetail = async () => {
      if (!activeProjectId || !parsedKbId || !parsedId || !isEditing) {
        return;
      }
      try {
        setLoading(true);
        const detail = await fetchKnowledgeItem(activeProjectId, parsedKbId, parsedId);
        form.setFieldsValue({
          document_name: detail.document_name,
          title: detail.title,
          keywords: detail.keywords?.join(', '),
          content: detail.content,
          source_url: detail.source_url,
          source_org: detail.source_org,
          review_due_at: detail.review_due_at,
          review_sla_days: detail.review_sla_days,
        });
      } catch (error) {
        message.error(error instanceof Error ? error.message : '知识详情加载失败');
      } finally {
        setLoading(false);
      }
    };

    void loadDetail();
  }, [activeProjectId, form, isEditing, parsedId, parsedKbId]);

  const submit = async (publishAfterSave: boolean) => {
    if (!activeProjectId || !parsedKbId) {
      return;
    }

    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        document_name: values.document_name,
        title: values.title,
        keywords: parseKeywords(values.keywords),
        content: values.content,
        source_url: values.source_url,
        source_org: values.source_org,
        review_due_at: values.review_due_at,
        review_sla_days: values.review_sla_days ? Number(values.review_sla_days) : undefined,
        status: publishAfterSave ? 'active' : 'editing',
      };
      const result = isEditing
        ? await updateKnowledgeItem(activeProjectId, parsedKbId, parsedId, payload)
        : await createKnowledgeItem(activeProjectId, parsedKbId, payload);

      if (publishAfterSave && result.status !== 'active') {
        await publishKnowledgeItem(activeProjectId, parsedKbId, result.id);
      }

      message.success(publishAfterSave ? '知识已保存并发布' : '知识草稿已保存');
      navigate(`/knowledge/bases/${kbId}/items`);
    } catch (error) {
      if (error instanceof Error && error.message) {
        message.error(error.message);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminPage
      title={isEditing ? `编辑知识（#${id}）` : `新建知识（KB ${kbId}）`}
      description={`配置文档名称、标题、关键词与正文内容。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['知识编辑', '相似问题', '状态流转']}
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再编辑知识。" style={{ marginBottom: 16 }} /> : null}
      <Card>
        <Form form={form} layout="vertical">
          <Form.Item label="文档名称" name="document_name">
            <Input />
          </Form.Item>
          <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入标题' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="关键词" name="keywords">
            <Input placeholder="多个关键词用逗号分隔" />
          </Form.Item>
          <Form.Item label={t('knowledgeEditor.sourceUrl')} name="source_url">
            <Input />
          </Form.Item>
          <Form.Item label={t('knowledgeEditor.sourceOrg')} name="source_org">
            <Input />
          </Form.Item>
          <Form.Item label={t('knowledgeEditor.reviewDueAt')} name="review_due_at">
            <Input placeholder="2026-04-24T18:00:00" />
          </Form.Item>
          <Form.Item label={t('knowledgeEditor.reviewSlaDays')} name="review_sla_days">
            <Input placeholder="90" />
          </Form.Item>
          <Form.Item label="知识内容" name="content" rules={[{ required: true, message: '请输入知识内容' }]}>
            <Input.TextArea rows={10} placeholder="请输入知识正文内容" />
          </Form.Item>
          <Space>
            <Button type="primary" loading={saving || loading} disabled={!activeProjectId} onClick={() => void submit(false)}>
              保存草稿
            </Button>
            <Button loading={saving || loading} disabled={!activeProjectId} onClick={() => void submit(true)}>
              保存并上线
            </Button>
          </Space>
          <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
            文件库里“QA 生成”和“切分入库”产出的结果，也会以知识条目的形式出现在这里，支持继续编辑。
          </Typography.Paragraph>
        </Form>
      </Card>
    </AdminPage>
  );
}
