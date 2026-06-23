import { useMemo, useState } from 'react';
import { Alert, Button, Card, Input, List, Space, Spin, Tag, Typography } from 'antd';
import { askQuestion } from '@/services/api';

type MessageItem = {
  role: 'user' | 'assistant';
  content: string;
  sources?: { knowledge_id: number; title: string }[];
};

export default function ChatRealPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<MessageItem[]>([
    { role: 'assistant', content: '您好，我是 NexusClaw，請問您想諮詢哪項業務？' },
  ]);

  const sessionId = useMemo(() => 'sess_001', []);
  const projectId = '1';

  const onSend = async () => {
    const content = query.trim();
    if (!content) return;

    setError(null);
    setMessages((prev) => [...prev, { role: 'user', content }]);
    setQuery('');
    setLoading(true);

    try {
      const res = await askQuestion(projectId, {
        session_id: sessionId,
        query: content,
        use_memory: true,
      });

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.data?.answer || '暂无回答',
          sources: res.data?.sources || [],
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : '发送失败');
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
            <div style={{ width: '100%' }}>
              <Typography.Text strong>{item.role === 'assistant' ? '助手' : '用户'}：</Typography.Text>
              <Typography.Paragraph style={{ marginTop: 8, marginBottom: 8 }}>{item.content}</Typography.Paragraph>
              {item.sources && item.sources.length > 0 && (
                <Space wrap>
                  {item.sources.map((source) => (
                    <Tag key={source.knowledge_id}>{source.title}</Tag>
                  ))}
                </Space>
              )}
            </div>
          </List.Item>
        )}
      />
      {loading && <Spin style={{ marginBottom: 16 }} />}
      <Space.Compact style={{ width: '100%', marginTop: 16 }}>
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="请输入您的问题" onPressEnter={onSend} />
        <Button type="primary" onClick={onSend}>发送</Button>
      </Space.Compact>
    </Card>
  );
}
