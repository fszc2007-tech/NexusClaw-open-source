import { useEffect, useState } from 'react';
import { Button, Form, Input } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';

import { useI18n } from '@/i18n/useI18n';
import { login } from '@/services/authApi';
import { message } from '@/services/notify';

import './index.less';

type LoginFormValues = {
  username: string;
  password: string;
};

type LoginAnalyticsEvent = 'admin_login_view' | 'admin_login_submit' | 'admin_login_success' | 'admin_login_failure';

const statusKeys = ['login.status.model', 'login.status.vector', 'login.status.guardrail'];

const capabilityCards = [
  {
    title: 'login.capability.knowledge.title',
    desc: 'login.capability.knowledge.desc',
    icon: 'plus',
  },
  {
    title: 'login.capability.retrieval.title',
    desc: 'login.capability.retrieval.desc',
    icon: 'route',
  },
  {
    title: 'login.capability.security.title',
    desc: 'login.capability.security.desc',
    icon: 'shield',
  },
];

function trackLoginEvent(eventName: LoginAnalyticsEvent, properties: Record<string, unknown> = {}) {
  if (typeof window === 'undefined') {
    return;
  }

  if (process.env.NODE_ENV !== 'production') {
    window.console.debug('[analytics]', eventName, properties);
  }
}

function NexusClawIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 96 96" aria-hidden="true" focusable="false">
      <rect x="7" y="6" width="82" height="84" rx="24" fill="#286FFF" />
      <path d="M7 6H89V46C62 34 38 32 7 48V6Z" fill="#35D6FF" fillOpacity="0.52" />
      <path d="M43 26C59 31 74 38 89 48V90H7V68C19 50 31 39 43 26Z" fill="#233DFF" fillOpacity="0.48" />
      <rect x="8.5" y="7.5" width="79" height="81" rx="22.5" stroke="rgba(255,255,255,0.36)" strokeWidth="3" />
      <path d="M7 26C25 12 52 17 89 34V6H7V26Z" fill="#FFFFFF" fillOpacity="0.22" />
      <path d="M18 72C34 58 47 63 61 49C72 39 75 29 83 21V90H18V72Z" fill="#0B2B8F" fillOpacity="0.13" />
      <path d="M31 62C36 45.8 47 34 65.6 24.4" stroke="#FFFFFF" strokeWidth="6.2" strokeLinecap="round" />
      <path d="M39.6 68.6C44.4 52.4 54.8 40.3 72.6 31.2" stroke="#D3F9FF" strokeWidth="6.2" strokeLinecap="round" opacity="0.9" />
      <path d="M48.5 72.4C52.5 58.2 61.9 47 77.8 39" stroke="#D3F9FF" strokeWidth="5.4" strokeLinecap="round" opacity="0.74" />
      <path d="M27.5 32.2L48 21.8L69.3 32.2V54.8L48 66.3L27.5 54.8V32.2Z" fill="#FFFFFF" fillOpacity="0.14" stroke="#FFFFFF" strokeOpacity="0.42" strokeWidth="2.7" strokeLinejoin="round" />
      <path d="M35.8 51.5C40.8 42.2 48.8 37.2 59.8 35.7" stroke="#FFFFFF" strokeWidth="4.8" strokeLinecap="round" />
      <path d="M35.5 40.4L48 50.8L62.2 40.4" stroke="#CFF8FF" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="27.5" cy="32.2" r="4" fill="#FFFFFF" />
      <circle cx="69.3" cy="32.2" r="4" fill="#FFFFFF" />
      <circle cx="48" cy="66.3" r="4" fill="#FFFFFF" />
      <circle cx="48" cy="21.8" r="3.2" fill="#CFF8FF" />
    </svg>
  );
}

