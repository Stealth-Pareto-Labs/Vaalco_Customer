import type {
  AskResponse,
  ChatMessage,
  DashboardData,
  HistoryEntry,
  LoginResponse,
  Run,
  RunResponse,
  SendResponse,
  StatusResponse
} from "@/lib/types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const TOKEN_KEY = "vaalco_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, signal } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };

  if (auth) {
    const token = getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new ApiError(0, "Network error");
  }

  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data && typeof data === "object" && "detail" in data) {
        const d = (data as { detail: unknown }).detail;
        if (typeof d === "string") detail = d;
      }
    } catch {
      // ignore body parse errors
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export const api = {
  login(code: string): Promise<LoginResponse> {
    return request<LoginResponse>("/auth/login", {
      method: "POST",
      body: { code },
      auth: false
    });
  },

  status(signal?: AbortSignal): Promise<StatusResponse> {
    return request<StatusResponse>("/status", { signal });
  },

  ask(message: string, history: ChatMessage[]): Promise<AskResponse> {
    return request<AskResponse>("/ask", {
      method: "POST",
      body: { message, history }
    });
  },

  signalsLatest(): Promise<Run> {
    return request<Run>("/signals/latest");
  },

  signalsRun(trigger: string, deliver: boolean): Promise<RunResponse> {
    return request<RunResponse>("/signals/run", {
      method: "POST",
      body: { trigger, deliver }
    });
  },

  signalsHistory(): Promise<HistoryEntry[]> {
    return request<HistoryEntry[]>("/signals/history");
  },

  signalsRunById(id: string): Promise<Run> {
    return request<Run>(`/signals/run/${encodeURIComponent(id)}`);
  },

  signalsSend(runId: string | null): Promise<SendResponse> {
    return request<SendResponse>("/signals/send", {
      method: "POST",
      body: { run_id: runId }
    });
  },

  dashboard(signal?: AbortSignal): Promise<DashboardData> {
    return request<DashboardData>("/dashboard", { signal });
  },

  getSettings(): Promise<{ alert_email: string }> {
    return request<{ alert_email: string }>("/settings");
  },

  setAlertEmail(email: string): Promise<{ alert_email: string }> {
    return request<{ alert_email: string }>("/settings/alert-email", {
      method: "POST",
      body: { email }
    });
  }
};

export function previewUrl(id: string): string {
  const token = getToken() ?? "";
  return `${API_BASE}/signals/preview/${encodeURIComponent(id)}?token=${encodeURIComponent(token)}`;
}
