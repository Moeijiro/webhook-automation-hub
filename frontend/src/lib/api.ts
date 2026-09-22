/**
 * One fetch wrapper for the dashboard.
 *
 * Requests always send credentials: the session is an HttpOnly cookie the
 * frontend can neither read nor forge. API keys exist for scripts, not for
 * the browser, so none is ever stored here.
 */

import type {
  ActionCatalogEntry,
  ApiKey,
  CreatedApiKey,
  ExecutionPage,
  Stats,
  User,
  Workflow,
  WorkflowDetail,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: init.body ? { "Content-Type": "application/json" } : undefined,
    ...init,
  });

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, readError(payload) ?? response.statusText);
  }
  return payload as T;
}

/** FastAPI reports validation errors as a list; flatten it to one line. */
function readError(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const entry = item as { loc?: unknown[]; msg?: string };
        const field = entry.loc?.slice(1).join(".") ?? "";
        return field ? `${field}: ${entry.msg}` : entry.msg;
      })
      .join("; ");
  }
  return null;
}

interface ExecutionQuery {
  limit?: number;
  offset?: number;
  status?: string;
  workflow_id?: number;
}

function query(params: ExecutionQuery): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  authConfig: () => request<{ registration_enabled: boolean }>("/api/auth/config"),
  me: () => request<User>("/api/auth/me"),
  register: (email: string, password: string) =>
    request<User>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),

  stats: () => request<Stats>("/api/stats"),
  actions: () => request<ActionCatalogEntry[]>("/api/actions"),

  workflows: () => request<Workflow[]>("/api/workflows"),
  workflow: (id: number) => request<WorkflowDetail>(`/api/workflows/${id}`),
  createWorkflow: (body: unknown) =>
    request<WorkflowDetail>("/api/workflows", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateWorkflow: (id: number, body: unknown) =>
    request<Workflow>(`/api/workflows/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteWorkflow: (id: number) =>
    request<void>(`/api/workflows/${id}`, { method: "DELETE" }),

  executions: (params: ExecutionQuery = {}) =>
    request<ExecutionPage>(`/api/executions${query(params)}`),
  workflowLogs: (id: number, params: ExecutionQuery = {}) =>
    request<ExecutionPage>(`/api/workflows/${id}/logs${query(params)}`),

  apiKeys: () => request<ApiKey[]>("/api/api-keys"),
  createApiKey: (name: string) =>
    request<CreatedApiKey>("/api/api-keys", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  revokeApiKey: (id: number) =>
    request<void>(`/api/api-keys/${id}`, { method: "DELETE" }),
};
