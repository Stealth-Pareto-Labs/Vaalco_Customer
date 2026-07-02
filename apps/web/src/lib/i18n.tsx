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
  "tab.dashboard": "Dashboard",
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

  // Dashboard
  "dashboard.loading": "Loading dashboard…",
  "dashboard.retry": "Retry",
  "dashboard.asOf": "As of",
  "dashboard.reports": "reports loaded",
  "dashboard.empty.title": "No reports loaded yet",
  "dashboard.empty.body": "Charts will appear once daily reports are ingested.",

  // Dashboard · sections
  "dashboard.section.fuelCost": "Fuel & cost",
  "dashboard.section.efficiency": "Efficiency & workload",
  "dashboard.section.maintenance": "Maintenance & fluids",
  "dashboard.section.engineSafety": "Engine & safety",

  // Dashboard · KPIs
  "dashboard.kpi.avgFuel": "Avg daily fuel",
  "dashboard.kpi.annualCost": "Annualised fuel cost",
  "dashboard.kpi.netVsModel": "Net vs model",
  "dashboard.kpi.openSignals": "Open signals",
  "dashboard.kpi.perDay": "/ day",
  "dashboard.kpi.overspent": "overspent",
  "dashboard.kpi.saved": "saved",

  // Dashboard · chart titles & subtitles
  "dashboard.chart.fuelActual.title": "Daily fuel — actual vs. model",
  "dashboard.chart.fuelActual.sub":
    "Actual daily fuel vs the DP-workload model; the gap is the deviation.",
  "dashboard.chart.fuelCost.title": "Fuel cost vs. model ($/day)",
  "dashboard.chart.fuelCost.sub": "Positive = overspent vs expected · negative = saved.",
  "dashboard.chart.dpEff.title": "DP fuel efficiency",
  "dashboard.chart.dpEff.sub": "Litres per DP-hour · {spread}% spread best↔worst.",
  "dashboard.chart.fuelVsDp.title": "Fuel vs. DP hours",
  "dashboard.chart.fuelVsDp.sub": "Model: {base} L base + {rate} L per DP-hour.",
  "dashboard.chart.lube.title": "Hours to next lube service",
  "dashboard.chart.lube.sub": "By machine · red = overdue/urgent.",
  "dashboard.chart.fluids.title": "Consumable fluids — days to empty",
  "dashboard.chart.fluids.sub": "At the recent consumption rate.",
  "dashboard.chart.engine.title": "Main engine cylinder exhaust temps (°C)",
  "dashboard.chart.engine.sub": "Per-cylinder exhaust temperature.",
  "dashboard.chart.hse.title": "HSE indicators",
  "dashboard.chart.hse.sub": "Period totals.",

  // Dashboard · axes & units
  "dashboard.axis.litres": "Litres",
  "dashboard.axis.costDay": "USD / day",
  "dashboard.axis.lPerDp": "L / DP-hour",
  "dashboard.axis.dpHours": "DP hours",
  "dashboard.axis.hoursRemaining": "Hours remaining",
  "dashboard.axis.daysToEmpty": "Days to empty",
  "dashboard.axis.tempC": "°C",
  "dashboard.axis.cylinder": "Cylinder",
  "dashboard.unit.L": "L",

  // Dashboard · legends & chips
  "dashboard.legend.actual": "Actual",
  "dashboard.legend.expected": "Expected (model)",
  "dashboard.legend.overspent": "Overspent",
  "dashboard.legend.saved": "Saved",
  "dashboard.legend.me1": "ME1",
  "dashboard.legend.me2": "ME2",
  "dashboard.chip.high": "H",
  "dashboard.chip.medium": "M",
  "dashboard.chip.low": "L",

  // Dashboard · badges & HSE labels
  "dashboard.badge.handEntered": "Hand-entered — not a live sensor feed",
  "dashboard.hse.nearMisses": "Near misses",
  "dashboard.hse.drills": "Drills",
  "dashboard.hse.toolbox": "Toolbox meetings",
  "dashboard.hse.riskAssessments": "Risk assessments",
  "dashboard.hse.ptw": "Permits to work",
  "dashboard.hse.workdaysLost": "Workdays lost",
  "dashboard.hse.propertyDamage": "Property damage",
  "dashboard.hse.medical": "Medical reports",

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
  "tab.dashboard": "Tableau de bord",
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

  // Dashboard
  "dashboard.loading": "Chargement du tableau de bord…",
  "dashboard.retry": "Réessayer",
  "dashboard.asOf": "Au",
  "dashboard.reports": "rapports chargés",
  "dashboard.empty.title": "Aucun rapport chargé pour le moment",
  "dashboard.empty.body":
    "Les graphiques s'afficheront dès l'intégration des rapports journaliers.",

  // Dashboard · sections
  "dashboard.section.fuelCost": "Carburant & coût",
  "dashboard.section.efficiency": "Efficacité & charge de travail",
  "dashboard.section.maintenance": "Maintenance & fluides",
  "dashboard.section.engineSafety": "Moteur & sécurité",

  // Dashboard · KPIs
  "dashboard.kpi.avgFuel": "Carburant journalier moyen",
  "dashboard.kpi.annualCost": "Coût carburant annualisé",
  "dashboard.kpi.netVsModel": "Écart net vs modèle",
  "dashboard.kpi.openSignals": "Signaux ouverts",
  "dashboard.kpi.perDay": "/ jour",
  "dashboard.kpi.overspent": "surconsommé",
  "dashboard.kpi.saved": "économisé",

  // Dashboard · chart titles & subtitles
  "dashboard.chart.fuelActual.title": "Carburant journalier — réel vs modèle",
  "dashboard.chart.fuelActual.sub":
    "Carburant réel journalier vs le modèle de charge DP ; l'écart correspond à la déviation.",
  "dashboard.chart.fuelCost.title": "Coût carburant vs modèle ($/jour)",
  "dashboard.chart.fuelCost.sub":
    "Positif = surconsommation vs prévu · négatif = économie.",
  "dashboard.chart.dpEff.title": "Efficacité carburant DP",
  "dashboard.chart.dpEff.sub": "Litres par heure DP · {spread}% d'écart meilleur↔pire.",
  "dashboard.chart.fuelVsDp.title": "Carburant vs heures DP",
  "dashboard.chart.fuelVsDp.sub": "Modèle : {base} L de base + {rate} L par heure DP.",
  "dashboard.chart.lube.title": "Heures avant prochaine vidange",
  "dashboard.chart.lube.sub": "Par machine · rouge = en retard/urgent.",
  "dashboard.chart.fluids.title": "Fluides consommables — jours avant épuisement",
  "dashboard.chart.fluids.sub": "Au rythme de consommation récent.",
  "dashboard.chart.engine.title": "Températures d'échappement cylindres moteur principal (°C)",
  "dashboard.chart.engine.sub": "Température d'échappement par cylindre.",
  "dashboard.chart.hse.title": "Indicateurs HSE",
  "dashboard.chart.hse.sub": "Totaux de la période.",

  // Dashboard · axes & units
  "dashboard.axis.litres": "Litres",
  "dashboard.axis.costDay": "USD / jour",
  "dashboard.axis.lPerDp": "L / heure DP",
  "dashboard.axis.dpHours": "Heures DP",
  "dashboard.axis.hoursRemaining": "Heures restantes",
  "dashboard.axis.daysToEmpty": "Jours avant épuisement",
  "dashboard.axis.tempC": "°C",
  "dashboard.axis.cylinder": "Cylindre",
  "dashboard.unit.L": "L",

  // Dashboard · legends & chips
  "dashboard.legend.actual": "Réel",
  "dashboard.legend.expected": "Prévu (modèle)",
  "dashboard.legend.overspent": "Surconsommation",
  "dashboard.legend.saved": "Économie",
  "dashboard.legend.me1": "MP1",
  "dashboard.legend.me2": "MP2",
  "dashboard.chip.high": "H",
  "dashboard.chip.medium": "M",
  "dashboard.chip.low": "B",

  // Dashboard · badges & HSE labels
  "dashboard.badge.handEntered": "Saisi à la main — pas un flux de capteur en direct",
  "dashboard.hse.nearMisses": "Presqu'accidents",
  "dashboard.hse.drills": "Exercices",
  "dashboard.hse.toolbox": "Réunions sécurité",
  "dashboard.hse.riskAssessments": "Évaluations des risques",
  "dashboard.hse.ptw": "Permis de travail",
  "dashboard.hse.workdaysLost": "Journées perdues",
  "dashboard.hse.propertyDamage": "Dommages matériels",
  "dashboard.hse.medical": "Rapports médicaux",

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
