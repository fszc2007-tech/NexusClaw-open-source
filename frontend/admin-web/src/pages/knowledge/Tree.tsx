import { Button, Card, Col, List, Row, Space, Tag, Timeline } from 'antd';
import { useParams } from '@umijs/max';
import AdminPage from '@/components/AdminPage';

export default function KnowledgeTreePage() {
  const { kbId } = useParams();

  return (
    <AdminPage
      title={`知识管理 · 知识树（KB ${kbId}）`}
      description="用于拖拽编辑业务知识树、维护节点权重和条件列表，并管理历史版本、上传下载与发布。"
      tags={['版本管理', '节点权重', '条件列表']}
      extra={
        <Space>
          <Button>上传树 JSON</Button>
          <Button type="primary">发布当前版本</Button>
        </Space>
      }
    >
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card title="树结构编辑区">
            <Timeline
              items={[
                { color: 'blue', children: '提取公积金' },
                { color: 'gray', children: '租房' },
                { color: 'gray', children: '购房' },
                { color: 'green', children: '无发票租房（叶子节点）' },
              ]}
            />
            <Tag color="processing">后续接入拖拽画布、节点抽屉、规整与重置动作</Tag>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="版本与发布">
            <List
              dataSource={[
                { version: 'v5', status: '已发布' },
                { version: 'v4', status: '历史版本' },
                { version: 'v3', status: '历史版本' },
              ]}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <a key={`${item.version}-download`}>下载</a>,
                    <a key={`${item.version}-edit`}>编辑</a>,
                  ]}
                >
                  <Space>
                    <strong>{item.version}</strong>
                    <Tag color={item.status === '已发布' ? 'success' : 'default'}>{item.status}</Tag>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </AdminPage>
  );
}
