import { create } from 'zustand';

interface LoadingState {
  pendingCount: number;
  message: string;
  start: (message?: string) => void;
  finish: () => void;
}

export const useLoadingStore = create<LoadingState>(set => ({
  pendingCount: 0,
  message: '正在处理请求...',
  start: message =>
    set(state => ({
      pendingCount: state.pendingCount + 1,
      message: message || state.message || '正在处理请求...',
    })),
  finish: () =>
    set(state => ({
      pendingCount: Math.max(0, state.pendingCount - 1),
      message: state.pendingCount <= 1 ? '正在处理请求...' : state.message,
    })),
}));
