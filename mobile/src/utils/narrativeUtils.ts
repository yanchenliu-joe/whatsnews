import type { Narrative } from "../types";

export type VoiceCardState = "loading" | "ready" | "unavailable" | "error" | "hidden";

export function isNarrativeScriptReady(narrative: Narrative | null): boolean {
  return narrative?.status === "ready";
}

export function shouldShowVoiceCard(narrative: Narrative | null): boolean {
  return Boolean(narrative?.report_date);
}
