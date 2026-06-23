import { Button, Card, Form, Input, Typography } from 'antd';

export default function PersonaPage() {
  return (
    <Card>
      <Typography.Title level={3}>项目人设配置</Typography.Title>
      <Form layout="vertical" initialValues={{ assistantName: 'NexusClaw', assistantRole: '政务问答助手' }}>
        <Form.Item label="助手名称" name="assistantName">
          <Input />
        </Form.Item>
        <Form.Item label="助手身份" name="assistantRole">
          <Input />
        </Form.Item>
        <Form.Item label="开场语" name="openingText">
          <Input.TextArea rows={3} placeholder="您好，我是 NexusClaw，請問您想諮詢哪項業務？" />
        </Form.Item>
        <Form.Item label="系统提示词" name="systemPrompt">
          <Input.TextArea rows={6} placeholder="请输入项目级 system prompt" />
        </Form.Item>
        <Button type="primary">保存</Button>
      </Form>
    </Card>
  );
}
