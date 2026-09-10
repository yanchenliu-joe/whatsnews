import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { translateFieldsFromEnglish } from "../utils/onDeviceTranslation";
import type { SupportedLanguage } from "../i18n";

type Result<TFields extends Record<string, string>> = {
  /** Translated fields when available, otherwise the original English fields. */
  fields: TFields;
  /** True once a translation has actually been produced for the current fields+language. */
  isTranslated: boolean;
  isTranslating: boolean;
  /** When true, `fields` shows the original English (user tapped "View original"). */
  showingOriginal: boolean;
  toggleShowOriginal: () => void;
};

/**
 * Auto-translates a set of English fields (e.g. { summary, wim }) into the
 * current UI language on-device (2026-07-13, see onDeviceTranslation.ts).
 * No-ops entirely when the UI language is English — this app's content
 * (articles, narrative) is always authored in English server-side.
 */
export function useOnDeviceTranslation<TFields extends Record<string, string>>(
  originalFields: TFields,
): Result<TFields> {
  const { i18n } = useTranslation();
  const language = i18n.language as SupportedLanguage;

  const [translatedFields, setTranslatedFields] = useState<TFields | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [showingOriginal, setShowingOriginal] = useState(false);
  const requestIdRef = useRef(0);

  // Stable dependency key so effect only re-runs when the actual field
  // values or target language change, not on every render.
  const fieldsKey = Object.entries(originalFields)
    .map(([k, v]) => `${k}=${v}`)
    .join("|");

  useEffect(() => {
    setShowingOriginal(false);
    setTranslatedFields(null);

    if (language === "en" || !fieldsKey) {
      return;
    }

    const requestId = ++requestIdRef.current;
    setIsTranslating(true);
    translateFieldsFromEnglish(originalFields, language)
      .then((result) => {
        if (requestIdRef.current !== requestId) return;
        setTranslatedFields(result as TFields | null);
      })
      .finally(() => {
        if (requestIdRef.current === requestId) setIsTranslating(false);
      });
    // fieldsKey captures the meaningful identity of originalFields.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldsKey, language]);

  const isTranslated = Boolean(translatedFields);
  const fields = showingOriginal || !translatedFields ? originalFields : translatedFields;

  return {
    fields,
    isTranslated,
    isTranslating,
    showingOriginal,
    toggleShowOriginal: () => setShowingOriginal((v) => !v),
  };
}
