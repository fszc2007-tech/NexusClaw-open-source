import { Card, Space, Typography } from 'antd';
import type { ReactNode } from 'react';

type PortalPageProps = {
  title: string;
  description: string;
  eyebrow?: string;
  extra?: ReactNode;
  children: ReactNode;
};

export default function PortalPage({
  title,
  description,
  eyebrow = 'NexusClaw Portal',
  extra,
  children,
}: PortalPageProps) {
  return (
    <div className="portal-shell">
      <div className="portal-page">
        <div className="portal-page__header">
          <div>
            <div className="portal-page__eyebrow">{eyebrow}</div>
            <Typography.Title level={2} className="portal-page__title">
              {title}
            </Typography.Title>
            <Typography.Text type="secondary" className="portal-page__description">
              {description}
            </Typography.Text>
          </div>
          {extra ? <Space>{extra}</Space> : null}
        </div>
        <Card className="portal-card">{children}</Card>
      </div>
    </div>
  );
}
