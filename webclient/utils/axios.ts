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
  if (config.data instanceof FormData) delete config.headers["Content-Type"];
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

export async function fetchAuthenticated(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const request = (accessToken: string | null) => {
    const headers = new Headers(init.headers);
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(input, { ...init, headers });
  };

  const response = await request(getStoredToken("peka_access_token"));
  if (response.status !== 401) return response;

  const refreshToken = getStoredToken("peka_refresh_token");
  if (!refreshToken) return response;

  try {
    const refreshResponse = await refreshClient.post<TokenResponse>("/auth/refresh", {
      refresh_token: refreshToken,
    });
    storeAuthTokens(refreshResponse.data);
    return request(getStoredToken("peka_access_token"));
  } catch (error) {
    clearAuthStorage();
    throw error;
  }
}

export default axiosInstance;
