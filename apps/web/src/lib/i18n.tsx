"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from "react";

export type Locale = "en" | "fr";

export const LOCALE_KEY = "vaalco_locale";

type Messages = Record<string, string>;

const en: Messages = {
  // Brand / header
  "app.title": "Navigator Z — Vessel Intelligence",
  "app.subtitle": "Fuel · DP efficiency · maintenance · HSE",
  "header.logout": "Log out",
  "header.settings": "Alert settings",
  "settings.title": "Alert settings",
  "settings.description": "Choose who receives the email alerts.",
  "settings.emailLabel": "Alert recipient email",
  "settings.placeholder": "name@company.com",
  "settings.save": "Save",
  "settings.saving": "Saving…",
  "settings.saved": "Saved",
  "settings.cancel": "Cancel",
  "settings.invalid": "Please enter a valid email address.",
  "settings.loadError": "Couldn't load settings.",
  "settings.saveError": "Couldn't save. Please try again.",
  "status.reportsLoaded": "reports loaded",
  "status.disconnected": "disconnected",

  // Tabs
  "tab.ask": "Ask",
  "tab.signals": "Signals",

  // Login
  "login.title": "Fuel Intelligence",
  "login.subtitle": "Vessel operations console",
  "login.codeLabel": "Access code",
  "login.codePlaceholder": "Enter your access code",
  "login.submit": "Sign in",
  "login.loading": "Signing in…",
  "login.error": "Invalid access code",
  "login.errorNetwork": "Couldn't reach the server. Check your connection and try again.",
  "login.footer": "Secure access · VAALCO Energy",

  // Ask tab
  "ask.hint": "Ask about fuel consumption, DP efficiency, maintenance, or HSE across recent daily reports.",
  "ask.placeholder": "Ask a question about the vessel…",
  "ask.send": "Send",
  "ask.thinking": "Thinking",
  "ask.emptyThread": "Start a conversation or pick a suggestion below.",
  "ask.chip.fuel": "How's our fuel overall?",
  "ask.chip.fuelSpike": "Why was fuel high on the 22nd?",
  "ask.chip.dp": "How efficient is our DP?",
  "ask.chip.maintenance": "Anything overdue for maintenance?",

  // Signals tab
  "signals.high": "High priority",
  "signals.medium": "Medium",
  "signals.low": "Low",
  "signals.execSummary": "Executive summary",
  "signals.evidence": "Evidence",
  "signals.nextSteps": "Recommended next steps",
  "signals.askAbout": "Ask about this",
  "signals.rerun": "Re-run",
  "signals.rerunning": "Re-running…",
  "signals.previewEmail": "Preview email",
  "signals.sendNow": "Send now",
  "signals.sending": "Sending…",
  "signals.history": "Report history",
  "signals.empty": "All monitored metrics are within thresholds",
  "signals.loading": "Loading intelligence report…",
  "signals.asOf": "As of",
  "signals.generated": "Generated",

  // Toasts
  "toast.rerunDone": "Signals report re-run complete",
  "toast.sendDone": "Report sent",
  "toast.sendError": "Failed to send report",
  "toast.rerunError": "Failed to re-run report",
  "toast.previewError": "Unable to open preview",
  "toast.loadError": "Failed to load data",

  // Common
  "common.retry": "Retry",
  "common.error": "Something went wrong"
};

const fr: Messages = {
  // Brand / header
  "app.title": "Navigator Z — Renseignement Navire",
  "app.subtitle": "Carburant · efficacité DP · maintenance · HSE",
  "header.logout": "Déconnexion",
  "header.settings": "Paramètres d'alerte",
  "settings.title": "Paramètres d'alerte",
  "settings.description": "Choisissez qui reçoit les alertes par e-mail.",
  "settings.emailLabel": "E-mail du destinataire des alertes",
  "settings.placeholder": "nom@entreprise.com",
  "settings.save": "Enregistrer",
  "settings.saving": "Enregistrement…",
  "settings.saved": "Enregistré",
  "settings.cancel": "Annuler",
  "settings.invalid": "Veuillez saisir une adresse e-mail valide.",
  "settings.loadError": "Impossible de charger les paramètres.",
  "settings.saveError": "Échec de l'enregistrement. Veuillez réessayer.",
  "status.reportsLoaded": "rapports chargés",
  "status.disconnected": "déconnecté",

  // Tabs
  "tab.ask": "Demander",
  "tab.signals": "Signaux",

  // Login
  "login.title": "Renseignement Carburant",
  "login.subtitle": "Console d'exploitation du navire",
  "login.codeLabel": "Code d'accès",
  "login.codePlaceholder": "Saisissez votre code d'accès",
  "login.submit": "Se connecter",
  "login.loading": "Connexion…",
  "login.error": "Code d'accès invalide",
  "login.errorNetwork": "Serveur inaccessible. Vérifiez votre connexion et réessayez.",
  "login.footer": "Accès sécurisé · VAALCO Energy",

  // Ask tab
  "ask.hint": "Posez des questions sur la consommation de carburant, l'efficacité DP, la maintenance ou le HSE à partir des rapports journaliers récents.",
  "ask.placeholder": "Posez une question sur le navire…",
  "ask.send": "Envoyer",
  "ask.thinking": "Réflexion",
  "ask.emptyThread": "Démarrez une conversation ou choisissez une suggestion ci-dessous.",
  "ask.chip.fuel": "Comment se porte notre carburant globalement ?",
  "ask.chip.fuelSpike": "Pourquoi le carburant était-il élevé le 22 ?",
  "ask.chip.dp": "Quelle est l'efficacité de notre DP ?",
  "ask.chip.maintenance": "Y a-t-il des maintenances en retard ?",

  // Signals tab
  "signals.high": "Priorité haute",
  "signals.medium": "Moyenne",
  "signals.low": "Basse",
  "signals.execSummary": "Résumé exécutif",
  "signals.evidence": "Éléments probants",
  "signals.nextSteps": "Actions recommandées",
  "signals.askAbout": "En savoir plus",
  "signals.rerun": "Relancer",
  "signals.rerunning": "Relance…",
  "signals.previewEmail": "Aperçu e-mail",
  "signals.sendNow": "Envoyer maintenant",
  "signals.sending": "Envoi…",
  "signals.history": "Historique des rapports",
  "signals.empty": "Toutes les métriques surveillées sont dans les seuils",
  "signals.loading": "Chargement du rapport de renseignement…",
  "signals.asOf": "Au",
  "signals.generated": "Généré le",

  // Toasts
  "toast.rerunDone": "Relance du rapport de signaux terminée",
  "toast.sendDone": "Rapport envoyé",
  "toast.sendError": "Échec de l'envoi du rapport",
  "toast.rerunError": "Échec de la relance du rapport",
  "toast.previewError": "Impossible d'ouvrir l'aperçu",
  "toast.loadError": "Échec du chargement des données",

  // Common
  "common.retry": "Réessayer",
  "common.error": "Une erreur est survenue"
};

const dictionaries: Record<Locale, Messages> = { en, fr };

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(LOCALE_KEY);
      if (stored === "en" || stored === "fr") {
        setLocaleState(stored);
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(LOCALE_KEY, next);
    } catch {
      // ignore storage errors
    }
    if (typeof document !== "undefined") {
      document.documentElement.lang = next;
    }
  }, []);

  const t = useCallback(
    (key: string): string => {
      const dict = dictionaries[locale];
      return dict[key] ?? dictionaries.en[key] ?? key;
    },
    [locale]
  );

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}
