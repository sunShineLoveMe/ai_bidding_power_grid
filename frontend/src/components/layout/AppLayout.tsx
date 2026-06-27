import type { PointerEvent as ReactPointerEvent, PropsWithChildren } from 'react';
import { BookOpen, Box, CircleDollarSign, ClipboardCheck, FileClock, FileSearch, Home, LogOut, Settings, ShieldCheck, Sparkles, UserRound } from 'lucide-react';
import { Button } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { GlobalLoading } from '../common/GlobalLoading';
import { BrandMark } from '../common/BrandMark';
import { KnowledgeSearchDrawer } from '../../pages/KnowledgeBase/KnowledgeSearchDrawer';
import { useLoadingStore } from '../../stores/loadingStore';
import { useAuthStore } from '../../stores/authStore';
import { logout } from '../../api/auth';

const navItems = [
  { path: '/', label: '主页', icon: Home },
  { path: '/interpretation', label: '招标项目', icon: FileSearch },
  { path: '/formal-check', label: '正式检查', icon: ClipboardCheck },
  { path: '/knowledge', label: '企业知识库', icon: BookOpen },
  { path: '/qualification', label: '企业资信库', icon: ShieldCheck },
  { path: '/products', label: '企业产品库', icon: Box },
  { path: '/usage-cost', label: '用量与成本', icon: CircleDollarSign },
  { path: '/history', label: '历史记录', icon: FileClock },
] as const;

const ASSISTANT_POSITION_KEY = 'ai-bidding-knowledge-assistant-position';

type AssistantPosition = { x: number; y: number };

function defaultAssistantPosition(): AssistantPosition {
  if (typeof window === 'undefined') return { x: 0, y: 0 };
  const estimatedWidth = window.innerWidth >= 1536 ? 150 : 48;
  return {
    x: window.innerWidth - estimatedWidth - 28,
    y: window.innerHeight - 120,
  };
}

function clampAssistantPosition(position: AssistantPosition, element?: HTMLElement | null): AssistantPosition {
  if (typeof window === 'undefined') return position;
  const margin = 12;
  const headerGuard = 76;
  const footerGuard = 60;
  const width = element?.offsetWidth || (window.innerWidth >= 1536 ? 150 : 48);
  const height = element?.offsetHeight || 48;
  return {
    x: Math.min(Math.max(position.x, margin), window.innerWidth - width - margin),
    y: Math.min(Math.max(position.y, headerGuard), window.innerHeight - height - footerGuard),
  };
}

function readAssistantPosition(): AssistantPosition {
  const fallback = defaultAssistantPosition();
  if (typeof window === 'undefined') return fallback;
  try {
    const raw = window.localStorage.getItem(ASSISTANT_POSITION_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<AssistantPosition>;
    if (typeof parsed.x === 'number' && typeof parsed.y === 'number') {
      return { x: parsed.x, y: parsed.y };
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export function AppLayout({ children }: PropsWithChildren): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const [knowledgeAssistantOpen, setKnowledgeAssistantOpen] = useState(false);
  const assistantButtonRef = useRef<HTMLButtonElement | null>(null);
  const dragStateRef = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number; dragged: boolean } | null>(null);
  const [assistantPosition, setAssistantPosition] = useState<AssistantPosition>(() => readAssistantPosition());
  const [assistantDragging, setAssistantDragging] = useState(false);
  const pendingCount = useLoadingStore(state => state.pendingCount);
  const user = useAuthStore(state => state.user);
  const clearSession = useAuthStore(state => state.clearSession);
  const loadingLocked = pendingCount > 0;

  async function handleLogout() {
    try {
      await logout();
    } finally {
      clearSession();
      navigate('/login', { replace: true });
    }
  }

  useEffect(() => {
    const handleResize = () => {
      setAssistantPosition(position => {
        const next = clampAssistantPosition(position, assistantButtonRef.current);
        window.localStorage.setItem(ASSISTANT_POSITION_KEY, JSON.stringify(next));
        return next;
      });
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  function handleAssistantPointerDown(event: ReactPointerEvent<HTMLButtonElement>): void {
    if (event.button !== 0) return;
    const origin = clampAssistantPosition(assistantPosition, assistantButtonRef.current);
    dragStateRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: origin.x,
      originY: origin.y,
      dragged: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleAssistantPointerMove(event: ReactPointerEvent<HTMLButtonElement>): void {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    const dx = event.clientX - dragState.startX;
    const dy = event.clientY - dragState.startY;
    if (!dragState.dragged && Math.hypot(dx, dy) < 4) return;
    dragState.dragged = true;
    setAssistantDragging(true);
    setAssistantPosition(clampAssistantPosition({ x: dragState.originX + dx, y: dragState.originY + dy }, assistantButtonRef.current));
  }

  function finishAssistantDrag(event: ReactPointerEvent<HTMLButtonElement>): void {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    const next = clampAssistantPosition({
      x: dragState.originX + event.clientX - dragState.startX,
      y: dragState.originY + event.clientY - dragState.startY,
    }, assistantButtonRef.current);
    setAssistantPosition(next);
    window.localStorage.setItem(ASSISTANT_POSITION_KEY, JSON.stringify(next));
    setAssistantDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleAssistantClick(): void {
    const dragged = dragStateRef.current?.dragged;
    dragStateRef.current = null;
    if (dragged) return;
    setKnowledgeAssistantOpen(true);
  }

  return (
    <div className="h-screen overflow-hidden bg-slate-50 text-slate-950">
      <header className="fixed left-0 right-0 top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-7 shadow-[0_2px_12px_rgba(22,35,72,0.04)]">
        <div className="flex items-center gap-3 text-[26px] font-black tracking-normal">
          <BrandMark size={40} />
          <span>AI标书系统</span>
        </div>
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-bold text-slate-600">
            <UserRound size={16} />
            <span>{user?.displayName || user?.username || '当前用户'}</span>
          </div>
          <Button type="text" icon={<Settings size={18} />} onClick={() => navigate('/settings')}>
            系统设置
          </Button>
          <Button type="text" icon={<LogOut size={18} />} onClick={handleLogout}>
            退出
          </Button>
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
        ref={assistantButtonRef}
        type="primary"
        title="知识库助手"
        aria-label="知识库助手"
        className={`knowledge-assistant-fab ${assistantDragging ? 'knowledge-assistant-fab-dragging' : ''}`}
        style={{ left: assistantPosition.x, top: assistantPosition.y }}
        icon={<Sparkles size={16} />}
        onPointerDown={handleAssistantPointerDown}
        onPointerMove={handleAssistantPointerMove}
        onPointerUp={finishAssistantDrag}
        onPointerCancel={finishAssistantDrag}
        onClick={handleAssistantClick}
      >
        <span className="hidden 2xl:inline">知识库助手</span>
      </Button>

      <KnowledgeSearchDrawer
        visible={knowledgeAssistantOpen}
        onClose={() => setKnowledgeAssistantOpen(false)}
      />

      <footer className="fixed bottom-0 left-0 right-0 z-30 flex h-12 items-center justify-between border-t border-slate-200 bg-white px-7 text-sm font-semibold text-slate-500">
        <span>国家电网投标智能工作台 · 招标解析 · 标书编制 · 正式检查</span>
        <span>企业资料本地可控 · 支持内网部署 · 面向真实投标交付</span>
      </footer>
    </div>
  );
}
