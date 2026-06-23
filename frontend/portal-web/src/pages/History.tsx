import { useEffect, useMemo, useState } from 'react';
import { Card, Empty, List, Select, Space, Typography } from 'antd';
import { message } from '@/services/notify';

import PortalPage from '@/components/PortalPage';
import { fetchSessions, type ChatSessionSummary } from '@/services/chatApi';
import { fetchProjects, type ProjectRecord } from '@/services/projectApi';

export default function HistoryPage() {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<number>();
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const items = await fetchProjects();
        setProjects(items);
        if (items[0]) {
          setActiveProjectId(items[0].id);
        }
      } catch (error) {
        message.error(error instanceof Error ? error.message : '项目列表加载失败');
      }
    };

    void loadProjects();
  }, []);

  useEffect(() => {
    const loadSessions = async () => {
      if (!activeProjectId) {
        return;
      }

      try {
        setSessions(await fetchSessions(activeProjectId));
      } catch (error) {
        message.error(error instanceof Error ? error.message : '历史会话加载失败');
      }
    };

    void loadSessions();
  }, [activeProjectId]);

  const projectOptions = useMemo(
    () =>
      projects.map((project) => ({
        value: project.id,
        label: `${project.company_name} (${project.project_key})`,
      })),
    [projects],
  );

  return (
    <PortalPage
      title="历史会话"
      description="查看 NexusClaw 的历史问答会话与上下文记录。"
    >
      <div className="portal-toolbar">
        <Typography.Text type="secondary">当前项目</Typography.Text>
        <Select
          style={{ width: 280 }}
          placeholder="请选择项目"
          value={activeProjectId}
          options={projectOptions}
          onChange={setActiveProjectId}
        />
      </div>

      {sessions.length ? (
        <List
          className="portal-session-list"
          dataSource={sessions}
          split={false}
          renderItem={(item) => (
            <List.Item>
              <div className="portal-history-item">
                <Space direction="vertical" size={4}>
                  <Typography.Text strong>{item.title}</Typography.Text>
                  <Typography.Text type="secondary">{item.session_id}</Typography.Text>
                  {item.summary ? <Typography.Text type="secondary">{item.summary}</Typography.Text> : null}
                  <Typography.Text>{item.last_query || '暂无最近问题'}</Typography.Text>
                  <Typography.Text type="secondary">{item.last_answer || '暂无最近回答'}</Typography.Text>
                </Space>
              </div>
            </List.Item>
          )}
        />
      ) : (
        <Card bordered={false}>
          <Empty description="当前项目暂无历史会话" />
        </Card>
      )}
    </PortalPage>
  );
}
