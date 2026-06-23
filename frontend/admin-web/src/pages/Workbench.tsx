import { Link } from '@umijs/max';
import { Card, Col, List, Row, Space, Tag, Typography } from 'antd';

import AdminPage from '@/components/AdminPage';

type Tone = 'blue' | 'amber' | 'mint' | 'violet';

const overviewCards: Array<{
  tone: Tone;
  label: string;
  value: string;
  meta: string;
  foot: string;
}> = [
  {
    tone: 'blue',
    label: '內容治理',
    value: '知識庫',
    meta: '文件、知識條目與知識樹結構',
    foot: '保證內容可檢索、可追溯、可維護',
  },
  {
    tone: 'amber',
    label: '體驗驗證',
    value: '問答聯調',
    meta: '真實提問、回放與檢索驗證',
    foot: '快速觀察回答質量與引用依據',
  },
  {
    tone: 'mint',
    label: '質量巡檢',
    value: '測試任務',
    meta: '測試集、回歸任務與結果觀察',
    foot: '把變更後的穩定性留在可追蹤流程裡',
  },
  {
    tone: 'violet',
    label: '問題定位',
    value: '會話日誌',
    meta: '異常回放、命中鏈路與使用情境',
    foot: '適合追查線上真實問題與關鍵樣本',
  },
];

const realtimeStats = [
  {
    label: '配置核查',
    value: '開場白 / Prompt / 記憶',
    note: '先確保策略配置與當前業務口徑一致。',
  },
  {
    label: '內容維護',
    value: '文件 / 條目 / 結構',
    note: '上傳後及時檢查可檢索性與治理狀態。',
  },
  {
    label: '體驗巡檢',
    value: '問答 / 搜索',
    note: '用真實問題驗證引用、改寫與回覆完整度。',
  },
  {
    label: '異常定位',
    value: '日誌 / 任務 / 樣本',
    note: '把問題回放、測試與治理串成同一條鏈路。',
  },
];

const trendCards = [
  {
    title: '管理節奏',
    subtitle: '工作台核心節點',
    badge: 'Workbench Flow',
    tone: 'blue' as const,
    points: [6, 8, 7, 11, 9, 14, 10, 16],
    notes: ['配置確認', '內容上新', '體驗聯調', '測試回歸'],
  },
  {
    title: '巡檢視角',
    subtitle: '常見排查動線',
    badge: 'Ops Active',
    tone: 'violet' as const,
    points: [5, 12, 8, 10, 14, 11, 15, 13],
    notes: ['檢索命中', '回答質量', '會話回放', '治理收斂'],
  },
];

const quickEntryItems = [
  {
    title: '項目管理',
    description: '查看項目列表、維護成員與基礎設定。',
    path: '/projects',
  },
  {
    title: '知識資產',
    description: '進入知識庫與治理隊列，完成內容維護。',
    path: '/knowledge/bases',
  },
  {
    title: '測試任務',
    description: '發起回歸檢查並跟蹤質量結果。',
    path: '/testing/tasks',
  },
  {
    title: '歷史日誌',
    description: '回看會話上下文，定位線上異常樣本。',
    path: '/logs/chat',
  },
];

const operationChecklist = [
  '先確認項目配置、開場白與 Prompt 是否與當前業務一致。',
  '檢查新上傳文件與知識條目是否能被正常檢索與引用。',
  '對高頻問題做一次真實提問聯調，觀察回答與依據是否穩定。',
  '有異常樣本時，優先回放日誌，再回看相關知識與測試任務。',
];

function cardIconPath(tone: Tone) {
  switch (tone) {
    case 'amber':
      return (
        <>
          <path d="M8 17.5h8" />
          <path d="M9.2 7.5h5.6l-.8 3.4h2.5L12 16l.9-3.6H10z" />
        </>
      );
    case 'mint':
      return (
        <>
          <path d="M8.5 8.5h7" />
          <path d="M8.5 12h7" />
          <path d="M8.5 15.5h4.5" />
          <rect x="6" y="5.5" width="12" height="13" rx="3" />
        </>
      );
    case 'violet':
      return (
        <>
          <path d="M6.5 12h2.8l1.7-3.3 2.4 6.1 1.7-3.1h2.4" />
          <path d="M12 5.5v2" />
          <path d="M12 16.5v2" />
        </>
      );
    default:
      return (
        <>
          <rect x="5.5" y="6" width="5.5" height="5.5" rx="1.3" />
          <rect x="13" y="6" width="5.5" height="4.2" rx="1.3" />
          <rect x="13" y="11.8" width="5.5" height="6.2" rx="1.3" />
          <rect x="5.5" y="13.3" width="5.5" height="4.7" rx="1.3" />
        </>
      );
  }
}

function OverviewIcon({ tone }: { tone: Tone }) {
  return (
    <span className={`admin-workbench__overviewIcon admin-workbench__overviewIcon--${tone}`} aria-hidden="true">
      <svg viewBox="0 0 24 24">
        {cardIconPath(tone)}
      </svg>
    </span>
  );
}

function Sparkline({ points, tone }: { points: number[]; tone: 'blue' | 'violet' }) {
  const width = 320;
  const height = 128;
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = Math.max(max - min, 1);
  const color = tone === 'violet' ? '#8b5cf6' : '#3b82f6';
  const coords = points.map((point, index) => {
    const x = (index / (points.length - 1)) * width;
    const y = height - ((point - min) / range) * (height - 18) - 8;
    return `${x},${y}`;
  });
  const area = `M ${coords[0]} L ${coords.slice(1).join(' L ')} L ${width},${height} L 0,${height} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="admin-workbench__sparkline" aria-hidden="true">
      <defs>
        <linearGradient id={`admin-spark-${tone}`} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={color} stopOpacity="0.24" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#admin-spark-${tone})`} />
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={coords.join(' ')}
      />
      {coords.map((point) => {
        const [x, y] = point.split(',');
        return <circle key={point} cx={x} cy={y} r="3.5" fill="#ffffff" stroke={color} strokeWidth="2.5" />;
      })}
    </svg>
  );
}

