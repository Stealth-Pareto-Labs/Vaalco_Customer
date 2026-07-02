"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { RefreshCw, Mail, Send, AlertTriangle, Loader2 } from "lucide-react";
import { api, ApiError, previewUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useToast } from "@/components/Toast";
import StatTile from "@/components/StatTile";
import SignalCard from "@/components/SignalCard";
import type { HistoryEntry, Run } from "@/lib/types";

interface SignalsProps {
  active: boolean;
  onProbe: (probe: string) => void;
  onHighCount: (n: number) => void;
}

export default function Signals({ active, onProbe, onHighCount }: SignalsProps) {
  const { t, locale } = useI18n();
  const { toast } = useToast();

  const [run, setRun] = useState<Run | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);
  const [sending, setSending] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const loadedOnce = useRef(false);

  const setRunAndCount = useCallback(
    (r: Run | null) => {
      setRun(r);
      onHighCount(r?.counts.high ?? 0);
    },
    [onHighCount]
  );

  const loadHistory = useCallback(async () => {
    try {
      const h = await api.signalsHistory();
      setHistory(Array.isArray(h) ? h : []);
    } catch {
      // history is non-critical; keep silent
    }
  }, []);

  const loadLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.signalsLatest(locale);
      setRunAndCount(r);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("common.error");
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [setRunAndCount, t, locale]);

  useEffect(() => {
    if (active && !loadedOnce.current) {
      loadedOnce.current = true;
      void loadLatest();
      void loadHistory();
    }
  }, [active, loadLatest, loadHistory]);

  // Re-generate the report in the new language when the user switches locale.
  useEffect(() => {
    if (active && loadedOnce.current) void loadLatest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale]);

  const handleRerun = useCallback(async () => {
    setRerunning(true);
    try {
      const res = await api.signalsRun("manual: re-run", false, locale);
      setRunAndCount(res.run);
      await loadHistory();
      toast(t("toast.rerunDone"), "success");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("toast.rerunError");
      toast(msg, "error");
    } finally {
      setRerunning(false);
    }
  }, [loadHistory, setRunAndCount, t, toast, locale]);

  const handlePreview = useCallback(async () => {
    let id = run?.run_id ?? null;
    if (!id) {
      setPreviewing(true);
      try {
        const res = await api.signalsRun("manual: preview", false, locale);
        setRunAndCount(res.run);
        await loadHistory();
        id = res.run_id;
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : t("toast.previewError");
        toast(msg, "error");
        setPreviewing(false);
        return;
      }
      setPreviewing(false);
    }
    if (id) {
      window.open(previewUrl(id), "_blank", "noopener,noreferrer");
    } else {
      toast(t("toast.previewError"), "error");
    }
  }, [run, loadHistory, setRunAndCount, t, toast, locale]);

  const handleSend = useCallback(async () => {
    setSending(true);
    try {
      const res = await api.signalsSend(run?.run_id ?? null);
      let extra = "";
      const delivery = res.delivery as { status?: unknown } | null;
      if (delivery && typeof delivery.status === "string") {
        extra = ` · ${delivery.status}`;
      }
      toast(`${t("toast.sendDone")}${extra}`, "success");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : t("toast.sendError");
      toast(msg, "error");
    } finally {
      setSending(false);
    }
  }, [run, t, toast]);

  const loadRunById = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      try {
        const r = await api.signalsRunById(id);
        setRunAndCount(r);
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : t("common.error");
        toast(msg, "error");
      } finally {
        setLoading(false);
      }
    },
    [setRunAndCount, t, toast]
  );

  const dateFmt = useCallback(
    (iso: string): string => {
      if (!iso) return "";
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      return d.toLocaleString(locale === "fr" ? "fr-FR" : "en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      });
    },
    [locale]
  );

  const busy = rerunning || sending || previewing;

  return (
    <div className="py-4">
      {/* Action bar */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <ActionButton
          onClick={handleRerun}
          disabled={busy}
          loading={rerunning}
          icon={<RefreshCw size={15} className={rerunning ? "spin" : ""} />}
          label={rerunning ? t("signals.rerunning") : t("signals.rerun")}
          primary
        />
        <ActionButton
          onClick={handlePreview}
          disabled={busy}
          loading={previewing}
          icon={<Mail size={15} />}
          label={t("signals.previewEmail")}
        />
        <ActionButton
          onClick={handleSend}
          disabled={busy || !run}
          loading={sending}
          icon={<Send size={15} />}
          label={sending ? t("signals.sending") : t("signals.sendNow")}
        />
      </div>

      {loading && !run ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-line bg-surface px-4 py-14 text-center text-[14px] text-mut">
          <Loader2 size={26} className="spin text-primary" aria-hidden="true" />
          {t("signals.loading")}
        </div>
      ) : error && !run ? (
        <div
          className="flex items-center justify-between gap-3 rounded-xl border px-4 py-4"
          style={{ borderColor: "var(--hi)", background: "var(--hi-bg)" }}
        >
          <span className="flex items-center gap-2 text-[15px] text-ink">
            <AlertTriangle size={18} style={{ color: "var(--hi)" }} />
            {error}
          </span>
          <button
            type="button"
            onClick={() => void loadLatest()}
            className="focus-ring cursor-pointer rounded-lg border border-line2 bg-surface2 px-3 py-1.5 text-[14px] font-medium text-ink transition-colors duration-150 hover:border-primary"
          >
            {t("common.retry")}
          </button>
        </div>
      ) : run ? (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-3 gap-3">
            <StatTile label={t("signals.high")} value={run.counts.high} severity="high" />
            <StatTile
              label={t("signals.medium")}
              value={run.counts.medium}
              severity="medium"
            />
            <StatTile label={t("signals.low")} value={run.counts.low} severity="low" />
          </div>

          {/* Meta */}
          <div className="mono mt-3 flex flex-wrap gap-x-4 gap-y-1 px-1 text-[12px] text-mut2">
            <span>{run.vessel}</span>
            <span>{run.field}</span>
            <span>
              {t("signals.asOf")} {run.as_of}
            </span>
            <span>{run.date_range}</span>
          </div>

          {/* Executive summary */}
          {run.executive_summary && (
            <div
              className="mt-4 rounded-xl border border-line bg-surface p-4"
              style={{ borderLeft: "3px solid var(--accent)" }}
            >
              <h2 className="mb-1.5 text-[12px] font-semibold uppercase tracking-wide text-accent">
                {t("signals.execSummary")}
              </h2>
              <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink">
                {run.executive_summary}
              </p>
            </div>
          )}

          {/* Signals */}
          {run.signals && run.signals.length > 0 ? (
            <div className="mt-4 flex flex-col gap-3">
              {run.signals.map((sig) => (
                <SignalCard key={sig.id} signal={sig} onProbe={onProbe} />
              ))}
            </div>
          ) : (
            <div className="mt-4 rounded-xl border border-dashed border-line2 bg-surface/50 px-4 py-10 text-center text-[15px] text-mut">
              {t("signals.empty")}
            </div>
          )}

          {/* History */}
          {history.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-mut">
                {t("signals.history")}
              </h2>
              <ul className="flex flex-col gap-2">
                {history.map((h) => (
                  <li key={h.run_id}>
                    <button
                      type="button"
                      onClick={() => void loadRunById(h.run_id)}
                      className={`focus-ring flex w-full cursor-pointer items-center gap-3 rounded-lg border bg-surface px-3.5 py-3 text-left transition-colors duration-150 hover:border-line2 ${
                        run.run_id === h.run_id
                          ? "border-primary"
                          : "border-line"
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="mono truncate text-[12px] text-mut2">
                          {dateFmt(h.generated_at)}
                          {h.as_of ? ` · ${t("signals.asOf")} ${h.as_of}` : ""}
                        </div>
                        <div className="mt-0.5 truncate text-[14px] text-ink">
                          {h.headline}
                        </div>
                        <div className="truncate text-[12px] text-mut">
                          {h.trigger}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <CountChip value={h.counts.high} severity="high" />
                        <CountChip value={h.counts.medium} severity="medium" />
                        <CountChip value={h.counts.low} severity="low" />
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        <div className="rounded-xl border border-dashed border-line2 bg-surface/50 px-4 py-10 text-center text-[15px] text-mut">
          {t("signals.empty")}
        </div>
      )}
    </div>
  );
}

function ActionButton({
  onClick,
  disabled,
  loading,
  icon,
  label,
  primary
}: {
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
  icon: ReactNode;
  label: string;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-busy={loading}
      className={`focus-ring flex cursor-pointer items-center gap-2 rounded-lg px-3.5 py-2 text-[14px] font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${
        primary
          ? "bg-primary text-white hover:bg-primary-strong"
          : "border border-line bg-surface2 text-ink hover:border-line2"
      }`}
    >
      <span aria-hidden="true">{icon}</span>
      {label}
    </button>
  );
}

function CountChip({
  value,
  severity
}: {
  value: number;
  severity: "high" | "medium" | "low";
}) {
  const map = {
    high: { color: "var(--hi)", bg: "var(--hi-bg)" },
    medium: { color: "var(--med)", bg: "var(--med-bg)" },
    low: { color: "var(--lo)", bg: "var(--lo-bg)" }
  } as const;
  const s = map[severity];
  return (
    <span
      className="mono tnum inline-flex h-6 min-w-6 items-center justify-center rounded-md px-1.5 text-[12px] font-semibold"
      style={{ color: s.color, background: s.bg }}
    >
      {value}
    </span>
  );
}
