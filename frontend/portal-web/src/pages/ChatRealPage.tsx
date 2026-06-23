import { useMemo, useState } from 'react';
import { Alert, Button, Card, Input, List, Space, Typography } from 'antd';
import { askQuestion } from '@/services/api_real';

export default function ChatRealPage() {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([
    { role: 'assistant', content: '您好，我是 NexusClaw，請問您想諮詢哪項業務？' },
  ]);

  const sessionId = useMemo(() => 'sess_001', []);

  const handleSend = async () => {
    if (!input.trim()) return;
    const query = input.trim();
    setMessages((prev) => [...prev, { role: 'user', content: query }]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const res = await askQuestion({ session_id: sessionId, query, use_memory: true });
      setMessages((prev) => [...prev, { role: 'assistant', content: res.data?.answer || '暂无回答' }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : '请求失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <Typography.Title level={3}>NexusClaw 問答（真實接口）</Typography.Title>
      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
      <List
        dataSource={messages}
        renderItem={(item) => (
          <List.Item>
            <Typography.Text strong>{item.role === 'assistant' ? '助手' : '用户'}：</Typography.Text>
            <Typography.Text>{item.content}</Typography.Text>
          </List.Item>
        )}
      />
      <Space.Compact style={{ width: '100%', marginTop: 16 }}>
        <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="请输入您的问题" onPressEnter={handleSend} />
        <Button type="primary" loading={loading} onClick={handleSend}>发送</Button>
      </Space.Compact>
    </Card>
  );
}
