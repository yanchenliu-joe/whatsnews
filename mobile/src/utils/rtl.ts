import { I18nManager } from "react-native";

/** Drill-in chevron pointing in the reading direction (Phase 38, added
 * 2026-07-06) — RN mirrors flexDirection automatically once
 * I18nManager.isRTL is true, but text glyphs used as icons don't flip on
 * their own. "›" points forward (LTR); use the flipped glyph in RTL. */
export function forwardChevron(): string {
  return I18nManager.isRTL ? "‹" : "›";
}

/** Back-navigation chevron, opposite of forwardChevron(). */
export function backChevron(): string {
  return I18nManager.isRTL ? "›" : "‹";
}

/** Back-navigation arrow ("←"/"→" style, distinct glyph from the chevron
 * variants above — used where the existing design already used an arrow
 * rather than a chevron, e.g. AIAssistantScreen's header back button). */
export function backArrow(): string {
  return I18nManager.isRTL ? "→" : "←";
}

/** Current RTL layout state — read fresh each call rather than imported as
 * a snapshot, since it can change at runtime via LanguageSync. */
export function isRTL(): boolean {
  return I18nManager.isRTL;
}
