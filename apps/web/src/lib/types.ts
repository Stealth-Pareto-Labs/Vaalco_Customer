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

export interface DeliveryResult {
  email?: {
    sent?: boolean;
    simulated?: boolean;
    provider?: string;
    error?: string;
    detail?: string;
    to?: string[];
    id?: string;
  };
  sms?: { sent?: boolean; detail?: string };
}

export interface SendResponse {
  run_id: string;
  delivery: DeliveryResult | null;
}

export interface SettingsConfig {
  emails: string[];
  digest_enabled: boolean;
  digest_time: string; // "HH:MM"
  timezone: string;
  critical_immediate: boolean;
}

// ---- Dashboard ----
export interface FuelPoint {
  date: string;
  actual_L: number;
  expected_L: number;
  deviation_L: number;
  cost_usd: number;
  dp_hours: number | null;
  L_per_dp_hour: number | null;
}

export interface MaintenanceItem {
  machine: string;
  total_run_hours: number | null;
  next_target_h: number | null;
  hours_remaining: number | null;
  days_to_service: number | null;
  status: string;
}

export interface FluidItem {
  name: string;
  balance: number | null;
  consumed: number | null;
  unit: string | null;
  days_to_empty: number | null;
  is_waste: boolean;
}

export interface DpEffDay {
  date: string;
  dp_hours: number;
  fuel_L: number;
  L_per_dp_hour: number;
}

export interface DashboardData {
  as_of: string;
  vessel: string;
  field: string;
  reports_loaded: number;
  date_range: string;
  mgo_price_per_m3: number;
  model: { base_L: number; rate: number; sd: number };
  kpis: {
    mean_daily_fuel_L: number;
    mean_daily_cost_usd: number;
    annualised_cost_usd: number;
    net_deviation_L: number;
    net_cost_impact_usd: number;
    worst_day: string;
    worst_day_deviation_L: number;
  };
  signal_counts: Counts;
  fuel_series: FuelPoint[];
  dp_efficiency: {
    days: DpEffDay[];
    best: DpEffDay | null;
    worst: DpEffDay | null;
    spread_percent: number | null;
  };
  maintenance: MaintenanceItem[];
  fluids: FluidItem[];
  engine: {
    me1_temps: number[];
    me2_temps: number[];
    me1_deviation: number | null;
    me2_deviation: number | null;
    telemetry_is_static: boolean;
    note: string;
  } | null;
  hse: {
    tallies: Record<string, number>;
    near_misses: number | null;
  } | null;
  error?: string;
}
