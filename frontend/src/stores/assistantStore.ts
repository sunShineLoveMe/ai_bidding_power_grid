import { create } from 'zustand';

export interface AssistantMessage {
  id: string;
  role: 'assistant' | 'user';
  content: string;
}

interface AssistantState {
  open: boolean;
  messages: AssistantMessage[];
  setOpen: (open: boolean) => void;
  addMessage: (message: Omit<AssistantMessage, 'id'>) => void;
}

const initialMessages: AssistantMessage[] = [
  {
    id: 'welcome',
    role: 'assistant',
    content: '你好，我是 AI 标书助手。可解答系统使用、标书编写、资料入库等问题。',
  },
];

export const useAssistantStore = create<AssistantState>(set => ({
  open: false,
  messages: initialMessages,
  setOpen: open => set({ open }),
  addMessage: message =>
    set(state => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: `${Date.now()}-${state.messages.length}`,
        },
      ],
    })),
}));
