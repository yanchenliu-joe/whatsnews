import i18n from "../i18n";

/**
 * Editorial serif headline typeface (Newsreader, Google Fonts, added
 * 2026-07-11 design pass) — used for article titles, mastheads, and
 * other headline text to give the app an editorial/magazine voice
 * instead of relying on the system font everywhere.
 *
 * Newsreader only ships Latin-script glyphs. Languages using a script it
 * doesn't cover (Chinese, Japanese, Hindi, Arabic, Bengali, Urdu) fall
 * back to the system font's bold weight instead — not a visual bug, just
 * a real limitation of the free-font option: there's no single free
 * typeface spanning all 12 of this app's UI languages with a matching
 * editorial character. See docs/ENGINEERING.md's Mobile section.
 */
const SERIF_SUPPORTED_LANGUAGES = new Set(["en", "es", "pt", "fr", "ru"]);

export const NEWSREADER_FONT_FAMILY = {
  regular: "Newsreader_400Regular",
  medium: "Newsreader_500Medium",
  semibold: "Newsreader_600SemiBold",
  bold: "Newsreader_700Bold",
} as const;

export type HeadlineWeight = keyof typeof NEWSREADER_FONT_FAMILY;

/**
 * Returns the Newsreader font family name for the current UI language, or
 * `undefined` when the active language's script isn't covered — callers
 * should always pair this with an explicit `fontWeight` in the same style
 * object so the system-font fallback still renders at the right weight.
 *
 * Only use this for text whose *content* changes with the UI language
 * (article titles, translated labels). For fixed Latin text that never
 * translates — the "WhatsNews" wordmark — reference
 * NEWSREADER_FONT_FAMILY directly instead; it isn't affected by the
 * script-coverage limitation this function guards against.
 */
export function getHeadlineFontFamily(weight: HeadlineWeight = "semibold"): string | undefined {
  if (!SERIF_SUPPORTED_LANGUAGES.has(i18n.language)) {
    return undefined;
  }
  return NEWSREADER_FONT_FAMILY[weight];
}