export default function WorkbenchPage() {
  return (
    <AdminPage title="數據看板" description="把管理入口重組成更像運營控制台的首頁節奏。" hideHero>
      <div className="admin-workbench">
        <Card className="admin-workbench__hero">
          <div className="admin-workbench__heroMain">
            <Space wrap size={[10, 10]}>
              <Tag color="blue">Dashboard</Tag>
              <Tag color="geekblue">Admin Refresh</Tag>
            </Space>
            <Typography.Title level={2} className="admin-workbench__heroTitle">
              數據看板
            </Typography.Title>
            <Typography.Paragraph className="admin-workbench__heroDescription">
              參照你提供的 xiaopei admin dashboard 風格，把工作台調整成更乾淨的淺色看板首頁。先收口殼層、導航和卡片節奏，再承接項目治理、知識維護與體驗巡檢。
            </Typography.Paragraph>
          </div>
          <div className="admin-workbench__heroAside">
            <div className="admin-workbench__heroNote">
              <span>視覺方向</span>
              <strong>柔和漸層 + 浮層卡片 + 左側導覽</strong>
            </div>
            <div className="admin-workbench__heroNote">
              <span>當前重點</span>
              <strong>先提升首頁與共享殼層的一致性</strong>
            </div>
          </div>
        </Card>

        <Row gutter={[20, 20]} className="admin-dashboardSignals">
          {overviewCards.map((item) => (
            <Col xs={24} md={12} xl={6} key={item.label}>
              <Card className={`admin-signalCard admin-signalCard--${item.tone}`}>
                <div className="admin-signalCard__top">
                  <OverviewIcon tone={item.tone} />
                  <span className="admin-signalCard__dot" aria-hidden="true">
                    ·
                  </span>
                </div>
                <Typography.Text className="admin-signalCard__label">{item.label}</Typography.Text>
                <Typography.Title level={3} className="admin-signalCard__value">
                  {item.value}
                </Typography.Title>
                <Typography.Text className="admin-signalCard__meta">{item.meta}</Typography.Text>
                <Typography.Text className="admin-signalCard__foot">{item.foot}</Typography.Text>
              </Card>
            </Col>
          ))}
        </Row>

        <Card className="admin-panelCard admin-workbenchRealtime">
          <div className="admin-workbenchRealtime__header">
            <div>
              <Typography.Text className="admin-workbenchRealtime__eyebrow">Today&apos;s Control Focus</Typography.Text>
              <Typography.Title level={3} className="admin-workbenchRealtime__title">
                今日實時視圖
              </Typography.Title>
              <Typography.Text className="admin-workbenchRealtime__subtitle">
                不先堆滿複雜數據，而是把管理動作本身設計成可掃一眼理解的工作看板。
              </Typography.Text>
            </div>
            <Tag color="cyan">Realtime Workflow</Tag>
          </div>
          <div className="admin-workbenchRealtime__grid">
            {realtimeStats.map((item) => (
              <div key={item.label} className="admin-workbenchRealtime__stat">
                <Typography.Text className="admin-workbenchRealtime__statLabel">{item.label}</Typography.Text>
                <Typography.Title level={4} className="admin-workbenchRealtime__statValue">
                  {item.value}
                </Typography.Title>
                <Typography.Text className="admin-workbenchRealtime__statNote">{item.note}</Typography.Text>
              </div>
            ))}
          </div>
        </Card>

        <Row gutter={[20, 20]}>
          {trendCards.map((item) => (
            <Col xs={24} xl={12} key={item.title}>
              <Card className="admin-panelCard admin-workbenchTrend">
                <div className="admin-workbenchTrend__header">
                  <div>
                    <Typography.Title level={3} className="admin-workbenchTrend__title">
                      {item.title}
                    </Typography.Title>
                    <Typography.Text className="admin-workbenchTrend__subtitle">{item.subtitle}</Typography.Text>
                  </div>
                  <Tag color={item.tone === 'violet' ? 'purple' : 'blue'}>{item.badge}</Tag>
                </div>
                <Sparkline points={item.points} tone={item.tone} />
                <div className="admin-workbenchTrend__notes">
                  {item.notes.map((note) => (
                    <span key={note} className="admin-workbenchTrend__note">
                      {note}
                    </span>
                  ))}
                </div>
              </Card>
            </Col>
          ))}
        </Row>

        <Row gutter={[20, 20]} className="admin-dashboardActions">
          <Col xs={24} xl={14}>
            <Card title="常用管理入口" className="admin-panelCard">
              <List
                dataSource={quickEntryItems}
                renderItem={(item) => (
                  <List.Item extra={<Link to={item.path} className="admin-inlineLink">进入</Link>}>
                    <Space direction="vertical" size={2}>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Typography.Text type="secondary">{item.description}</Typography.Text>
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          </Col>

          <Col xs={24} xl={10}>
            <Card title="日常管理建議" className="admin-panelCard">
              <List
                dataSource={operationChecklist}
                renderItem={(item) => (
                  <List.Item>
                    <Space align="start" size={12}>
                      <span className="admin-workbench__checkDot" aria-hidden="true" />
                      <Typography.Text>{item}</Typography.Text>
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          </Col>
        </Row>
      </div>
    </AdminPage>
  );
}
