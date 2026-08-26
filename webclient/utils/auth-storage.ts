import type { TokenResponse } from '@/interface/auth';

const ACCESS_TOKEN_KEY = 'peka_access_token';
const REFRESH_TOKEN_KEY = 'peka_refresh_token';
const REMEMBER_ME_KEY = 'peka_remember_me';

function clearTokenStorage(storage: Storage) {
  storage.removeItem(ACCESS_TOKEN_KEY);
  storage.removeItem(REFRESH_TOKEN_KEY);
}

export function getStoredToken(key: string) {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(key) ?? sessionStorage.getItem(key);
}

export function storeAuthTokens(tokens: TokenResponse, rememberMe?: boolean) {
  if (typeof window === 'undefined') return;

  const persistent = rememberMe ?? localStorage.getItem(REMEMBER_ME_KEY) === 'true';
  const storage = persistent ? localStorage : sessionStorage;
  const otherStorage = persistent ? sessionStorage : localStorage;
  clearTokenStorage(otherStorage);

  if (persistent) {
    localStorage.setItem(REMEMBER_ME_KEY, 'true');
  } else {
    localStorage.removeItem(REMEMBER_ME_KEY);
  }

  storage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  storage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  const maxAge = persistent ? ` Max-Age=${tokens.expires_in};` : '';
  document.cookie = `peka_access_token=${encodeURIComponent(tokens.access_token)};${maxAge} Path=/; SameSite=Lax`;
}

export function clearAuthStorage() {
  if (typeof window === 'undefined') return;

  clearTokenStorage(localStorage);
  clearTokenStorage(sessionStorage);
  localStorage.removeItem(REMEMBER_ME_KEY);
  document.cookie = 'peka_access_token=; Max-Age=0; Path=/; SameSite=Lax';
}
