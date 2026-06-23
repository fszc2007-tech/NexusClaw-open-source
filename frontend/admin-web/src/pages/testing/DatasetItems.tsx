import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Form, Input, Modal, Space, Table, Typography } from 'antd';
import { message } from '@/services/notify';
import { useParams } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { createDatasetItem, fetchDatasetItems, type DatasetItemRecord } from '@/services/testingApi';

export default function DatasetItemsPage() {
  const { id } = useParams();
  const datasetId = Number(id);
  const [items, setItems] = useState<DatasetItemRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const { activeProject, activeProjectId } = useActiveProject();

  const loadItems = async () => {
    if (!activeProjectId || !datasetId) {
      return;
    }
    try {
      setLoading(true);
      setItems(await fetchDatasetItems(activeProjectId, datasetId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '测试集条目加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadItems();
  }, [activeProjectId, datasetId]);

  const columns = useMemo(
    () => [
      { title: '问题', dataIndex: 'query', key: 'query' },
      { title: '参考答案', dataIndex: 'refAnswer', key: 'refAnswer' },
      { title: '标签', dataIndex: 'tags', key: 'tags' },
    ],
    [],
  );

  const dataSource = items.map((item) => ({
    key: item.id,
    query: item.query,
    refAnswer: item.ref_answer || '-',
    tags: item.tags || '-',
  }));

  const handleCreate = async (values: {
    query: string;
    ref_answer?: string;
    expected_knowledge_ids?: string;
    tags?: string;
  }) => {
    if (!activeProjectId || !datasetId) {
      return;
    }
    try {
      await createDatasetItem(activeProjectId, datasetId, values);
      message.success('测试条目创建成功');
      setModalOpen(false);
      form.resetFields();
      await loadItems();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '测试条目创建失败');
    }
  };

  return (
    <AdminPage
      title={`测试管理 · 测试集条目（#${id}）`}
      description={`维护测试集中的 query / ref_answer 明细。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['query', 'ref_answer']}
      extra={
        <Space>
          <Button className="admin-appleButton admin-appleButton--secondary">上传 Excel</Button>
          <Button type="primary" className="admin-appleButton" disabled={!activeProjectId} onClick={() => setModalOpen(true)}>
            新建条目
          </Button>
        </Space>
      }
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再管理测试条目。" style={{ marginBottom: 16 }} /> : null}
      <Card className="admin-listPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              测试样本条目
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              维护单条 query、参考答案和期望命中的知识范围，用于批量回归评测与效果复核。
            </Typography.Text>
          </div>
          <div className="admin-listToolbar__aside">
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">条目数</span>
              <span className="admin-toolbarPill__value">{items.length}</span>
            </div>
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">数据集</span>
              <span className="admin-toolbarPill__value">#{id}</span>
            </div>
          </div>
        </div>
        <Table rowKey="key" loading={loading} pagination={false} columns={columns} dataSource={dataSource} />
      </Card>
      <Modal
        title="新建测试条目"
        className="admin-glassModal"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        destroyOnHidden
        okButtonProps={{ className: 'admin-appleButton' }}
        cancelButtonProps={{ className: 'admin-appleButton admin-appleButton--secondary' }}
      >
        <Form form={form} layout="vertical" onFinish={(values) => void handleCreate(values)}>
          <Form.Item label="问题" name="query" rules={[{ required: true, message: '请输入问题' }]}>
            <Input.TextArea rows={3} placeholder="例如：港澳通行证怎么办理？" />
          </Form.Item>
          <Form.Item label="参考答案" name="ref_answer">
            <Input.TextArea rows={4} placeholder="请输入期望参考答案" />
          </Form.Item>
          <Form.Item label="期望知识 ID" name="expected_knowledge_ids">
            <Input placeholder="例如：12,15,18" />
          </Form.Item>
          <Form.Item label="标签" name="tags">
            <Input placeholder="例如：通行证,出入境" />
          </Form.Item>
        </Form>
      </Modal>
    </AdminPage>
  );
}
