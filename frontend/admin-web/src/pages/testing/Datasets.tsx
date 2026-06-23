import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Form, Input, Modal, Space, Table, Tag, Typography } from 'antd';
import { message } from '@/services/notify';
import { Link } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import { createDataset, fetchDatasets, type DatasetRecord } from '@/services/testingApi';

export default function TestingDatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const { activeProject, activeProjectId } = useActiveProject();

  const loadDatasets = async () => {
    if (!activeProjectId) {
      return;
    }
    try {
      setLoading(true);
      setDatasets(await fetchDatasets(activeProjectId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '测试集列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDatasets();
  }, [activeProjectId]);

  const columns = useMemo(
    () => [
      { title: '名称', dataIndex: 'name', key: 'name' },
      { title: '描述', dataIndex: 'description', key: 'description' },
      { title: '条目数', dataIndex: 'count', key: 'count' },
      { title: '状态', dataIndex: 'status', key: 'status' },
      { title: '操作', dataIndex: 'actions', key: 'actions' },
    ],
    [],
  );

  const dataSource = datasets.map((dataset) => ({
    key: dataset.id,
    name: dataset.name,
    description: dataset.description || '-',
    count: dataset.item_count,
    status: <Tag color={dataset.status === 'active' ? 'success' : 'default'}>{dataset.status}</Tag>,
    actions: (
      <Link to={`/testing/datasets/${dataset.id}/items`} className="admin-inlineLink">
        查看条目
      </Link>
    ),
  }));

  const handleCreate = async (values: { name: string; description?: string }) => {
    if (!activeProjectId) {
      return;
    }
    try {
      await createDataset(activeProjectId, values);
      message.success('测试集创建成功');
      setModalOpen(false);
      form.resetFields();
      await loadDatasets();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '测试集创建失败');
    }
  };

  return (
    <AdminPage
      title="测试管理 · 测试集"
      description={`管理测试问题与参考答案数据集。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['Excel 导入', '样本维护', '数据集管理']}
      extra={
        <Space>
          <Button className="admin-appleButton admin-appleButton--secondary">下载模板</Button>
          <Button type="primary" className="admin-appleButton" disabled={!activeProjectId} onClick={() => setModalOpen(true)}>
            新建测试集
          </Button>
        </Space>
      }
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再管理测试集。" style={{ marginBottom: 16 }} /> : null}
      <Card className="admin-listPanel">
        <div className="admin-listToolbar admin-listToolbar--split">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              测试集列表
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              管理批量评测样本、参考答案和导入模板，为回归测试与效果比对提供统一基线。
            </Typography.Text>
          </div>
          <div className="admin-listToolbar__aside">
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">当前项目</span>
              <span className="admin-toolbarPill__value">{activeProject?.company_name ?? '未选择'}</span>
            </div>
            <div className="admin-toolbarPill">
              <span className="admin-toolbarPill__label">测试集</span>
              <span className="admin-toolbarPill__value">{datasets.length}</span>
            </div>
          </div>
        </div>
        <Table rowKey="key" loading={loading} pagination={false} columns={columns} dataSource={dataSource} />
      </Card>
      <Modal
        title="新建测试集"
        className="admin-glassModal"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        destroyOnHidden
        okButtonProps={{ className: 'admin-appleButton' }}
        cancelButtonProps={{ className: 'admin-appleButton admin-appleButton--secondary' }}
      >
        <Form form={form} layout="vertical" onFinish={(values) => void handleCreate(values)}>
          <Form.Item label="测试集名称" name="name" rules={[{ required: true, message: '请输入测试集名称' }]}>
            <Input placeholder="例如：政务咨询样本集" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入测试集说明" />
          </Form.Item>
        </Form>
      </Modal>
    </AdminPage>
  );
}
