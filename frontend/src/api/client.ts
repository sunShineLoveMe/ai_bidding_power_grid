import axios from 'axios';
import { useLoadingStore } from '../stores/loadingStore';

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipGlobalLoading?: boolean;
  }
}

export const apiClient = axios.create({
  baseURL: '/',
  timeout: 120000,
});

apiClient.interceptors.request.use(
  config => {
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
    const message = error.response?.data?.error || error.message || '请求失败';
    return Promise.reject(new Error(message));
  },
);
