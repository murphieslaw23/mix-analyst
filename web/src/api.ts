import axios from 'axios';

export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const API_KEY_STORAGE = 'syco_api_key';

export const getApiKey = (): string => {
  try {
    return localStorage.getItem(API_KEY_STORAGE) || '';
  } catch {
    return '';
  }
};

export const setApiKey = (key: string): void => {
  try {
    localStorage.setItem(API_KEY_STORAGE, key);
  } catch {
    // storage unavailable (private mode) — key simply won't persist
  }
};

export const authHeaders = (): Record<string, string> => {
  const key = getApiKey();
  return key ? { 'X-API-Key': key } : {};
};

export const api = axios.create({ baseURL: API_BASE });
