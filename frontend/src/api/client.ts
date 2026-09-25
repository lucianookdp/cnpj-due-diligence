import type {
  ApiError,
  BatchCheck,
  Company,
  Graph,
  GraphDelta,
  TokenResponse,
  WatchlistEntry,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const TOKEN_STORAGE_KEY = "radar_cnpj_token";

class ApiRequestError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } catch {
    // localStorage unavailable (private mode, etc.) — session just won't persist across reloads.
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // no-op
  }
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiError | null;
    throw new ApiRequestError(response.status, body?.detail ?? response.statusText);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export { ApiRequestError };

export function fetchCompany(cnpj: string, expectedActivityDescription?: string): Promise<Company> {
  const query = expectedActivityDescription
    ? `?expected_activity_description=${encodeURIComponent(expectedActivityDescription)}`
    : "";
  return request<Company>(`/companies/${encodeURIComponent(cnpj)}${query}`);
}

export function pdfUrl(cnpj: string, expectedActivityDescription?: string): string {
  const query = expectedActivityDescription
    ? `?expected_activity_description=${encodeURIComponent(expectedActivityDescription)}`
    : "";
  return `${BASE_URL}/companies/${encodeURIComponent(cnpj)}/pdf${query}`;
}

export function register(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function getWatchlist(): Promise<WatchlistEntry[]> {
  return request<WatchlistEntry[]>("/watchlist", { headers: authHeaders() });
}

export function addToWatchlist(cnpj: string, label?: string): Promise<WatchlistEntry> {
  return request<WatchlistEntry>("/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ cnpj, label: label || null }),
  });
}

export function removeFromWatchlist(entryId: string): Promise<void> {
  return request<void>(`/watchlist/${entryId}`, { method: "DELETE", headers: authHeaders() });
}

export function fetchGraph(cnpj: string, depth?: number): Promise<Graph> {
  const query = depth !== undefined ? `?depth=${depth}` : "";
  return request<Graph>(`/graph/${encodeURIComponent(cnpj)}${query}`);
}

export function expandCompanyNode(companyId: string): Promise<GraphDelta> {
  return request<GraphDelta>(`/graph/expand/company/${companyId}`, { method: "POST" });
}

export function expandPersonNode(personId: string): Promise<GraphDelta> {
  return request<GraphDelta>(`/graph/expand/person/${personId}`, { method: "POST" });
}

export function createBatchCheck(cnpjs: string[]): Promise<BatchCheck> {
  return request<BatchCheck>("/batches", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ cnpjs }),
  });
}

export function getBatchCheck(id: string): Promise<BatchCheck> {
  return request<BatchCheck>(`/batches/${id}`, { headers: authHeaders() });
}

export function listBatchChecks(): Promise<BatchCheck[]> {
  return request<BatchCheck[]>("/batches", { headers: authHeaders() });
}
