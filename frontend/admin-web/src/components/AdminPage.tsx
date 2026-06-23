import { Card, Space, Tag, Typography } from 'antd';
import type { ReactNode } from 'react';

type AdminPageProps = {
  title: string;
  description: string;
  tags?: string[];
  extra?: ReactNode;
  hideHero?: boolean;
  children: ReactNode;
};

export default function AdminPage({ title, description, tags = [], extra, hideHero = false, children }: AdminPageProps) {
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }} className="admin-page">
      {!hideHero ? (
        <Card className="admin-page__hero">
          <div className="admin-page__heroInner">
            <div className="admin-page__heading">
              <Space direction="vertical" size={4} className="admin-page__headingMain">
                <Typography.Title level={3} className="admin-page__title">
                  {title}
                </Typography.Title>
                <Typography.Text type="secondary" className="admin-page__description">
                  {description}
                </Typography.Text>
              </Space>
              {extra ? <div className="admin-page__headingExtra">{extra}</div> : null}
            </div>
            {tags.length > 0 ? (
              <Space wrap className="admin-page__tagRow">
                {tags.map((tag) => (
                  <Tag key={tag} color="blue">
                    {tag}
                  </Tag>
                ))}
              </Space>
            ) : null}
          </div>
        </Card>
      ) : null}
      {children}
    </Space>
  );
}
