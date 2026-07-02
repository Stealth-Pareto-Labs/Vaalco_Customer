"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createPortal } from "react-dom";
import { X, Mail, Loader2, Check, AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

export default function SettingsModal({ open, onClose }: SettingsModalProps) {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    setSaved(false);
    setError(null);
    setLoading(true);
    api
      .getSettings()
      .then((s) => setEmail(s.alert_email ?? ""))
      .catch(() => setError(t("settings.loadError")))
      .finally(() => setLoading(false));
  }, [open, t]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !mounted) return null;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const res = await api.setAlertEmail(email.trim());
      setEmail(res.alert_email ?? "");
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 400 ? t("settings.invalid") : t("settings.saveError"));
    } finally {
      setSaving(false);
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="glass hairline-top relative w-full max-w-md rounded-2xl p-6 shadow-2xl">
        <div className="mb-4 flex items-start justify-between">
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

        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <label htmlFor="alert-email" className="text-[13px] font-medium text-mut">
            {t("settings.emailLabel")}
          </label>
          <div className="relative">
            <Mail
              size={16}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mut2"
              aria-hidden="true"
            />
            <input
              id="alert-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("settings.placeholder")}
              disabled={loading}
              autoComplete="email"
              className="focus-ring w-full rounded-lg border border-line bg-black/25 py-2.5 pl-9 pr-3 text-[15px] text-ink placeholder:text-mut2 focus:border-primary disabled:opacity-50"
            />
          </div>

          {error && (
            <p role="alert" className="flex items-center gap-2 text-[13px]" style={{ color: "var(--hi)" }}>
              <AlertTriangle size={14} aria-hidden="true" />
              {error}
            </p>
          )}

          <div className="mt-1 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="focus-ring cursor-pointer rounded-lg border border-line px-4 py-2 text-[14px] font-medium text-mut transition-colors duration-150 hover:border-line2 hover:text-ink"
            >
              {t("settings.cancel")}
            </button>
            <button
              type="submit"
              disabled={saving || loading}
              className="focus-ring glow-primary flex cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 py-2 text-[14px] font-semibold text-white transition-all duration-150 hover:bg-primary-strong disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? (
                <Loader2 size={15} className="spin" aria-hidden="true" />
              ) : saved ? (
                <Check size={15} aria-hidden="true" />
              ) : null}
              {saved ? t("settings.saved") : saving ? t("settings.saving") : t("settings.save")}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
