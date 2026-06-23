import type { CSSProperties, ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import type { MenuProps } from 'antd';
import { Button, Divider, Layout, Menu, Select, Space, Spin, Tag, Typography } from 'antd';
import { Link, Outlet, history, useLocation } from '@umijs/max';

import { fetchCurrentUser, logout } from '@/services/authApi';
import { clearAuthState, getStoredUser, hasAuthSession, type AuthUser } from '@/services/authStore';
import { useI18n } from '@/i18n/useI18n';
import { useActiveProject } from '@/hooks/useActiveProject';
import { isAdminDemoMode } from '@/services/client';

const { Sider, Content } = Layout;

type MenuItem = Required<MenuProps>['items'][number];

function SidebarIcon({ children }: { children: ReactNode }) {
  return <span className="admin-menu__icon">{children}</span>;
}

function iconStrokeStyle(): CSSProperties {
  return {
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.75,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    vectorEffect: 'non-scaling-stroke',
  };
}

function ExperienceIcon() {
  const stroke = iconStrokeStyle();
  return (
    <SidebarIcon>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6 7.5h12a2.5 2.5 0 0 1 2.5 2.5v5a2.5 2.5 0 0 1-2.5 2.5h-6l-4.5 3v-3H6A2.5 2.5 0 0 1 3.5 15v-5A2.5 2.5 0 0 1 6 7.5Z" style={stroke} />
        <path d="M8 11h8M8 14h5" style={stroke} />
      </svg>
    </SidebarIcon>
  );
}

function SettingsIcon() {
  const stroke = iconStrokeStyle();
  return (
    <SidebarIcon>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 7h6M15 7h4M5 17h4M13 17h6" style={stroke} />
        <circle cx="13" cy="7" r="2.5" style={stroke} />
        <circle cx="10" cy="17" r="2.5" style={stroke} />
      </svg>
    </SidebarIcon>
  );
}

function KnowledgeIcon() {
  const stroke = iconStrokeStyle();
  return (
    <SidebarIcon>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 5.5h8a3 3 0 0 1 3 3v10H9.5A2.5 2.5 0 0 0 7 21Z" style={stroke} />
        <path d="M7 5.5A2.5 2.5 0 0 0 4.5 8v10.5H13" style={stroke} />
        <path d="M9 10h6M9 13.5h6" style={stroke} />
      </svg>
    </SidebarIcon>
  );
}

function TestingIcon() {
  const stroke = iconStrokeStyle();
  return (
    <SidebarIcon>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 4.5h6M10 4.5v4l-4 6.3A2.8 2.8 0 0 0 8.36 19h7.28A2.8 2.8 0 0 0 18 14.8L14 8.5v-4" style={stroke} />
        <path d="M8.5 12.5h7" style={stroke} />
      </svg>
    </SidebarIcon>
  );
}

function LogsIcon() {
  const stroke = iconStrokeStyle();
  return (
    <SidebarIcon>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4.5" y="5.5" width="15" height="13" rx="2.5" style={stroke} />
        <path d="M8 10h8M8 13.5h8M8 17h5" style={stroke} />
      </svg>
    </SidebarIcon>
  );
}

function UsersIcon() {
  const stroke = iconStrokeStyle();
  return (
    <SidebarIcon>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 11a3.25 3.25 0 1 0 0-6.5A3.25 3.25 0 0 0 12 11Z" style={stroke} />
        <path d="M5 19a7 7 0 0 1 14 0" style={stroke} />
        <path d="M17.5 7.5a2.4 2.4 0 0 1 2 3.9M20.5 18a5.9 5.9 0 0 0-2.2-3.2" style={stroke} />
      </svg>
    </SidebarIcon>
  );
}

function ProjectsIcon() {
  const stroke = iconStrokeStyle();
  return (
    <SidebarIcon>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4.5" y="5.5" width="15" height="13" rx="2.5" style={stroke} />
        <path d="M12 5.5v13M4.5 12h15" style={stroke} />
      </svg>
    </SidebarIcon>
  );
}

function buildPrimaryMenuItems(t: (key: string) => string): MenuItem[] {
  const experienceChildren: MenuItem[] = [
    { key: '/experience/chat', label: <Link to="/experience/chat">{t('layout.menu.experienceChat')}</Link> },
    { key: '/experience/search', label: <Link to="/experience/search">{t('layout.menu.experienceSearch')}</Link> },
  ];

  return [
    {
      key: 'experience',
      icon: <ExperienceIcon />,
      label: t('layout.menu.experience'),
      children: experienceChildren,
    },
    {
      key: 'settings',
      icon: <SettingsIcon />,
      label: t('layout.menu.settings'),
      children: [
        { key: '/settings/opening', label: <Link to="/settings/opening">{t('layout.menu.settingsOpening')}</Link> },
        { key: '/settings/memory', label: <Link to="/settings/memory">{t('layout.menu.settingsMemory')}</Link> },
        { key: '/settings/prompt', label: <Link to="/settings/prompt">{t('layout.menu.settingsPrompt')}</Link> },
      ],
    },
    {
      key: 'knowledge',
      icon: <KnowledgeIcon />,
      label: t('layout.menu.knowledge'),
      children: [
        { key: '/knowledge/bases', label: <Link to="/knowledge/bases">{t('layout.menu.knowledgeBases')}</Link> },
        { key: '/knowledge/governance', label: <Link to="/knowledge/governance">{t('layout.menu.knowledgeGovernance')}</Link> },
      ],
    },
    {
      key: 'testing',
      icon: <TestingIcon />,
      label: t('layout.menu.testing'),
      children: [
        { key: '/testing/datasets', label: <Link to="/testing/datasets">{t('layout.menu.testingDatasets')}</Link> },
        { key: '/testing/tasks', label: <Link to="/testing/tasks">{t('layout.menu.testingTasks')}</Link> },
      ],
    },
  ];
}

function buildUtilityMenuItems(t: (key: string) => string, currentUser: AuthUser | null): MenuItem[] {
  const canAccessProjects =
    currentUser?.system_role === 'super_admin' ||
    Boolean(currentUser?.project_memberships.some((item) => item.project_role === 'project_admin'));

  return [
    {
      key: 'logs',
      icon: <LogsIcon />,
      label: t('layout.menu.logs'),
      children: [{ key: '/logs/chat', label: <Link to="/logs/chat">{t('layout.menu.logsChat')}</Link> }],
    },
    currentUser?.system_role === 'super_admin'
      ? { key: '/users', icon: <UsersIcon />, label: <Link to="/users">{t('layout.menu.users')}</Link> }
      : null,
    canAccessProjects ? { key: '/projects', icon: <ProjectsIcon />, label: <Link to="/projects">{t('layout.menu.projects')}</Link> } : null,
  ].filter(Boolean) as MenuItem[];
}

function getSelectedMenuKey(pathname: string) {
  if (pathname.startsWith('/knowledge/bases')) return '/knowledge/bases';
  if (pathname.startsWith('/knowledge/governance')) return '/knowledge/governance';
  if (pathname.startsWith('/testing/datasets')) return '/testing/datasets';
  if (pathname.startsWith('/testing/tasks')) return '/testing/tasks';
  if (pathname.startsWith('/logs/chat')) return '/logs/chat';
  if (pathname.startsWith('/users')) return '/users';
  if (pathname.startsWith('/projects')) return '/projects';
  if (pathname.startsWith('/settings/opening')) return '/settings/opening';
  if (pathname.startsWith('/settings/memory')) return '/settings/memory';
  if (pathname.startsWith('/settings/prompt')) return '/settings/prompt';
  if (pathname.startsWith('/experience/chat')) return '/experience/chat';
  if (pathname.startsWith('/experience/search')) return '/experience/search';
  if (pathname.startsWith('/experience/document-qa')) return '/experience/document-qa';
  return '/knowledge/bases';
}

function getPrimaryRootKey(selectedKey: string) {
  if (selectedKey.startsWith('/experience/')) return 'experience';
  if (selectedKey.startsWith('/settings/')) return 'settings';
  if (selectedKey.startsWith('/knowledge/')) return 'knowledge';
  if (selectedKey.startsWith('/testing/')) return 'testing';
  return null;
}

function getUtilityRootKey(selectedKey: string) {
  if (selectedKey.startsWith('/logs/')) return 'logs';
  return null;
}

function getPageMeta(pathname: string, t: (key: string) => string) {
  if (pathname.startsWith('/knowledge/governance')) {
    return {
      title: t('layout.menu.knowledgeGovernance'),
      subtitle: '集中查看重复、失效与冲突知识，快速完成治理决策。',
    };
  }
  if (pathname.startsWith('/knowledge/')) {
    return {
      title: t('layout.menu.knowledgeBases'),
      subtitle: '维护知识库内容、文件结构与可检索性。',
    };
  }
  if (pathname.startsWith('/testing/')) {
    return {
      title: t('layout.menu.testing'),
      subtitle: '追踪测试集、回归任务和质量表现。',
    };
  }
  if (pathname.startsWith('/logs/')) {
    return {
      title: t('layout.menu.logs'),
      subtitle: '回放历史会话，定位异常回复和使用问题。',
    };
  }
  if (pathname.startsWith('/projects/')) {
    return {
      title: t('layout.menu.projects'),
      subtitle: '管理项目空间、成员权限与配置边界。',
    };
  }
  if (pathname.startsWith('/users')) {
    return {
      title: t('layout.menu.users'),
      subtitle: '维护后台账号、角色分配和访问范围。',
    };
  }
  if (pathname.startsWith('/settings/')) {
    return {
      title: t('layout.menu.settings'),
      subtitle: '调整开场白、记忆和 Prompt 策略。',
    };
  }
  if (pathname.startsWith('/experience/')) {
    return {
      title: t('layout.menu.experience'),
      subtitle: '从真实交互视角检查项目问答、检索和联调体验。',
    };
  }
  return {
    title: '数据看板',
    subtitle: '用更清晰的运营视角查看项目治理、内容维护与体验质量。',
  };
}

export default function AdminLayout() {
  const location = useLocation();
  const selectedKey = getSelectedMenuKey(location.pathname);
  const { activeProject, activeProjectId, loading, projects, setActiveProjectId } = useActiveProject();
  const { locale, localeOptions, setLocale, t } = useI18n();
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(getStoredUser());
  const [authLoading, setAuthLoading] = useState(location.pathname !== '/login');
  const primaryMenuItems = useMemo(() => buildPrimaryMenuItems(t), [t]);
  const utilityMenuItems = useMemo(() => buildUtilityMenuItems(t, currentUser), [currentUser, t]);
  const primarySelectedKeys = useMemo(
    () => (selectedKey === '/logs/chat' || selectedKey === '/users' || selectedKey === '/projects' ? [] : [selectedKey]),
    [selectedKey],
  );
  const utilitySelectedKeys = useMemo(
    () => (selectedKey === '/logs/chat' || selectedKey === '/users' || selectedKey === '/projects' ? [selectedKey] : []),
    [selectedKey],
  );
  const pageMeta = useMemo(() => getPageMeta(location.pathname, t), [location.pathname, t]);
  const todayLabel = useMemo(
    () =>
      new Intl.DateTimeFormat('zh-HK', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      }).format(new Date()),
    [],
  );
  const [openPrimaryKeys, setOpenPrimaryKeys] = useState<string[]>([]);
  const [openUtilityKeys, setOpenUtilityKeys] = useState<string[]>([]);

  const projectOptions = useMemo(
    () =>
      projects.map((project) => ({
        value: project.id,
        label: `${project.company_name} (${project.project_key})`,
      })),
    [projects],
  );

  useEffect(() => {
    const rootKey = getPrimaryRootKey(selectedKey);
    setOpenPrimaryKeys(rootKey ? [rootKey] : []);
  }, [selectedKey]);

  useEffect(() => {
    const rootKey = getUtilityRootKey(selectedKey);
    setOpenUtilityKeys(rootKey ? [rootKey] : []);
  }, [selectedKey]);

  useEffect(() => {
    if (location.pathname === '/login') {
      setAuthLoading(false);
      return;
    }
    if (!hasAuthSession()) {
      clearAuthState();
      history.replace('/login');
      return;
    }

    let cancelled = false;
    setAuthLoading(true);
    void fetchCurrentUser()
      .then((user) => {
        if (!cancelled) {
          setCurrentUser(user);
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearAuthState();
          history.replace('/login');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAuthLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  useEffect(() => {
    if (!currentUser || location.pathname === '/login') {
      return;
    }

    const canAccessProjects =
      currentUser.system_role === 'super_admin' ||
      currentUser.project_memberships.some((item) => item.project_role === 'project_admin');

    if (location.pathname.startsWith('/users') && currentUser.system_role !== 'super_admin') {
      history.replace('/knowledge/bases');
      return;
    }

    if (location.pathname.startsWith('/projects') && !canAccessProjects) {
      history.replace('/knowledge/bases');
      return;
    }

    if (location.pathname === '/projects/new' && currentUser.system_role !== 'super_admin') {
      history.replace('/projects');
    }
  }, [currentUser, location.pathname]);

  if (location.pathname === '/login') {
    return <Outlet />;
  }

  if (authLoading || !currentUser) {
    return (
      <div className="admin-app" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  const roleLabel =
    currentUser.system_role === 'super_admin'
      ? '角色：超级管理员'
      : currentUser.project_memberships.some((item) => item.project_role === 'project_admin')
        ? '角色：项目管理员'
        : '角色：项目成员';

  return (
    <div className="admin-app">
      <Layout className="admin-layout" style={{ minHeight: '100vh' }}>
        <Sider width={272} theme="light" className="admin-sider">
          <div className="admin-brand admin-brand--compact">
            <div className="admin-brand__mark" aria-hidden="true">
              N
            </div>
            <div className="admin-brand__copy">
              <Typography.Title level={4} className="admin-brand__title" style={{ margin: 0 }}>
                NexusClaw Admin
              </Typography.Title>
              <Typography.Text className="admin-brand__subtitle">Knowledge Ops Console</Typography.Text>
            </div>
          </div>
          <div className="admin-sider__nav">
            <Menu
              className="admin-menu admin-menu--primary"
              theme="light"
              mode="inline"
              selectedKeys={primarySelectedKeys}
              openKeys={openPrimaryKeys}
              onOpenChange={(keys) => setOpenPrimaryKeys(keys.length ? [String(keys[keys.length - 1])] : [])}
              items={primaryMenuItems}
            />
          </div>
          <div className="admin-sider__utility">
            <Divider className="admin-sider__divider" />
            <Typography.Text className="admin-sider__sectionLabel admin-sider__sectionLabel--secondary">
              {t('layout.menu.utility')}
            </Typography.Text>
            <Menu
              className="admin-menu admin-menu--utility"
              theme="light"
              mode="inline"
              selectedKeys={utilitySelectedKeys}
              openKeys={openUtilityKeys}
              onOpenChange={(keys) => setOpenUtilityKeys(keys.length ? [String(keys[keys.length - 1])] : [])}
              items={utilityMenuItems}
            />
            <div className="admin-sider__controlStack">
              <div className="admin-sider__selectShell">
                <Select
                  placeholder={t('layout.languagePlaceholder')}
                  options={localeOptions}
                  value={locale}
                  onChange={setLocale}
                />
              </div>
              <div className="admin-sider__selectShell">
                <Select
                  placeholder={t('layout.projectPlaceholder')}
                  loading={loading}
                  options={projectOptions}
                  value={activeProjectId ?? undefined}
                  onChange={setActiveProjectId}
                />
              </div>
              <div className="admin-sider__badgeRow">
                {isAdminDemoMode() ? <Tag color="cyan">{t('layout.demoMode')}</Tag> : null}
                <Tag color="gold">{roleLabel}</Tag>
              </div>
              <Button
                className="admin-sider__logoutButton"
                onClick={() => {
                  void logout().finally(() => {
                    setCurrentUser(null);
                    history.replace('/login');
                  });
                }}
              >
                退出登录
              </Button>
            </div>
            <Typography.Text className="admin-sider__footnote">
              {t('layout.sidebarFootnote')}
            </Typography.Text>
          </div>
        </Sider>
        <Layout className="admin-main">
          <div className="admin-shellHeader">
            <div className="admin-shellHeader__main">
              <Typography.Text className="admin-shellHeader__eyebrow">Admin Workspace</Typography.Text>
              <Typography.Title level={2} className="admin-shellHeader__title">
                {pageMeta.title}
              </Typography.Title>
              <Typography.Text className="admin-shellHeader__subtitle">{pageMeta.subtitle}</Typography.Text>
            </div>
            <Space wrap size={12} className="admin-shellHeader__aside">
              <div className="admin-shellHeader__pill">
                <span className="admin-shellHeader__pillLabel">当前项目</span>
                <strong>{activeProject?.company_name || t('layout.noProject')}</strong>
              </div>
              <div className="admin-shellHeader__pill admin-shellHeader__pill--date">
                <strong>{todayLabel}</strong>
              </div>
            </Space>
          </div>
          <Content className="admin-content">
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </div>
  );
}
