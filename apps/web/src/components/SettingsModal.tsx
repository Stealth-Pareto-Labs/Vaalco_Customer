"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createPortal } from "react-dom";
import {
  X, Mail, Loader2, Check, AlertTriangle, Plus, Send, Clock, Globe, Bell
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useToast } from "@/components/Toast";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

const BASE_TZ = [
  "Africa/Libreville", "UTC", "Europe/London", "Europe/Paris", "Africa/Lagos",
  "America/New_York", "America/Chicago", "America/Los_Angeles", "Asia/Dubai", "Asia/Singapore"
];

function isValidEmail(e: string) {
  const t = e.trim();
  return t.length > 2 && t.includes("@") && t.split("@")[1]?.includes(".");
}

export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  const { t } = useI18n();
  const { toast } = useToast();

  const [emails, setEmails] = useState<string[]>([]);
  const [newEmail, setNewEmail] = useState("");
  const [criticalImmediate, setCriticalImmediate] = useState(true);
  const [digestEnabled, setDigestEnabled] = useState(true);
  const [digestTime, setDigestTime] = useState("08:00");
  const [timezone, setTimezone] = useState("Africa/Libreville");

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    setSaved(false);
    setError(null);
    setNewEmail("");
    setLoading(true);
    api
      .getSettings()
      .then((s) => {
        setEmails(s.emails ?? []);
        setCriticalImmediate(s.critical_immediate ?? true);
        setDigestEnabled(s.digest_enabled ?? true);
        setDigestTime(s.digest_time ?? "08:00");
        setTimezone(s.timezone ?? "Africa/Libreville");
      })
      .catch(() => setError(t("settings.loadError")))
      .finally(() => setLoading(false));
  }, [open, t]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !mounted) return null;

  const tzList = (() => {
    let detected = "";
    try {
      detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
      /* ignore */
    }
    const set = new Set([timezone, detected, ...BASE_TZ].filter(Boolean));
    return Array.from(set);
  })();

  const addEmail = () => {
    const e = newEmail.trim();
    if (!e) return;
    if (!isValidEmail(e)) {
      setError(t("settings.invalid"));
      return;
    }
    if (emails.includes(e)) {
      setError(t("settings.emailExists"));
      return;
    }
    setEmails((prev) => [...prev, e]);
    setNewEmail("");
    setError(null);
    setSaved(false);
  };

  const removeEmail = (e: string) => {
    setEmails((prev) => prev.filter((x) => x !== e));
    setSaved(false);
  };

  const buildConfig = () => ({
    emails,
    digest_enabled: digestEnabled,
    digest_time: digestTime,
    timezone,
    critical_immediate: criticalImmediate
  });

  const persist = async () => {
    const res = await api.saveSettings(buildConfig());
    setEmails(res.emails ?? []);
    return res;
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await persist();
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 400 ? t("settings.invalid") : t("settings.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const sendNow = async () => {
    if (sending) return;
    setError(null);
    if (emails.length === 0) {
      setError(t("settings.noRecipients"));
      return;
    }
    setSending(true);
    try {
      await persist(); // make sure the latest recipients are saved first
      await api.signalsSend(null);
      toast(t("settings.sentOk"));
      onClose();
    } catch {
      toast(t("settings.sendError"), "error");
    } finally {
      setSending(false);
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />

      <div className="glass hairline-top relative flex max-h-[88vh] w-full max-w-lg flex-col rounded-2xl shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between p-6 pb-4">
          <div>
            <h2 id="settings-title" className="text-[17px] font-semibold text-ink">
              {t("settings.title")}
            </h2>
            <p className="mt-0.5 text-[13px] text-mut">{t("settings.description")}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("settings.cancel")}
            className="focus-ring -mr-1 -mt-1 cursor-pointer rounded-lg p-1.5 text-mut transition-colors duration-150 hover:bg-surface2 hover:text-ink"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {/* Body (scrolls) */}
        <div className="scroll-thin flex-1 overflow-y-auto px-6">
          {/* Recipients */}
          <SectionLabel icon={<Mail size={13} />}>{t("settings.recipients")}</SectionLabel>
          <div className="mb-2 flex flex-wrap gap-2">
            {emails.map((e) => (
              <span
                key={e}
                className="flex items-center gap-1.5 rounded-full border border-line2 bg-surface2 py-1 pl-3 pr-1.5 text-[13px] text-ink"
              >
                {e}
                <button
                  type="button"
                  onClick={() => removeEmail(e)}
                  aria-label={`Remove ${e}`}
                  className="focus-ring cursor-pointer rounded-full p-0.5 text-mut hover:text-hi"
                >
                  <X size={13} aria-hidden="true" />
                </button>
              </span>
            ))}
            {emails.length === 0 && !loading && (
              <span className="text-[13px] text-mut2">{t("settings.noRecipients")}</span>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addEmail();
                }
              }}
              placeholder={t("settings.placeholder")}
              disabled={loading}
              className="focus-ring min-w-0 flex-1 rounded-lg border border-line bg-black/25 px-3 py-2 text-[14px] text-ink placeholder:text-mut2 focus:border-primary disabled:opacity-50"
            />
            <button
              type="button"
              onClick={addEmail}
              className="focus-ring flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-line2 bg-surface2 px-3 py-2 text-[14px] font-medium text-ink transition-colors duration-150 hover:border-primary"
            >
              <Plus size={15} aria-hidden="true" />
              {t("settings.addEmail")}
            </button>
          </div>

          {/* Delivery rules */}
          <SectionLabel icon={<Bell size={13} />} className="mt-6">
            {t("settings.delivery")}
          </SectionLabel>

          <ToggleRow
            checked={criticalImmediate}
            onChange={setCriticalImmediate}
            label={t("settings.criticalImmediate")}
            hint={t("settings.criticalHint")}
          />

          <ToggleRow
            checked={digestEnabled}
            onChange={setDigestEnabled}
            label={t("settings.digestEnabled")}
            hint={t("settings.digestHint")}
          />

          {digestEnabled && (
            <div className="mb-1 mt-3 grid grid-cols-1 gap-3 rounded-xl border border-line bg-black/15 p-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1.5">
                <span className="flex items-center gap-1.5 text-[12.5px] font-medium text-mut">
                  <Clock size={13} aria-hidden="true" /> {t("settings.digestTime")}
                </span>
                <input
                  type="time"
                  value={digestTime}
                  onChange={(e) => setDigestTime(e.target.value)}
                  className="focus-ring rounded-lg border border-line bg-black/25 px-3 py-2 text-[14px] text-ink focus:border-primary"
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="flex items-center gap-1.5 text-[12.5px] font-medium text-mut">
                  <Globe size={13} aria-hidden="true" /> {t("settings.timezone")}
                </span>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="focus-ring rounded-lg border border-line bg-black/25 px-3 py-2 text-[14px] text-ink focus:border-primary"
                >
                  {tzList.map((tz) => (
                    <option key={tz} value={tz} className="bg-surface2">
                      {tz}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {error && (
            <p role="alert" className="mt-3 flex items-center gap-2 text-[13px]" style={{ color: "var(--hi)" }}>
              <AlertTriangle size={14} aria-hidden="true" />
              {error}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 p-6 pt-4">
          <button
            type="button"
            onClick={sendNow}
            disabled={sending}
            className="focus-ring flex cursor-pointer items-center gap-2 rounded-lg border border-line2 bg-surface2 px-3.5 py-2 text-[14px] font-medium text-ink transition-colors duration-150 hover:border-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sending ? <Loader2 size={15} className="spin" aria-hidden="true" /> : <Send size={15} aria-hidden="true" />}
            {sending ? t("settings.sending") : t("settings.sendNow")}
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="focus-ring cursor-pointer rounded-lg border border-line px-4 py-2 text-[14px] font-medium text-mut transition-colors duration-150 hover:border-line2 hover:text-ink"
            >
              {t("settings.cancel")}
            </button>
            <button
              type="button"
              onClick={onSubmit}
              disabled={saving || loading}
              className="glow-primary focus-ring flex cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 py-2 text-[14px] font-semibold text-white transition-all duration-150 hover:bg-primary-strong disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? <Loader2 size={15} className="spin" aria-hidden="true" /> : saved ? <Check size={15} aria-hidden="true" /> : null}
              {saved ? t("settings.saved") : saving ? t("settings.saving") : t("settings.save")}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

function SectionLabel({
  children,
  icon,
  className = ""
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-mut ${className}`}>
      <span className="text-mut2" aria-hidden="true">{icon}</span>
      {children}
    </div>
  );
}

function ToggleRow({
  checked,
  onChange,
  label,
  hint
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="focus-ring flex w-full items-start justify-between gap-3 rounded-xl border border-line bg-black/15 px-3.5 py-3 text-left transition-colors duration-150 hover:border-line2"
    >
      <span className="min-w-0">
        <span className="block text-[14px] font-medium text-ink">{label}</span>
        <span className="mt-0.5 block text-[12.5px] leading-snug text-mut">{hint}</span>
      </span>
      <span
        className="mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors duration-150"
        style={{ background: checked ? "var(--primary)" : "var(--line2)" }}
      >
        <span
          className="h-4 w-4 rounded-full bg-white transition-transform duration-150"
          style={{ transform: checked ? "translateX(16px)" : "translateX(0)" }}
        />
      </span>
    </button>
  );
}
