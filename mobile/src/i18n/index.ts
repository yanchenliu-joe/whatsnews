import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import * as Localization from "expo-localization";

import en from "./locales/en.json";
import zhHans from "./locales/zh-Hans.json";
import zhHant from "./locales/zh-Hant.json";
import es from "./locales/es.json";
import pt from "./locales/pt.json";
import ja from "./locales/ja.json";
import hi from "./locales/hi.json";
import ar from "./locales/ar.json";
import fr from "./locales/fr.json";
import bn from "./locales/bn.json";
import ru from "./locales/ru.json";
import ur from "./locales/ur.json";

export const SUPPORTED_LANGUAGES = [
  "en",
  "zh-Hans",
  "zh-Hant",
  "es",
  "pt",
  "ja",
  "hi",
  "ar",
  "fr",
  "bn",
  "ru",
  "ur",
] as const;

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const RTL_LANGUAGES: readonly SupportedLanguage[] = ["ar", "ur"];

export function isRtlLanguage(lang: string): boolean {
  return (RTL_LANGUAGES as readonly string[]).includes(lang);
}

const LANGUAGE_NAMES: Record<SupportedLanguage, string> = {
  en: "English",
  "zh-Hans": "简体中文",
  "zh-Hant": "繁體中文",
  es: "Español",
  pt: "Português",
  ja: "日本語",
  hi: "हिन्दी",
  ar: "العربية",
  fr: "Français",
  bn: "বাংলা",
  ru: "Русский",
  ur: "اردو",
};

export function languageDisplayName(lang: SupportedLanguage): string {
  return LANGUAGE_NAMES[lang];
}

function isSupportedLanguage(value: string): value is SupportedLanguage {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(value);
}

/** Best-effort device locale -> one of our supported codes, else "en". */
export function detectDeviceLanguage(): SupportedLanguage {
  const locales = Localization.getLocales();
  for (const locale of locales) {
    const tag = locale.languageTag; // e.g. "zh-Hans-CN", "en-US", "ar-SA"
    if (isSupportedLanguage(tag)) return tag;

    const languageCode = locale.languageCode; // e.g. "zh", "en", "ar"
    if (languageCode === "zh") {
      // Simplified for mainland/Singapore, Traditional otherwise (HK/TW/MO).
      const region = locale.regionCode ?? "";
      return region === "TW" || region === "HK" || region === "MO" ? "zh-Hant" : "zh-Hans";
    }
    if (languageCode && isSupportedLanguage(languageCode)) return languageCode;
  }
  return "en";
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    "zh-Hans": { translation: zhHans },
    "zh-Hant": { translation: zhHant },
    es: { translation: es },
    pt: { translation: pt },
    ja: { translation: ja },
    hi: { translation: hi },
    ar: { translation: ar },
    fr: { translation: fr },
    bn: { translation: bn },
    ru: { translation: ru },
    ur: { translation: ur },
  },
  lng: detectDeviceLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
