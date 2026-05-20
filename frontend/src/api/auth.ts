import { apiClient } from './client';
import type { AuthUser } from '../stores/authStore';

interface AuthResponse {
  token: string;
  user: AuthUser;
}

export async function login(username: string, password: string): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>('/api/users/login', { username, password });
  return response.data;
}

export async function register(
  username: string,
  password: string,
  displayName: string,
  companyName: string,
): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>('/api/users/register', {
    username,
    password,
    displayName,
    companyName,
  });
  return response.data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/api/users/logout', {}, { skipGlobalLoading: true });
}
