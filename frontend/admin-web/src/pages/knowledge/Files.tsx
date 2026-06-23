import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Descriptions, Modal, Popconfirm, Space, Table, Tag, Tooltip, Upload } from 'antd';
import { message } from '@/services/notify';
import { useParams } from '@umijs/max';

import AdminPage from '@/components/AdminPage';
import { useActiveProject } from '@/hooks/useActiveProject';
import {
  deleteKnowledgeFile,
  fetchFilePreview,
  fetchFiles,
  uploadKnowledgeFile,
  type FilePreview,
  type FileRecord,
} from '@/services/knowledgeApi';

function renderStatusTag(status: string) {
  const colorMap: Record<string, string> = {
    success: 'success',
    completed: 'success',
    generated: 'success',
    uploaded: 'processing',
    pending: 'default',
    skipped: 'default',
    failed: 'error',
  };

  return <Tag color={colorMap[status] || 'processing'}>{status}</Tag>;
}

function getAutoTaskStatus(file: FileRecord) {
  if (file.auto_process_task?.status) {
    return file.auto_process_task.status;
  }
  if (file.parse_status === 'failed') {
    return 'failed';
  }
  if (file.chunk_status === 'completed' || file.qa_status === 'generated') {
    return 'completed';
  }
  return 'pending';
}

function isProcessingFile(file: FileRecord) {
  return Boolean(file.auto_process_task && ['processing', 'pending'].includes(file.auto_process_task.status));
}

function getAutoImportMode(file: FileRecord) {
  const importMode = file.auto_process_task?.result_payload?.import_mode;
  return typeof importMode === 'string' ? importMode : null;
}

function getAutoProcessError(file: FileRecord) {
  const errorMessage = file.auto_process_task?.error_message;
  if (typeof errorMessage === 'string' && errorMessage.trim()) {
    return errorMessage;
  }
  return file.parse_error || null;
}

