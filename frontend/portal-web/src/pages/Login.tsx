import { Button, Card, Form, Input, Typography } from 'antd';

export default function LoginPage() {
  return (
    <div className="portal-shell portal-shell--centered">
      <div className="portal-login-card">
        <Card className="portal-card">
          <Typography.Text className="portal-page__eyebrow">NexusClaw Portal</Typography.Text>
          <Typography.Title level={2} style={{ marginTop: 10, marginBottom: 8 }}>
            NexusClaw 登录
          </Typography.Title>
          <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
            登录后进入 NexusClaw 问答与历史会话页面。
          </Typography.Text>
          <Form layout="vertical">
            <Form.Item label="用户名" name="username">
              <Input placeholder="请输入用户名" />
            </Form.Item>
            <Form.Item label="密码" name="password">
              <Input.Password placeholder="请输入密码" />
            </Form.Item>
            <Button type="primary" block>
              登录
            </Button>
          </Form>
        </Card>
      </div>
    </div>
  );
}
