import axios from 'axios';
import { useLoadingStore } from '../stores/loadingStore';
import { getAuthToken, useAuthStore } from '../stores/authStore';

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipGlobalLoading?: boolean;
  }
}

export const apiClient = axios.create({
  baseURL: '/',
  timeout: 120000,
  withCredentials: true,
});

apiClient.interceptors.request.use(
  config => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (!config.skipGlobalLoading) {
      useLoadingStore.getState().start();
    }
    return config;
  },
  error => {
    if (!error.config?.skipGlobalLoading) {
      useLoadingStore.getState().finish();
    }
    return Promise.reject(error);
  },
);

apiClient.interceptors.response.use(
  response => {
    if (!response.config.skipGlobalLoading) {
      useLoadingStore.getState().finish();
    }
    return response;
  },
  error => {
    if (!error.config?.skipGlobalLoading) {
      useLoadingStore.getState().finish();
    }
    if (error.response?.status === 401) {
      useAuthStore.getState().clearSession();
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
        window.location.href = '/login';
      }
    }
    const message = error.response?.data?.error || error.message || '请求失败';
    return Promise.reject(new Error(message));
  },
);