function CapabilityIcon({ type }: { type: string }) {
  if (type === 'route') {
    return (
      <svg viewBox="0 0 44 44" aria-hidden="true">
        <path d="M12 28C18 15 27 15 34 28" />
        <path d="M12 16C18 29 27 29 34 16" />
      </svg>
    );
  }

  if (type === 'shield') {
    return (
      <svg viewBox="0 0 44 44" aria-hidden="true">
        <path d="M22 10L34 16V27C34 33 28 37 22 39C16 37 10 33 10 27V16L22 10Z" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 44 44" aria-hidden="true">
      <path d="M13 22H31" />
      <path d="M22 13V31" />
    </svg>
  );
}

export default function LoginPage() {
  const [form] = Form.useForm<LoginFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const { t, tList } = useI18n();
  const trustBrands = tList('login.trustBrands');

  useEffect(() => {
    document.documentElement.classList.add('nc-login-page');
    document.body.classList.add('nc-login-page');
    trackLoginEvent('admin_login_view');

    return () => {
      document.documentElement.classList.remove('nc-login-page');
      document.body.classList.remove('nc-login-page');
    };
  }, []);

  const handleSubmit = async (values: LoginFormValues) => {
    if (!values.username || !values.password) {
      message.warning(t('login.validation.missingCredentials'));
      return;
    }

    try {
      setSubmitting(true);
      trackLoginEvent('admin_login_submit');
      await login(values.username, values.password);
      trackLoginEvent('admin_login_success');
      message.success(t('login.toast.success'));
      history.replace('/knowledge/bases');
    } catch (error) {
      trackLoginEvent('admin_login_failure', {
        errorType: error instanceof Error ? error.name : 'unknown',
      });
      message.error(error instanceof Error ? error.message : t('login.toast.fail'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="nc-login">
      <div className="nc-login__background" aria-hidden="true" />
      <div className="nc-login__shell">
        <section className="nc-login__intro" aria-label={t('login.introLabel')}>
          <header className="nc-login__brand">
            <NexusClawIcon className="nc-login__brandIcon" />
            <div>
              <strong>{t('login.productName')}</strong>
              <span>{t('login.brandSubtitle')}</span>
            </div>
          </header>

          <div className="nc-login__headline">
            <p className="nc-login__eyebrow">{t('login.eyebrow')}</p>
            <h1>
              <span>{t('login.heroTitleLine1')}</span>
              <span>{t('login.heroTitleLine2')}</span>
            </h1>
            <p>{t('login.heroSummary')}</p>
          </div>

          <div className="nc-login__opsPanel" aria-label={t('login.capabilityPanelTitle')}>
            <div className="nc-login__opsHeader">
              <div className="nc-login__traffic" aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
              <span>{t('login.pipelineLabel')}</span>
            </div>

            <div className="nc-login__capabilities">
              {capabilityCards.map((card) => (
                <article className="nc-login__capability" key={card.title}>
                  <div className="nc-login__capabilityIcon">
                    <CapabilityIcon type={card.icon} />
                  </div>
                  <strong>{t(card.title)}</strong>
                  <span>{t(card.desc)}</span>
                </article>
              ))}
            </div>
          </div>

          <div className="nc-login__trust" aria-label={t('login.trustLabel')}>
            {trustBrands.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </section>

        <aside className="nc-login__access" aria-label={t('login.accessPanelTitle')}>
          <header className="nc-login__accessHero">
            <NexusClawIcon className="nc-login__accessIcon" />
            <h2>{t('login.productName')}</h2>
            <p>{t('login.systemName')}</p>
          </header>

          <div className="nc-login__body">
            <div className="nc-login__status" aria-label={t('login.statusLabel')}>
              {statusKeys.map((key) => (
                <span key={key}>{t(key)}</span>
              ))}
            </div>

            <Form<LoginFormValues>
              form={form}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => void handleSubmit(values)}
              className="nc-login__form"
            >
              <Form.Item
                name="username"
                label={t('login.labelUser')}
                rules={[{ required: true, message: t('login.placeholder.username') }]}
              >
                <Input
                  size="large"
                  prefix={<UserOutlined />}
                  placeholder={t('login.placeholder.username')}
                  autoComplete="username"
                />
              </Form.Item>

              <Form.Item
                name="password"
                label={t('login.labelPassword')}
                rules={[{ required: true, message: t('login.placeholder.password') }]}
              >
                <Input.Password
                  size="large"
                  prefix={<LockOutlined />}
                  placeholder={t('login.placeholder.password')}
                  autoComplete="current-password"
                />
              </Form.Item>

              <Button type="primary" htmlType="submit" loading={submitting} block size="large" className="nc-login__submit">
                {submitting ? t('login.submitting') : t('login.loginBtn')}
              </Button>
            </Form>

            <p className="nc-login__hint">{t('login.footerHint')}</p>
          </div>
        </aside>
      </div>
    </main>
  );
}