export default function KnowledgeFilesPage() {
  const { kbId } = useParams();
  const parsedKbId = Number(kbId);
  const { activeProject, activeProjectId } = useActiveProject();
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const loadFiles = async () => {
    if (!activeProjectId || !parsedKbId) {
      return;
    }

    try {
      setLoading(true);
      setFiles(await fetchFiles(activeProjectId, parsedKbId));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '文件列表加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadFiles();
  }, [activeProjectId, parsedKbId]);

  useEffect(() => {
    if (!files.some(isProcessingFile)) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void loadFiles();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [files, activeProjectId, parsedKbId]);

  const columns = useMemo(
    () => [
      { title: '文件名', dataIndex: 'fileName', key: 'fileName' },
      { title: '格式', dataIndex: 'format', key: 'format' },
      { title: '文件大小', dataIndex: 'fileSize', key: 'fileSize' },
      { title: '解析器', dataIndex: 'parserName', key: 'parserName' },
      { title: '解析状态', dataIndex: 'parseStatus', key: 'parseStatus' },
      { title: '自动处理', dataIndex: 'autoProcessStatus', key: 'autoProcessStatus' },
      { title: 'QA 状态', dataIndex: 'qaStatus', key: 'qaStatus' },
      { title: '切分状态', dataIndex: 'chunkStatus', key: 'chunkStatus' },
      { title: '解析摘要', dataIndex: 'parseSummary', key: 'parseSummary' },
      { title: '操作', dataIndex: 'actions', key: 'actions' },
    ],
    [],
  );

  const dataSource = files.map((file) => ({
    key: file.id,
    fileName: file.file_name,
    format: (
      <Space size={4} wrap>
        {file.file_ext ? <Tag>{file.file_ext.toUpperCase()}</Tag> : null}
        {file.mime_type ? <Tag>{file.mime_type}</Tag> : null}
      </Space>
    ),
    fileSize: `${(file.file_size / 1024).toFixed(1)} KB`,
    parserName: file.parser_name || '-',
    parseStatus: renderStatusTag(file.parse_status),
    autoProcessStatus: renderStatusTag(getAutoTaskStatus(file)),
    qaStatus: renderStatusTag(file.qa_status),
    chunkStatus: renderStatusTag(file.chunk_status),
    parseSummary: (
      <Space direction="vertical" size={2}>
        <span>
          blocks: {String(file.parse_meta?.block_count ?? '-')}
          {' / '}
          pages: {String(file.parse_meta?.page_count ?? '-')}
        </span>
        <span>
          route: {String(file.parse_meta?.route_kind ?? '-')}
          {' / '}
          chunk: {String(file.parse_meta?.chunk_strategy ?? '-')}
        </span>
        {getAutoImportMode(file) ? <Tag color="processing">模式 {getAutoImportMode(file)}</Tag> : null}
        {file.parse_meta?.ocr_score_avg ? <Tag color="processing">OCR {String(file.parse_meta.ocr_score_avg)}</Tag> : null}
        {getAutoProcessError(file) ? (
          <Tooltip title={getAutoProcessError(file) || ''}>
            <Tag color="error">失败原因</Tag>
          </Tooltip>
        ) : null}
      </Space>
    ),
    actions: (
      <Space>
        <Button
          type="link"
          size="small"
          onClick={async () => {
            if (!activeProjectId) {
              return;
            }
            try {
              setPreviewLoading(true);
              setPreview(await fetchFilePreview(activeProjectId, parsedKbId, file.id));
            } catch (error) {
              message.error(error instanceof Error ? error.message : '文件预览加载失败');
            } finally {
              setPreviewLoading(false);
            }
          }}
        >
          预览
        </Button>
        <Popconfirm
          title="确认删除这个文件吗？"
          description="会同时删除由该文件生成的知识条目。"
          onConfirm={async () => {
            if (!activeProjectId) {
              return;
            }
            try {
              await deleteKnowledgeFile(activeProjectId, parsedKbId, file.id);
              message.success('文件已删除');
              await loadFiles();
            } catch (error) {
              message.error(error instanceof Error ? error.message : '文件删除失败');
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

  return (
    <AdminPage
      title={`知识管理 · 文件库（KB ${kbId}）`}
      description={`管理文档上传与自动入库状态。当前项目：${activeProject?.company_name ?? '未选择'}`}
      tags={['文件解析', '自动处理', '自动入库']}
      extra={
        <Space direction="vertical" size={8} align="end">
          <Upload
            showUploadList={false}
            customRequest={async ({ file, onError, onSuccess }) => {
              if (!activeProjectId || !parsedKbId) {
                const error = new Error('请先选择项目后再上传文件');
                message.warning(error.message);
                onError?.(error);
                return;
              }

              try {
                const uploaded = await uploadKnowledgeFile(activeProjectId, parsedKbId, file as File);
                if (uploaded.parse_status === 'failed') {
                  message.warning(`文件 ${String((file as File).name)} 已上传，但解析失败`);
                } else {
                  message.success(`文件 ${String((file as File).name)} 已上传，系统正在自动处理`);
                }
                await loadFiles();
                onSuccess?.({}, new XMLHttpRequest());
              } catch (error) {
                const uploadError = error instanceof Error ? error : new Error('文件上传失败');
                message.error(uploadError.message);
                onError?.(uploadError);
              }
            }}
          >
            <Button type="primary">上传文件</Button>
          </Upload>
          <span style={{ color: 'rgba(0, 0, 0, 0.45)', fontSize: 13 }}>
            支持 txt / md / csv / html / docx / xlsx / pptx / pdf / 图片；扫描件优先走本地 PaddleOCR，复杂版面可再接 VL。
          </span>
        </Space>
      }
    >
      {!activeProjectId ? <Alert type="warning" showIcon message="请先在右上角选择项目后再管理文件库。" style={{ marginBottom: 16 }} /> : null}
      <Alert
        type="info"
        showIcon
        message="上传成功后系统会自动完成解析、切分入库、QA 生成，并对复杂表格 PDF 自动切换 table-aware 结构化入库。该页主要用于查看处理状态、预览结果和删除文件。"
        style={{ marginBottom: 16 }}
      />
      <Card>
        <Table rowKey="key" loading={loading} pagination={false} columns={columns} dataSource={dataSource} />
      </Card>
      <Modal
        title={preview?.file_name || '文件预览'}
        open={Boolean(preview)}
        confirmLoading={previewLoading}
        onCancel={() => setPreview(null)}
        footer={null}
        width={900}
      >
        {preview ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="文件名">{preview.file_name}</Descriptions.Item>
              <Descriptions.Item label="解析器">{preview.parser_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="MIME">{preview.mime_type || '-'}</Descriptions.Item>
              <Descriptions.Item label="Blocks">{String(preview.parse_meta?.block_count ?? '-')}</Descriptions.Item>
              <Descriptions.Item label="Pages">{String(preview.parse_meta?.page_count ?? '-')}</Descriptions.Item>
              <Descriptions.Item label="Route">{String(preview.parse_meta?.route_kind ?? '-')}</Descriptions.Item>
              <Descriptions.Item label="Chunk">{String(preview.parse_meta?.chunk_strategy ?? '-')}</Descriptions.Item>
              <Descriptions.Item label="失败原因">{preview.parse_error || '-'}</Descriptions.Item>
            </Descriptions>
            <Card size="small" styles={{ body: { maxHeight: 480, overflow: 'auto', whiteSpace: 'pre-wrap' } }}>
              {preview.content || '当前文件没有可预览文本。'}
            </Card>
          </Space>
        ) : null}
      </Modal>
    </AdminPage>
  );
}
