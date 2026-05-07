import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export const api = axios.create({
  baseURL: API_BASE,
});

export const wsBase = API_BASE.startsWith('/')
  ? `${typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${typeof window !== 'undefined' ? window.location.host : 'localhost'}${API_BASE}`
  : API_BASE.replace(/^http/, 'ws');
