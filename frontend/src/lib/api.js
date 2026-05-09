import axios from "axios";
export const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const APP_PASSWORD_STORAGE_KEY = "yt-watcher-app-password";

export function getStoredAppPassword() {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(APP_PASSWORD_STORAGE_KEY) || "";
}

export function setStoredAppPassword(password) {
  if (typeof window === "undefined") return;
  if (password) {
    window.localStorage.setItem(APP_PASSWORD_STORAGE_KEY, password);
  } else {
    window.localStorage.removeItem(APP_PASSWORD_STORAGE_KEY);
  }
}

export function clearStoredAppPassword() {
  setStoredAppPassword("");
}

export const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "ngrok-skip-browser-warning": "true",
  },
});
api.interceptors.request.use((config) => {
  const password = getStoredAppPassword();
  if (password) {
    config.headers = config.headers || {};
    config.headers["X-App-Password"] = password;
  }
  return config;
});
export const wsBase = API_BASE.startsWith("/")
  ? `${typeof window !== "undefined" && window.location.protocol === "https:" ? "wss:" : "ws:"}//${typeof window !== "undefined" ? window.location.host : "localhost"}${API_BASE}`
  : API_BASE.replace(/^http/, "ws");
