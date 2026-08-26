import axios, { type InternalAxiosRequestConfig } from "axios";

import { clearAuthStorage, getStoredToken, storeAuthTokens } from "@/utils/auth-storage";
import type { TokenResponse } from "@/interface/auth";

const axiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { "Content-Type": "application/json" },
});

const refreshClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { "Content-Type": "application/json" },
});

axiosInstance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const accessToken = getStoredToken("peka_access_token");
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

axiosInstance.interceptors.response.use(undefined, async (error) => {
  const request = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
  const refreshToken = getStoredToken("peka_refresh_token");

  if (
    error.response?.status !== 401 ||
    !request ||
    request._retry ||
    !refreshToken ||
    request.url?.includes("/auth/refresh")
  ) {
    return Promise.reject(error);
  }

  request._retry = true;
  try {
    const response = await refreshClient.post<TokenResponse>("/auth/refresh", {
      refresh_token: refreshToken,
    });
    storeAuthTokens(response.data);
    request.headers.Authorization = `Bearer ${response.data.access_token}`;
    return axiosInstance(request);
  } catch (refreshError) {
    clearAuthStorage();
    return Promise.reject(refreshError);
  }
});

export default axiosInstance;
