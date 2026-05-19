import type { PropsWithChildren } from 'react';
import { BookOpen, Box, CircleDollarSign, FileClock, FileSearch, Home, Settings, ShieldCheck, Sparkles } from 'lucide-react';
import { Button, Tag } from 'antd';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { GlobalLoading } from '../common/GlobalLoading';
import { BrandMark } from '../common/BrandMark';
import { KnowledgeSearchDrawer } from '../../pages/KnowledgeBase/KnowledgeSearchDrawer';
import { useLoadingStore } from '../../stores/loadingStore';

const navItems = [
  { path: '/', label: '主页', icon: Home },
  { path: '/interpretation', label: '招标项目', icon: FileSearch },
  { path: '/knowledge', label: '企业知识库', icon: BookOpen },
  { path: '/qualification', label: '企业资信库', icon: ShieldCheck },
  { path: '/products', label: '企业产品库', icon: Box },
  { path: '/usage-cost', label: '用量与成本', icon: CircleDollarSign },
  { path: '/history', label: '历史记录', icon: FileClock },
] as const;

export function AppLayout({ children }: PropsWithChildren): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const [knowledgeAssistantOpen, setKnowledgeAssistantOpen] = useState(false);
  const pendingCount = useLoadingStore(state => state.pendingCount);
  const loadingLocked = pendingCount > 0;

  return (
    <div className="h-screen overflow-hidden bg-slate-50 text-slate-950">
      <header className="fixed left-0 right-0 top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-7 shadow-[0_2px_12px_rgba(22,35,72,0.04)]">
        <div className="flex items-center gap-3 text-[26px] font-black tracking-normal">
          <BrandMark size={40} />
          <span>AI标书系统</span>
        </div>
        <div className="flex items-center gap-5">
          <Button type="text" icon={<Settings size={18} />} onClick={() => navigate('/settings')}>
            系统设置
          </Button>
          <Tag className="m-0 rounded-lg border-blue-300 px-4 py-1.5 text-base font-bold text-blue-600">v0.1 单机版</Tag>
        </div>
      </header>

      <aside className="fixed bottom-12 left-0 top-16 z-20 w-60 border-r border-slate-200 bg-white px-5 py-7">
        <nav className="grid gap-3" aria-label="主导航">
          {navItems.map(item => {
            const Icon = item.icon;
            const active = location.pathname === item.path || (item.path === '/' && location.pathname === '/bidding');
            return (
              <button
                key={item.path}
                type="button"
                className={`flex h-14 items-center gap-4 rounded-xl px-4 text-left text-base font-bold transition ${
                  active ? 'bg-blue-50 text-blue-600' : 'text-slate-600 hover:bg-slate-50'
                }`}
                onClick={() => navigate(item.path)}
              >
                <Icon size={22} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className={`fixed bottom-12 left-60 right-0 top-16 overflow-x-hidden p-5 ${loadingLocked ? 'overflow-hidden' : 'overflow-y-auto'}`}>
        {children}
        <GlobalLoading />
      </main>

      <Button
        type="primary"
        className="fixed bottom-[72px] right-7 z-40 h-14 rounded-full bg-gradient-to-r from-blue-600 to-cyan-500 px-6 text-base font-black shadow-xl shadow-blue-200"
        icon={<Sparkles size={19} />}
        onClick={() => setKnowledgeAssistantOpen(true)}
      >
        知识库助手
      </Button>

      <KnowledgeSearchDrawer
        visible={knowledgeAssistantOpen}
        onClose={() => setKnowledgeAssistantOpen(false)}
      />

      <footer className="fixed bottom-0 left-0 right-0 z-30 flex h-12 items-center justify-between border-t border-slate-200 bg-white px-7 text-sm font-semibold text-slate-500">
        <span>企业单机部署版 · 招标项目 · 知识库问答 · 标书编制</span>
        <span>数据本地可控 · 支持内网部署 · 面向水利招投标场景</span>
      </footer>
    </div>
  );
}
