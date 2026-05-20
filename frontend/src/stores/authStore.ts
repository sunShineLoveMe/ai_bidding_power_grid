import { create } from 'zustand';

export interface AuthUser {
  id: string;
  username: string;
  displayName: string;
  companyName?: string;
  role: string;
}

interface AuthState {
  token: string;
  user: AuthUser | null;
  setSession: (token: string, user: AuthUser) => void;
  clearSession: () => void;
}

const TOKEN_KEY = 'aiBiddingAuthToken';
const USER_KEY = 'aiBiddingAuthUser';

function readUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) as AuthUser : null;
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>(set => ({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: readUser(),
  setSession: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ token, user });
  },
  clearSession: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ token: '', user: null });
  },
}));

export function getAuthToken(): string {
  return useAuthStore.getState().token || localStorage.getItem(TOKEN_KEY) || '';
}
