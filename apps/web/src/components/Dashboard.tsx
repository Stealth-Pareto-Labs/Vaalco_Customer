"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode
} from "react";
import { AlertTriangle, Loader2, Info } from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  Cell
} from "recharts";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { DashboardData } from "@/lib/types";

const REFRESH_MS = 20000;

/* Palette (mirrors the design tokens in globals.css) */
const C = {
  primary: "#3b82f6",
  hi: "#e0584f",
  med: "#d99a3c",
  lo: "#4a9cb0",
  mut: "#869199",
  accent: "#d97706"
};

const GRID = "rgba(255,255,255,0.05)";
const axisTick = { fill: "#8a959c", fontSize: 11 };
const axisTickSm = { fill: "#8a959c", fontSize: 10 };

const tooltipStyle: CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--line2)",
  borderRadius: 8,
  fontFamily: "var(--font-mono), ui-monospace, monospace",
  fontSize: 12
};
const tooltipProps = {
  contentStyle: tooltipStyle,
  labelStyle: { color: "var(--mut)" },
  itemStyle: { color: "var(--ink)" }
} as const;

/* ---------- small helpers ---------- */

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return reduced;
}

const num = (n: number | null | undefined): string =>
  n == null ? "—" : n.toLocaleString();

function usdCompact(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}

const mmdd = (iso: string): string => (iso && iso.length >= 10 ? iso.slice(5) : iso);

/** interpolate {tokens} in an i18n string */
function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) =>
    k in vars ? String(vars[k]) : `{${k}}`
  );
}

/* ---------- component ---------- */

