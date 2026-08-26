import axios, { type InternalAxiosRequestConfig } from 'axios';

import type { TokenResponse } from '@/interface/auth';

const axiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { 'Content-Type': 'application/json' },
});

const refreshClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { 'Content-Type': 'application/json' },
});

function token(name: string) {
  return typeof window === 'undefined' ? null : sessionStorage.getItem(name);
}

function storeTokens(tokens: TokenResponse) {
  sessionStorage.setItem('peka_access_token', tokens.access_token);
  sessionStorage.setItem('peka_refresh_token', tokens.refresh_token);
  document.cookie = `peka_access_token=${encodeURIComponent(tokens.access_token)}; Max-Age=${tokens.expires_in}; Path=/; SameSite=Lax`;
}

axiosInstance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const accessToken = token('peka_access_token');
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

axiosInstance.interceptors.response.use(undefined, async (error) => {
  const request = error.config as InternalAxiosRequestConfig & { _retry?: boolean } | undefined;
  const refreshToken = token('peka_refresh_token');

  if (error.response?.status !== 401 || !request || request._retry || !refreshToken || request.url?.includes('/auth/refresh')) {
    return Promise.reject(error);
  }

  request._retry = true;
  try {
    const response = await refreshClient.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken });
    storeTokens(response.data);
    request.headers.Authorization = `Bearer ${response.data.access_token}`;
    return axiosInstance(request);
  } catch (refreshError) {
    sessionStorage.removeItem('peka_access_token');
    sessionStorage.removeItem('peka_refresh_token');
    document.cookie = 'peka_access_token=; Max-Age=0; Path=/; SameSite=Lax';
    return Promise.reject(refreshError);
  }
});

export default axiosInstance;
