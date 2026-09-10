import AsyncStorage from "@react-native-async-storage/async-storage";
import type { onTranslateTask as OnTranslateTaskFn } from "expo-translate-text";
import { Converter as openCcConverter } from "opencc-js";

import { IS_EXPO_GO } from "./expoGo";
import type { SupportedLanguage } from "../i18n";

// `expo-translate-text`'s own module-level code calls expo-modules-core's
// requireNativeModule('ExpoTranslateText') at *import* time (confirmed by
// reading node_modules/expo-translate-text/build/ExpoTranslateTextModule.js
// directly), which throws immediately in Expo Go regardless of any runtime
// guard — a static top-level `import { onTranslateTask } from
// "expo-translate-text"` would therefore crash the app on load. Only
// require() this package lazily after the IS_EXPO_GO check below passes.
function loadOnTranslateTask(): typeof OnTranslateTaskFn | null {
  if (IS_EXPO_GO) return null;
  return (require("expo-translate-text") as { onTranslateTask: typeof OnTranslateTaskFn })
    .onTranslateTask;
}

// expo-translate-text (2026-07-13) — Apple's on-device Translation
// framework on iOS (requires iOS 18+ for the silent, no-UI translateTask
// used here; older iOS just falls through to the catch below and shows
// the English original), Google ML Kit on Android. Free, on-device, no
// OPENAI_API_KEY involved — chosen specifically to keep the free-version
// pivot's zero-AI-cost guarantee while still translating content.
//
// Neither platform's translation API distinguishes Simplified vs.
// Traditional Chinese (both take a plain "zh" language code) — for
// "zh-Hant" we always request "zh" then run the result through opencc-js
// (pure JS, no native dependency) to convert to Traditional. This is safe
// even if a given OS build happens to already return Traditional text,
// since opencc-js only rewrites characters it recognizes as Simplified.
const LANGUAGE_TO_CODE: Partial<Record<SupportedLanguage, string>> = {
  "zh-Hans": "zh",
  "zh-Hant": "zh",
  es: "es",
  pt: "pt",
  ja: "ja",
  hi: "hi",
  ar: "ar",
  fr: "fr",
  bn: "bn",
  ru: "ru",
  ur: "ur",
};

const simplifiedToTraditional = openCcConverter({ from: "cn", to: "tw" });

// BCP-47 locale for expo-speech (Speech.speak's `language` option) — a
// plain 2-letter code often resolves fine, but a full region tag is more
// reliable across both the iOS and Android TTS engines.
const LANGUAGE_TO_SPEECH_LOCALE: Partial<Record<SupportedLanguage, string>> = {
  "zh-Hans": "zh-CN",
  "zh-Hant": "zh-TW",
  es: "es-ES",
  pt: "pt-BR",
  ja: "ja-JP",
  hi: "hi-IN",
  ar: "ar-SA",
  fr: "fr-FR",
  bn: "bn-BD",
  ru: "ru-RU",
  ur: "ur-PK",
};

/** BCP-47 locale for on-device TTS, or `undefined` to use the default English voice. */
export function speechLocaleFor(targetLanguage: SupportedLanguage): string | undefined {
  return LANGUAGE_TO_SPEECH_LOCALE[targetLanguage];
}

const CACHE_KEY_PREFIX = "@whatsnews_translation_cache:";

/** Small, dependency-free string hash — only used to keep cache keys short. */
function hashText(value: string): string {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return hash.toString(36);
}

async function readCache(key: string): Promise<Record<string, string> | null> {
  try {
    const raw = await AsyncStorage.getItem(CACHE_KEY_PREFIX + key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

async function writeCache(key: string, value: Record<string, string>): Promise<void> {
  try {
    await AsyncStorage.setItem(CACHE_KEY_PREFIX + key, JSON.stringify(value));
  } catch {
    // best-effort cache, safe to drop
  }
}

/**
 * Translates a set of named English strings (e.g. { summary, wim }) into
 * the given UI language, all in one native call. Returns `null` if
 * translation isn't available at all (Expo Go, unsupported OS version,
 * empty input, native call failure) — callers should fall back to showing
 * the original English rather than an error state, matching this app's
 * standing "degrade gracefully" pattern for native-module gaps.
 */
export async function translateFieldsFromEnglish(
  fields: Record<string, string>,
  targetLanguage: SupportedLanguage,
): Promise<Record<string, string> | null> {
  const code = LANGUAGE_TO_CODE[targetLanguage];
  if (!code || IS_EXPO_GO) return null;

  const entries = Object.entries(fields).filter(([, v]) => Boolean(v && v.trim()));
  if (entries.length === 0) return null;

  const cacheKey = `${targetLanguage}:${hashText(entries.map(([k, v]) => `${k}=${v}`).join("|"))}`;
  const cached = await readCache(cacheKey);
  if (cached) return cached;

  try {
    const onTranslateTask = loadOnTranslateTask();
    if (!onTranslateTask) return null;

    const input = Object.fromEntries(entries);
    const result = await onTranslateTask({
      input,
      sourceLangCode: "en",
      targetLangCode: code,
    });

    const translatedMap = result.translatedTexts as Record<string, string>;
    const finalMap: Record<string, string> = {};
    for (const [key, original] of entries) {
      const translated = translatedMap[key];
      finalMap[key] =
        typeof translated === "string" && translated.trim()
          ? targetLanguage === "zh-Hant"
            ? simplifiedToTraditional(translated)
            : translated
          : original;
    }

    void writeCache(cacheKey, finalMap);
    return finalMap;
  } catch {
    // Unsupported OS version (iOS < 18), model unavailable, or any other
    // native-side failure — no error UI, just skip translation entirely.
    return null;
  }
}
