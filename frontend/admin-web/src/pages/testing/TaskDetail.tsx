import { Button, Card, Descriptions, Space, Table, Tag, Typography } from 'antd';
import { useParams } from '@umijs/max';
import AdminPage from '@/components/AdminPage';

const columns = [
  { title: '问题', dataIndex: 'query', key: 'query' },
  { title: '机跑答案', dataIndex: 'answer', key: 'answer' },
  { title: '评测结果', dataIndex: 'result', key: 'result' },
];

export default function TestingTaskDetailPage() {
  const { id } = useParams();

  return (
    <AdminPage
      title={`测试管理 · 任务详情（#${id}）`}
      description="查看任务汇总、单条机跑结果、自动评测结果和人工复核入口。"
      tags={['结果明细', '人工复核']}
      extra={
        <Space wrap>
          <Button className="admin-appleButton admin-appleButton--secondary">导出结果</Button>
          <Button type="primary" className="admin-appleButton">
            重新运行
          </Button>
        </Space>
      }
    >
      <Card className="admin-listPanel">
        <div className="admin-listToolbar">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              任务概览
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              先确认任务状态、评测类型和样本规模，再进入结果明细做人工复核。
            </Typography.Text>
          </div>
        </div>
        <div className="admin-detailGrid">
          <div className="admin-detailStat">
            <span className="admin-detailStat__label">任务名称</span>
            <Typography.Title level={3} className="admin-detailStat__value">
              四月检索效果测试
            </Typography.Title>
            <span className="admin-detailStat__hint">用于检查四月版本的检索召回与可答复率。</span>
          </div>
          <div className="admin-detailStat">
            <span className="admin-detailStat__label">运行状态</span>
            <div className="admin-detailStat__tagWrap">
              <Tag color="processing">运行中</Tag>
            </div>
            <span className="admin-detailStat__hint">系统正在持续写入机跑结果，可随时刷新查看。</span>
          </div>
          <div className="admin-detailStat">
            <span className="admin-detailStat__label">数据集</span>
            <Typography.Title level={3} className="admin-detailStat__value">
              政务咨询样本集
            </Typography.Title>
            <span className="admin-detailStat__hint">覆盖高频办事问答与检索测试样本。</span>
          </div>
          <div className="admin-detailStat">
            <span className="admin-detailStat__label">任务类型</span>
            <Typography.Title level={3} className="admin-detailStat__value">
              retrieval_only
            </Typography.Title>
            <span className="admin-detailStat__hint">当前任务只评估召回与证据链，不比较最终回答。</span>
          </div>
          <div className="admin-detailMeta">
            <Descriptions column={2}>
              <Descriptions.Item label="创建时间">2026-04-24 10:30</Descriptions.Item>
              <Descriptions.Item label="执行模型">DeepSeek Chat</Descriptions.Item>
              <Descriptions.Item label="样本总数">128</Descriptions.Item>
              <Descriptions.Item label="待复核">17</Descriptions.Item>
            </Descriptions>
          </div>
        </div>
      </Card>
      <Card className="admin-listPanel" style={{ marginTop: 16 }}>
        <div className="admin-listToolbar">
          <div className="admin-listToolbar__main">
            <Typography.Title level={4} className="admin-listToolbar__title">
              结果明细
            </Typography.Title>
            <Typography.Text type="secondary" className="admin-listToolbar__subtitle">
              每条记录展示原始问题、机跑答案和当前评测结论，后续可在这里承接人工复核。
            </Typography.Text>
          </div>
        </div>
        <Table
          rowKey="query"
          pagination={false}
          columns={columns}
          dataSource={[
            {
              query: '港澳通行证怎么办理？',
              answer: '请准备身份证明并前往出入境窗口办理。',
              result: '可回答，待人工复核',
            },
          ]}
        />
      </Card>
    </AdminPage>
  );
}