export default function Dashboard({ active }: { active: boolean }) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const anim = !reduced;

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dataRef = useRef<DashboardData | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    if (!dataRef.current) setLoading(true);
    try {
      const d = await api.dashboard(ctrl.signal);
      dataRef.current = d;
      setData(d);
      setError(null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (err instanceof Error && err.name === "AbortError") return;
      // keep previous data on refresh failures; only surface an error on first load
      if (!dataRef.current) {
        setError(err instanceof ApiError ? err.message : t("common.error"));
      }
    } finally {
      if (!ctrl.signal.aborted) setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (!active) return;
    void load();
    const id = setInterval(() => void load(), REFRESH_MS);
    return () => {
      clearInterval(id);
      abortRef.current?.abort();
    };
  }, [active, load]);

  /* ----- first load / error / empty gates ----- */

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-[14px] text-mut">
        <Loader2 size={26} className="spin text-primary" aria-hidden="true" />
        {t("dashboard.loading")}
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="py-4">
        <div
          className="flex items-center justify-between gap-3 rounded-xl border px-4 py-4"
          style={{ borderColor: "var(--hi)", background: "var(--hi-bg)" }}
        >
          <span className="flex items-center gap-2 text-[15px] text-ink">
            <AlertTriangle size={18} style={{ color: "var(--hi)" }} aria-hidden="true" />
            {error}
          </span>
          <button
            type="button"
            onClick={() => void load()}
            className="focus-ring cursor-pointer rounded-lg border border-line2 bg-surface2 px-3 py-1.5 text-[14px] font-medium text-ink transition-colors duration-150 hover:border-primary"
          >
            {t("dashboard.retry")}
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  if (data.error || data.reports_loaded === 0) {
    return (
      <div className="py-4">
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line2 bg-surface/50 px-4 py-16 text-center">
          <Info size={22} className="text-mut2" aria-hidden="true" />
          <div className="text-[15px] font-medium text-ink">{t("dashboard.empty.title")}</div>
          <div className="max-w-sm text-[13px] text-mut">{t("dashboard.empty.body")}</div>
        </div>
      </div>
    );
  }

  /* ----- derived series (all guarded) ----- */

  const kpis = data.kpis;
  const model = data.model;
  const counts = data.signal_counts;
  const fuelSeries = Array.isArray(data.fuel_series) ? data.fuel_series : [];
  const dpDays = Array.isArray(data.dp_efficiency?.days) ? data.dp_efficiency.days : [];
  const spread = data.dp_efficiency?.spread_percent ?? null;
  const bestDate = data.dp_efficiency?.best?.date ?? null;
  const worstDate = data.dp_efficiency?.worst?.date ?? null;

  const fuelData = fuelSeries.map((p) => ({
    date: mmdd(p.date),
    actual_L: p.actual_L,
    expected_L: p.expected_L
  }));

  const costData = fuelSeries.map((p) => ({ date: mmdd(p.date), cost_usd: p.cost_usd }));

  const dpData = dpDays.map((d) => ({
    date: mmdd(d.date),
    rawDate: d.date,
    L_per_dp_hour: d.L_per_dp_hour
  }));

  // scatter: fuel vs DP hours, split by deviation sign, with a model line
  const scatterPts = fuelSeries.filter((p) => p.dp_hours != null);
  const scatterOver = scatterPts
    .filter((p) => p.deviation_L > 0)
    .map((p) => ({ x: p.dp_hours as number, y: p.actual_L }));
  const scatterSaved = scatterPts
    .filter((p) => p.deviation_L <= 0)
    .map((p) => ({ x: p.dp_hours as number, y: p.actual_L }));
  const dpXs = scatterPts.map((p) => p.dp_hours as number);
  const xMin = dpXs.length ? Math.min(...dpXs) : 0;
  const xMax = dpXs.length ? Math.max(...dpXs) : 1;
  const modelSegment = [
    { x: xMin, y: model.base_L + model.rate * xMin },
    { x: xMax, y: model.base_L + model.rate * xMax }
  ];

  // maintenance: hours to next service
  const maint = (Array.isArray(data.maintenance) ? data.maintenance : []).filter(
    (m) => m.hours_remaining != null
  );
  const maintColor = (m: (typeof maint)[number]): string => {
    const status = (m.status || "").toLowerCase();
    const urgent =
      status === "overdue" ||
      (m.hours_remaining ?? 0) < 0 ||
      (m.days_to_service != null && m.days_to_service <= 3);
    if (urgent) return C.hi;
    if (status.includes("due soon")) return C.med;
    return C.lo;
  };

  // fluids: only non-waste with a days-to-empty, ascending, top 8
  const fluids = (Array.isArray(data.fluids) ? data.fluids : [])
    .filter((f) => !f.is_waste && f.days_to_empty != null)
    .sort((a, b) => (a.days_to_empty as number) - (b.days_to_empty as number))
    .slice(0, 8)
    .map((f) => ({ name: f.name, days_to_empty: f.days_to_empty as number }));
  const fluidColor = (d: number): string => (d <= 3 ? C.hi : d <= 7 ? C.med : C.lo);

  // engine temps: grouped per cylinder
  const engine = data.engine;
  const me1 = engine?.me1_temps ?? [];
  const me2 = engine?.me2_temps ?? [];
  const cylN = Math.max(me1.length, me2.length);
  const engineData = Array.from({ length: cylN }, (_, i) => ({
    cyl: i + 1,
    me1: me1[i] ?? null,
    me2: me2[i] ?? null
  }));
  const engineStatic = !!engine?.telemetry_is_static;

  // HSE: non-zero tallies mapped to short labels
  const hseTallies = data.hse?.tallies ?? {};
  const hseLabel = (key: string): string => {
    const k = key.toLowerCase();
    if (k.includes("near miss")) return t("dashboard.hse.nearMisses");
    if (k.includes("drill")) return t("dashboard.hse.drills");
    if (k.includes("tool box") || k.includes("toolbox")) return t("dashboard.hse.toolbox");
    if (k.includes("risk assess")) return t("dashboard.hse.riskAssessments");
    if (k.includes("permit")) return t("dashboard.hse.ptw");
    if (k.includes("workdays")) return t("dashboard.hse.workdaysLost");
    if (k.includes("property")) return t("dashboard.hse.propertyDamage");
    if (k.includes("medical")) return t("dashboard.hse.medical");
    return key;
  };
  const hseItems = Object.entries(hseTallies)
    .filter(([, v]) => typeof v === "number" && v !== 0)
    .map(([key, v]) => ({
      key,
      label: hseLabel(key),
      value: v,
      highlight: key.toLowerCase().includes("near miss")
    }));

  const net = kpis.net_cost_impact_usd;
  const netColor = net > 0 ? C.hi : net < 0 ? C.lo : C.mut;
  const signSym = (n: number) => (n > 0 ? "+" : n < 0 ? "−" : "");

  return (
    <div className="space-y-8 py-4">
      {/* Meta strip */}
      <div className="mono flex flex-wrap gap-x-4 gap-y-1 px-1 text-[12px] text-mut2">
        <span>{data.vessel}</span>
        <span>{data.field}</span>
        <span>
          {t("dashboard.asOf")} {data.as_of}
        </span>
        <span>{data.date_range}</span>
        <span>
          {data.reports_loaded} {t("dashboard.reports")}
        </span>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label={t("dashboard.kpi.avgFuel")}
          value={`${num(kpis.mean_daily_fuel_L)} ${t("dashboard.unit.L")}`}
          sub={`$${num(kpis.mean_daily_cost_usd)} ${t("dashboard.kpi.perDay")}`}
        />
        <KpiCard
          label={t("dashboard.kpi.annualCost")}
          value={usdCompact(kpis.annualised_cost_usd)}
          sub={`$${num(kpis.annualised_cost_usd)}`}
        />
        <KpiCard
          label={t("dashboard.kpi.netVsModel")}
          value={`${signSym(net)}$${num(Math.abs(net))}`}
          valueColor={netColor}
          sub={`${signSym(kpis.net_deviation_L)}${num(Math.abs(kpis.net_deviation_L))} ${t("dashboard.unit.L")} · ${
            net > 0 ? t("dashboard.kpi.overspent") : t("dashboard.kpi.saved")
          }`}
        />
        <KpiCard label={t("dashboard.kpi.openSignals")} value={String(counts.total)}>
          <div className="mt-2 flex items-center gap-1.5">
            <SignalChip value={counts.high} color={C.hi} letter={t("dashboard.chip.high")} />
            <SignalChip value={counts.medium} color={C.med} letter={t("dashboard.chip.medium")} />
            <SignalChip value={counts.low} color={C.lo} letter={t("dashboard.chip.low")} />
          </div>
        </KpiCard>
      </div>

      {/* Section: Fuel & cost */}
      <section className="space-y-5">
        <SectionHeader>{t("dashboard.section.fuelCost")}</SectionHeader>

        <ChartCard
          title={t("dashboard.chart.fuelActual.title")}
          subtitle={t("dashboard.chart.fuelActual.sub")}
          height={260}
        >
          <ComposedChart data={fuelData} margin={{ top: 6, right: 16, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="date" tick={axisTick} stroke="var(--line2)" tickLine={false} />
            <YAxis
              tick={axisTick}
              stroke="var(--line2)"
              tickLine={false}
              width={54}
              label={yLabel(t("dashboard.axis.litres"))}
            />
            <Tooltip cursor={{ stroke: "var(--line2)" }} {...tooltipProps} />
            <Legend wrapperStyle={legendStyle} />
            <Line
              type="monotone"
              dataKey="actual_L"
              name={t("dashboard.legend.actual")}
              stroke={C.primary}
              strokeWidth={2}
              dot={{ r: 2, fill: C.primary }}
              activeDot={{ r: 4 }}
              isAnimationActive={anim}
            />
            <Line
              type="monotone"
              dataKey="expected_L"
              name={t("dashboard.legend.expected")}
              stroke={C.mut}
              strokeWidth={1.75}
              strokeDasharray="5 4"
              dot={false}
              isAnimationActive={anim}
            />
          </ComposedChart>
        </ChartCard>

        <ChartCard
          title={t("dashboard.chart.fuelCost.title")}
          subtitle={t("dashboard.chart.fuelCost.sub")}
          height={240}
        >
          <BarChart data={costData} margin={{ top: 6, right: 16, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="date" tick={axisTick} stroke="var(--line2)" tickLine={false} />
            <YAxis
              tick={axisTick}
              stroke="var(--line2)"
              tickLine={false}
              width={54}
              label={yLabel(t("dashboard.axis.costDay"))}
            />
            <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} {...tooltipProps} />
            <ReferenceLine y={0} stroke="var(--line2)" />
            <Bar
              dataKey="cost_usd"
              name={t("dashboard.axis.costDay")}
              radius={[3, 3, 0, 0]}
              maxBarSize={44}
              isAnimationActive={anim}
            >
              {costData.map((d, i) => (
                <Cell key={i} fill={d.cost_usd >= 0 ? C.hi : C.lo} />
              ))}
            </Bar>
          </BarChart>
        </ChartCard>
      </section>

      {/* Section: Efficiency & workload */}
      <section className="space-y-5">
        <SectionHeader>{t("dashboard.section.efficiency")}</SectionHeader>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <ChartCard
            title={t("dashboard.chart.dpEff.title")}
            subtitle={fill(t("dashboard.chart.dpEff.sub"), { spread: spread ?? "—" })}
          >
            <BarChart data={dpData} margin={{ top: 6, right: 16, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="date" tick={axisTick} stroke="var(--line2)" tickLine={false} />
              <YAxis
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                width={48}
                label={yLabel(t("dashboard.axis.lPerDp"))}
              />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} {...tooltipProps} />
              <Bar
                dataKey="L_per_dp_hour"
                name={t("dashboard.axis.lPerDp")}
                radius={[3, 3, 0, 0]}
                maxBarSize={40}
                isAnimationActive={anim}
              >
                {dpData.map((d, i) => (
                  <Cell
                    key={i}
                    fill={
                      d.rawDate === bestDate
                        ? C.lo
                        : d.rawDate === worstDate
                          ? C.hi
                          : C.primary
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ChartCard>

          <ChartCard
            title={t("dashboard.chart.fuelVsDp.title")}
            subtitle={fill(t("dashboard.chart.fuelVsDp.sub"), {
              base: num(model.base_L),
              rate: num(model.rate)
            })}
          >
            <ScatterChart margin={{ top: 6, right: 16, bottom: 8, left: 4 }}>
              <CartesianGrid stroke={GRID} />
              <XAxis
                type="number"
                dataKey="x"
                name={t("dashboard.axis.dpHours")}
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                label={xLabel(t("dashboard.axis.dpHours"))}
              />
              <YAxis
                type="number"
                dataKey="y"
                name={t("dashboard.axis.litres")}
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                width={54}
                domain={["dataMin - 500", "dataMax + 500"]}
                label={yLabel(t("dashboard.axis.litres"))}
              />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} {...tooltipProps} />
              <Legend wrapperStyle={legendStyle} />
              <ReferenceLine
                segment={modelSegment}
                stroke={C.mut}
                strokeDasharray="5 4"
                ifOverflow="extendDomain"
              />
              <Scatter
                name={t("dashboard.legend.overspent")}
                data={scatterOver}
                fill={C.hi}
                isAnimationActive={anim}
              />
              <Scatter
                name={t("dashboard.legend.saved")}
                data={scatterSaved}
                fill={C.lo}
                isAnimationActive={anim}
              />
            </ScatterChart>
          </ChartCard>
        </div>
      </section>

      {/* Section: Maintenance & fluids */}
      <section className="space-y-5">
        <SectionHeader>{t("dashboard.section.maintenance")}</SectionHeader>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <ChartCard
            title={t("dashboard.chart.lube.title")}
            subtitle={t("dashboard.chart.lube.sub")}
            height={260}
          >
            <BarChart
              layout="vertical"
              data={maint}
              margin={{ top: 6, right: 20, bottom: 4, left: 8 }}
            >
              <CartesianGrid stroke={GRID} horizontal={false} />
              <XAxis
                type="number"
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                label={xLabel(t("dashboard.axis.hoursRemaining"))}
              />
              <YAxis
                type="category"
                dataKey="machine"
                tick={axisTickSm}
                stroke="var(--line2)"
                tickLine={false}
                width={140}
              />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} {...tooltipProps} />
              <ReferenceLine x={0} stroke="var(--line2)" />
              <Bar
                dataKey="hours_remaining"
                name={t("dashboard.axis.hoursRemaining")}
                radius={[0, 3, 3, 0]}
                maxBarSize={26}
                isAnimationActive={anim}
              >
                {maint.map((m, i) => (
                  <Cell key={i} fill={maintColor(m)} />
                ))}
              </Bar>
            </BarChart>
          </ChartCard>

          <ChartCard
            title={t("dashboard.chart.fluids.title")}
            subtitle={t("dashboard.chart.fluids.sub")}
            height={260}
          >
            <BarChart data={fluids} margin={{ top: 6, right: 16, bottom: 48, left: 4 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis
                dataKey="name"
                tick={axisTickSm}
                stroke="var(--line2)"
                tickLine={false}
                interval={0}
                angle={-30}
                textAnchor="end"
                height={56}
              />
              <YAxis
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                width={44}
                label={yLabel(t("dashboard.axis.daysToEmpty"))}
              />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} {...tooltipProps} />
              <Bar
                dataKey="days_to_empty"
                name={t("dashboard.axis.daysToEmpty")}
                radius={[3, 3, 0, 0]}
                maxBarSize={40}
                isAnimationActive={anim}
              >
                {fluids.map((f, i) => (
                  <Cell key={i} fill={fluidColor(f.days_to_empty)} />
                ))}
              </Bar>
            </BarChart>
          </ChartCard>
        </div>
      </section>

      {/* Section: Engine & safety */}
      <section className="space-y-5">
        <SectionHeader>{t("dashboard.section.engineSafety")}</SectionHeader>
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <ChartCard
            title={t("dashboard.chart.engine.title")}
            subtitle={
              engineStatic && engine?.note
                ? engine.note
                : t("dashboard.chart.engine.sub")
            }
            badge={
              engineStatic ? (
                <span
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold"
                  style={{ color: "var(--med)", background: "var(--med-bg)" }}
                >
                  <AlertTriangle size={12} aria-hidden="true" />
                  {t("dashboard.badge.handEntered")}
                </span>
              ) : undefined
            }
          >
            <BarChart data={engineData} margin={{ top: 6, right: 16, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis
                dataKey="cyl"
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                label={xLabel(t("dashboard.axis.cylinder"))}
              />
              <YAxis
                tick={axisTick}
                stroke="var(--line2)"
                tickLine={false}
                width={44}
                domain={["dataMin - 10", "dataMax + 10"]}
                label={yLabel(t("dashboard.axis.tempC"))}
              />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} {...tooltipProps} />
              <Legend wrapperStyle={legendStyle} />
              <Bar
                dataKey="me1"
                name={t("dashboard.legend.me1")}
                fill={C.primary}
                radius={[3, 3, 0, 0]}
                maxBarSize={22}
                isAnimationActive={anim}
              />
              <Bar
                dataKey="me2"
                name={t("dashboard.legend.me2")}
                fill={C.accent}
                radius={[3, 3, 0, 0]}
                maxBarSize={22}
                isAnimationActive={anim}
              />
            </BarChart>
          </ChartCard>

          <div className="rounded-xl border border-line bg-surface p-5">
            <h4 className="text-[15px] font-semibold text-ink">
              {t("dashboard.chart.hse.title")}
            </h4>
            <p className="mt-0.5 text-[12.5px] text-mut">{t("dashboard.chart.hse.sub")}</p>
            {hseItems.length > 0 ? (
              <div className="mt-4 grid grid-cols-2 gap-3">
                {hseItems.map((it) => (
                  <div
                    key={it.key}
                    className="rounded-lg border border-line bg-surface2 p-3"
                    style={
                      it.highlight
                        ? { borderColor: "var(--med)", background: "var(--med-bg)" }
                        : undefined
                    }
                  >
                    <div
                      className="mono tnum text-[24px] font-semibold leading-none"
                      style={{ color: it.highlight ? "var(--med)" : "var(--ink)" }}
                    >
                      {num(it.value)}
                    </div>
                    <div className="mt-1.5 text-[12px] text-mut">{it.label}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-lg border border-dashed border-line2 bg-surface2/50 px-4 py-8 text-center text-[13px] text-mut">
                {t("dashboard.empty.body")}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

/* ---------- presentational bits ---------- */

const legendStyle: CSSProperties = { fontSize: 12, paddingTop: 6, color: "var(--mut)" };

function yLabel(value: string) {
  return {
    value,
    angle: -90,
    position: "insideLeft" as const,
    fill: "#8a959c",
    fontSize: 11,
    style: { textAnchor: "middle" as const }
  };
}

function xLabel(value: string) {
  return {
    value,
    position: "insideBottom" as const,
    offset: -2,
    fill: "#8a959c",
    fontSize: 11
  };
}

function SectionHeader({ children }: { children: ReactNode }) {
  return (
    <h3 className="px-1 text-[12px] font-semibold uppercase tracking-[0.08em] text-mut2">
      {children}
    </h3>
  );
}

function KpiCard({
  label,
  value,
  sub,
  valueColor,
  children
}: {
  label: string;
  value: string;
  sub?: string;
  valueColor?: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-[11.5px] font-medium uppercase tracking-wide text-mut">
        {label}
      </div>
      <div
        className="mono tnum mt-2 text-[26px] font-semibold leading-none"
        style={{ color: valueColor ?? "var(--ink)" }}
      >
        {value}
      </div>
      {sub && <div className="mt-1.5 text-[12px] text-mut">{sub}</div>}
      {children}
    </div>
  );
}

function SignalChip({
  value,
  color,
  letter
}: {
  value: number;
  color: string;
  letter: string;
}) {
  return (
    <span
      className="mono tnum inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold"
      style={{ color, background: `${color}1f` }}
    >
      {letter}
      {value}
    </span>
  );
}

function ChartCard({
  title,
  subtitle,
  badge,
  height = 240,
  children
}: {
  title: string;
  subtitle: string;
  badge?: ReactNode;
  height?: number;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-[15px] font-semibold text-ink">{title}</h4>
          <p className="mt-0.5 text-[12.5px] leading-snug text-mut">{subtitle}</p>
        </div>
        {badge}
      </div>
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          {children as never}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
