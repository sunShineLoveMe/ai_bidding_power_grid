import { create } from 'zustand';
import type { RecentTask } from '../types/bid';
import { formatNow } from '../utils/format';

interface BidProjectState {
  recentTasks: RecentTask[];
  addTask: (task: Omit<RecentTask, 'id' | 'createdAt'>) => void;
}

export const useBidProjectStore = create<BidProjectState>(set => ({
  recentTasks: [],
  addTask: task =>
    set(state => ({
      recentTasks: [
        {
          ...task,
          id: `${Date.now()}`,
          createdAt: formatNow(),
        },
        ...state.recentTasks,
      ].slice(0, 5),
    })),
}));
