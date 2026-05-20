import { Form, Input, Button, message } from 'antd';
import { ArrowRight, BookMarked, Braces, FileCheck2, Fingerprint, KeyRound, LockKeyhole, Rocket, ShieldCheck, UserRound } from 'lucide-react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { login, register } from '../../api/auth';
import { useAuthStore } from '../../stores/authStore';
import { GridKnowledgeScene } from './GridKnowledgeScene';

interface AuthPageProps {
  mode: 'login' | 'register';
}

interface AuthFormValues {
  username: string;
  password: string;
  displayName?: string;
  companyName?: string;
}

export function AuthPage({ mode }: AuthPageProps): JSX.Element {
  const navigate = useNavigate();
  const { token, setSession } = useAuthStore();
  const isRegister = mode === 'register';

  if (token) {
    return <Navigate to="/" replace />;
  }

  const pageCopy = isRegister
    ? {
      eyebrow: '创建企业账号',
      title: '开启企业 AI 标书全流程工作台',
      description: '从招标文件解析、资料沉淀到正文生成、合规检查和正式文档导出，帮助团队更快形成可交付初稿。',
      cardTitle: '注册账号',
      cardDesc: '创建后即可进入企业标书工作台',
      submit: '注册并进入',
      switchText: '已有账号？',
      switchAction: '返回登录',
    }
    : {
      eyebrow: '欢迎回来',
      title: 'AI 驱动的标书全流程编制平台',
      description: '面向国内企业投标场景，打通招标解析、资料调用、正文生成、合规检查与正式文档导出，让标书编制更快、更准、更可控。',
      cardTitle: '登录工作台',
      cardDesc: '进入你的企业标书项目',
      submit: '登录进入',
      switchText: '还没有账号？',
      switchAction: '创建账号',
    };

  async function handleFinish(values: AuthFormValues) {
    try {
      const session = isRegister
        ? await register(
          values.username,
          values.password,
          values.displayName || values.username,
          values.companyName || '',
        )
        : await login(values.username, values.password);
      setSession(session.token, session.user);
      message.success(isRegister ? '注册成功，已进入工作台' : '登录成功');
      navigate('/', { replace: true });
    } catch (error) {
      message.error(error instanceof Error ? error.message : '操作失败');
    }
  }

  return (
    <main className={`auth-shell ${isRegister ? 'auth-register' : 'auth-login'}`}>
      <GridKnowledgeScene variant={mode} />
      <section className="auth-visual" aria-hidden="true">
        <div className="auth-eyebrow">{pageCopy.eyebrow}</div>
        <div className="auth-copy">
          <h1>{pageCopy.title}</h1>
          <p>{pageCopy.description}</p>
        </div>
        <div className="auth-metrics">
          <div><BookMarked size={22} /><strong>{isRegister ? '资料统一沉淀' : '智能解析招标文件'}</strong><span>{isRegister ? '标书、资信、产品资料集中管理' : '识别评分办法、资格要求和关键响应点'}</span></div>
          <div><FileCheck2 size={22} /><strong>{isRegister ? '流程一站打通' : '复用企业知识资产'}</strong><span>{isRegister ? '解析、生成、检查、导出连贯完成' : '沉淀历史标书、资信文件和项目经验'}</span></div>
          <div><Braces size={22} /><strong>{isRegister ? '企业资料可控' : '全流程生成与校验'}</strong><span>{isRegister ? '适合本地化和私有化部署' : '从大纲、正文到检查和导出形成闭环'}</span></div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <div className="auth-card-header">
            <div className="auth-icon">{isRegister ? <Rocket size={22} /> : <ShieldCheck size={22} />}</div>
            <div>
              <h2>{pageCopy.cardTitle}</h2>
              <p>{pageCopy.cardDesc}</p>
            </div>
          </div>

          <Form layout="vertical" size="large" onFinish={handleFinish} requiredMark={false}>
            <Form.Item
              name="username"
              label="账号"
              rules={[{ required: true, message: '请输入账号' }, { min: 3, message: '账号至少 3 个字符' }]}
            >
              <Input prefix={isRegister ? <Fingerprint size={17} /> : <UserRound size={17} />} autoComplete="username" placeholder={isRegister ? '设置企业登录账号' : '请输入登录账号'} />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }, { min: 8, message: '密码至少 8 位' }]}
            >
              <Input.Password prefix={isRegister ? <KeyRound size={17} /> : <LockKeyhole size={17} />} autoComplete={isRegister ? 'new-password' : 'current-password'} placeholder={isRegister ? '设置至少 8 位密码' : '请输入密码'} />
            </Form.Item>
            <Button type="primary" htmlType="submit" block className="auth-submit">
              {pageCopy.submit} <ArrowRight size={18} />
            </Button>
          </Form>

          <div className="auth-switch">
            {pageCopy.switchText}
            <Link to={isRegister ? '/login' : '/register'}>
              {pageCopy.switchAction}
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
