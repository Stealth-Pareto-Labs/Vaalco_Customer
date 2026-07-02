export type Priority = "high" | "medium" | "low";

export type ChartType = "line" | "bar";

export interface ChartSpec {
  type: ChartType;
  labels: (string | number)[];
  values: number[];
  field?: string;
  y_label?: string;
  title?: string;
}

export interface TraceItem {
  tool: string;
  arguments: Record<string, unknown>;
}

export interface AskResponse {
  answer: string;
  trace: TraceItem[];
  charts: ChartSpec[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface Counts {
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface EvidenceItem {
  label: string;
  value: string | number;
}

export interface Signal {
  id: string;
  priority: Priority;
  category: string;
  title: string;
  explanation?: string;
  summary?: string;
  evidence: EvidenceItem[];
  next_steps: string[];
  probe?: string;
}

export interface Run {
  run_id: string;
  generated_at: string;
  trigger: string;
  vessel: string;
  field: string;
  operator: string;
  as_of: string;
  date_range: string;
  reports_loaded: number;
  counts: Counts;
  executive_summary: string;
  narrated_by_model: boolean;
  signals: Signal[];
}

export interface HistoryEntry {
  run_id: string;
  generated_at: string;
  trigger: string;
  as_of: string;
  headline: string;
  counts: Counts;
}

export interface StatusResponse {
  api_key: boolean;
  provider: string;
  days: number;
  new_reports: unknown[];
}

export interface LoginResponse {
  token: string;
  expires_in: number;
}

export interface RunResponse {
  run_id: string;
  run: Run;
  delivery: unknown;
}

export interface SendResponse {
  run_id: string;
  delivery: unknown;
}
