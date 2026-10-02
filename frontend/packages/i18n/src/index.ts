// Traductions (i18next) partagées par la Gestion et le Portail : français par défaut, anglais.
import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import { en } from "./locales/en";
import { fr } from "./locales/fr";

export { applyServerErrors, errorMessage, fieldMessage, firstErrorMessage } from "./errors";
export {
  formatDate,
  formatDateTime,
  formatDay,
  formatMonth,
  formatPhone,
  formatTime,
  formatVisit,
} from "./format";
// Les applications passent par ce paquet (une seule instance d'i18next).
export { Trans, useTranslation } from "react-i18next";
export type { TFunction } from "i18next";
export { en, fr };

export type Language = "fr" | "en";
export const LANGUAGES: Language[] = ["fr", "en"];

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "translation";
    resources: { translation: typeof fr };
  }
}

// Langue choisie sur cet appareil avant la connexion ; ensuite, celle du compte.
const STORAGE_KEY = "mwangaza.language";
// Le serveur répond dans la langue de l'interface (messages, PDF, Excel), pas dans celle du
// navigateur : Django lit ce cookie avant `Accept-Language` (`LANGUAGE_COOKIE_NAME`).
const SERVER_COOKIE = "django_language";

function storedLanguage(): Language | null {
  try {
    const value = globalThis.localStorage?.getItem(STORAGE_KEY);
    return value === "fr" || value === "en" ? value : null;
  } catch {
    return null;
  }
}

/** Démarre i18next ; à appeler une fois, avant d'afficher l'application. */
export function setupI18n(language?: Language) {
  const lng = language ?? storedLanguage() ?? "fr";
  void i18next.use(initReactI18next).init({
    lng,
    fallbackLng: "fr",
    supportedLngs: LANGUAGES,
    resources: { fr: { translation: fr }, en: { translation: en } },
    interpolation: { escapeValue: false },
  });
  applyLanguage(lng);
  return i18next;
}

/** Change la langue de l'interface et la garde sur cet appareil. */
export function changeLanguage(language: Language) {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, language);
  } catch {
    // Stockage refusé (navigation privée) : la langue vaut pour cette visite seulement.
  }
  applyLanguage(language);
  return i18next.changeLanguage(language);
}

function applyLanguage(language: string) {
  if (typeof document === "undefined") return;
  document.documentElement.lang = language;
  document.cookie = `${SERVER_COOKIE}=${language}; path=/; max-age=31536000; samesite=lax`;
}
