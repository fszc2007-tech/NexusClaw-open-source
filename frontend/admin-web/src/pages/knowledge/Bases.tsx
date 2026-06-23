import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Checkbox, Form, Input, Modal, Popconfirm, Space, Table, Tag, Typography } from 'antd';
import { message } from '@/services/notify';
import { Link } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  fetchKnowledgeBases,
  updateKnowledgeBase,
  type KnowledgeBaseRecord,
} from '@/services/knowledgeApi';

export default function KnowledgeBasesPage() {
  const [bases, setBases] = useState<KnowledgeBaseRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingBase, setEditingBase] = useState<KnowledgeBaseRecord | null>(null);
  const [form] = Form.useForm();
  const { activeProject, activeProjectId } = useActiveProject();

  const loadBases = async () => {
    if (!activeProjectId) {
      return;
    }

    try {
      setLoading(true);
      setBases(await fetchKnowledgeBases(activeProjectId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '知识库列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadBases();
  }, [activeProjectId]);

  const columns = useMemo(
    () => [
      { title: '知识库名称', dataIndex: 'name', key: 'name' },
      { title: '描述', dataIndex: 'description', key: 'description' },
      { title: '默认', dataIndex: 'isDefault', key: 'isDefault' },
      { title: '操作', dataIndex: 'actions', key: 'actions' },
    ],
    [],
  );

  const dataSource = bases.map((base) => ({
    key: base.id,
    name: base.name,
    description: base.description || '-',
    isDefault: base.is_default ? <Tag color="success">默认</Tag> : <Tag>否</Tag>,
    actions: (
      <Space>
        <Button
          type="link"
          size="small"
          onClick={() => {
            setEditingBase(base);
            form.setFieldsValue(base);
            setModalOpen(true);
          }}
        >
          编辑
        </Button>
        <Link to={`/knowledge/bases/${base.id}/items`}>知识条目</Link>
        <Link to={`/knowledge/bases/${base.id}/tree`}>知识树</Link>
        <Link to={`/knowledge/bases/${base.id}/files`}>文件库</Link>
        <Popconfirm
          title="确认删除这个知识库吗？"
          description="会同时删除该知识库下的文件和知识条目。"
          onConfirm={async () => {
            if (!activeProjectId) {
              return;
            }
            try {
              await deleteKnowledgeBase(activeProjectId, base.id);
              message.success('知识库已删除');
              await loadBases();
            } catch (error) {
              message.error(error instanceof Error ? error.message : '知识库删除失败');
            }
          }}
        >
          <Button type="link" size="small" danger>
            删除
          </Button>
        </Popconfirm>
      </Space>
    ),
  }));

  const handleSubmit = async (values: { name: string; description?: string; is_default?: boolean }) => {
    if (!activeProjectId) {
      return;
    }

    try {
      if (editingBase) {
        await updateKnowledgeBase(activeProjectId, editingBase.id, values);
        message.success('知识库更新成功');
      } else {
        await createKnowledgeBase(activeProjectId, values);
        message.success('知识库创建成功');
      }
      setModalOpen(false);
      setEditingBase(null);
      form.resetFields();
      await loadBases();
    } catch (error) {
      message.error(error instanceof Error ? error.message : editingBase ? '知识库更新失败' : '知识库创建失败');
    }
  };

  return (
    <AdminPage
      title="知识管理 · 知识库"
      description={`按项目维度管理知识库。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['默认知识库', '项目隔离']}
      extra={
        <Button
          type="primary"
          className="admin-appleButton"
          onClick={() => {
            setEditingBase(null);
            form.resetFields();
            setModalOpen(true);
          }}
          disabled={!activeProjectId}
        >
          新建知识库
        </Button>
      }
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再管理知识库。" style={{ marginBottom: 16 }} /> : null}
      <Card className="admin-listPanel">
        <div className="admin-listToolbar">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              知识库列表
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              管理项目下的知识空间、默认库与内容入口。
            </Typography.Text>
          </div>
        </div>
        <Table rowKey="key" loading={loading} pagination={false} columns={columns} dataSource={dataSource} />
      </Card>
      <Modal
        title={editingBase ? `编辑知识库（#${editingBase.id}）` : '新建知识库'}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          setEditingBase(null);
        }}
        onOk={() => form.submit()}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={(values) => void handleSubmit(values)}>
          <Form.Item label="知识库名称" name="name" rules={[{ required: true, message: '请输入知识库名称' }]}>
            <Input placeholder="例如：公积金知识库" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入知识库说明" />
          </Form.Item>
          <Form.Item name="is_default" valuePropName="checked">
            <Checkbox>设为默认知识库</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </AdminPage>
  );
}
