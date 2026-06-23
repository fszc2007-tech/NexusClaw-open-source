import { useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, Spin, Typography } from 'antd';
import { useParams } from '@umijs/max';
import { fetchProjectPersona } from '@/services/api';

export default function PersonaRealPage() {
  const { id = '1' } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchProjectPersona(id)
      .then((res) => {
        form.setFieldsValue(res.data || {});
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id, form]);

  return (
    <Card>
      <Typography.Title level={3}>项目人设配置（真实接口）</Typography.Title>
      {loading && <Spin />}
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      {!loading && !error && (
        <Form form={form} layout="vertical">
          <Form.Item label="助手名称" name="assistant_name">
            <Input />
          </Form.Item>
          <Form.Item label="助手身份" name="assistant_role">
            <Input />
          </Form.Item>
          <Form.Item label="开场语" name="opening_text">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item label="系统提示词" name="system_prompt">
            <Input.TextArea rows={6} />
          </Form.Item>
          <Button type="primary">保存</Button>
        </Form>
      )}
    </Card>
  );
}
