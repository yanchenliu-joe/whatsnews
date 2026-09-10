import { STREAK_ACTIVE_THRESHOLD } from "./streakDates";

/**
 * 32-badge achievement system (2026-07-11 design pass) — replicates the
 * reference mockup's "30 Badges" grid. The mockup's own header text says
 * "30 unlocked" but the grid it draws has 32 distinct badges — a real
 * inconsistency in the source image, not a miscount here. Implemented all
 * 32 shown rather than arbitrarily dropping 2 to force the number to match;
 * the UI reads the real array length rather than a hardcoded "30".
 *
 * Every badge here needed a real unlock rule invented against this app's
 * actual tracked data — the mockup only specifies names/icons, not
 * semantics. Rules are documented per-badge below. None of this required a
 * backend change; everything is derived from local on-device tracking (see
 * context/AchievementsContext.tsx).
 *
 * Badge names/descriptions are deliberately English-only, not run through
 * i18n — matching the existing precedent for PDF export HTML and
 * server-provided voice-profile labels (see docs/ENGINEERING.md). Translating 32
 * badges x 2 fields x 12 languages was judged out of proportion to this
 * pass's actual scope; all surrounding screen chrome ("All Badges",
 * "Locked", "Unlocked", etc.) is still fully translated.
 */

export type BadgeId =
  | "first_steps"
  | "streak_3"
  | "streak_7"
  | "streak_14"
  | "streak_30"
  | "early_bird"
  | "night_owl"
  | "weekend_warrior"
  | "topic_explorer"
  | "news_enthusiast"
  | "deep_reader"
  | "quick_catch"
  | "consistent_reader"
  | "knowledge_seeker"
  | "global_citizen"
  | "market_watcher"
  | "tech_lover"
  | "politics_watcher"
  | "business_minded"
  | "health_focused"
  | "green_guardian"
  | "science_geek"
  | "culture_vulture"
  | "travel_seeker"
  | "crypto_curious"
  | "ai_enthusiast"
  | "sports_fan"
  | "photo_lover"
  | "video_watcher"
  | "audio_listener"
  | "sharer"
  | "completionist";

export type BadgeColor = "green" | "orange" | "yellow" | "blue" | "purple" | "rose" | "navy" | "gold";

export type BadgeDef = {
  id: BadgeId;
  name: string;
  description: string;
  icon: string; // emoji glyph
  color: BadgeColor;
};

export const BADGE_DEFS: BadgeDef[] = [
  { id: "first_steps", name: "First Steps", description: "Read your first article", icon: "👟", color: "green" },
  { id: "streak_3", name: "3-Day Streak", description: "Keep a 3-day reading streak", icon: "🔥", color: "orange" },
  { id: "streak_7", name: "1-Week Streak", description: "Keep a 7-day reading streak", icon: "⚡", color: "yellow" },
  { id: "streak_14", name: "2-Week Streak", description: "Keep a 14-day reading streak", icon: "🏆", color: "gold" },
  { id: "streak_30", name: "30-Day Streak", description: "Keep a 30-day reading streak", icon: "💎", color: "blue" },
  { id: "early_bird", name: "Early Bird", description: "Read an article between 6:00 and 6:30am", icon: "☀️", color: "yellow" },
  { id: "night_owl", name: "Night Owl", description: "Read an article between 11pm and 4am", icon: "🌙", color: "navy" },
  { id: "weekend_warrior", name: "Weekend Warrior", description: "Have an active reading day on a weekend", icon: "🛌", color: "orange" },
  { id: "topic_explorer", name: "Topic Explorer", description: "Read from 5 different topics", icon: "🧭", color: "blue" },
  { id: "news_enthusiast", name: "News Enthusiast", description: "Read 25 articles total", icon: "🔍", color: "yellow" },
  { id: "deep_reader", name: "Deep Reader", description: "Read 50 articles total", icon: "📖", color: "purple" },
  { id: "quick_catch", name: "Quick Catch", description: "Read 5 articles in a single day", icon: "⏱️", color: "blue" },
  { id: "consistent_reader", name: "Consistent Reader", description: "Be active on 10 different days", icon: "🛡️", color: "green" },
  { id: "knowledge_seeker", name: "Knowledge Seeker", description: "Read from 10 different topics", icon: "🧠", color: "rose" },
  { id: "global_citizen", name: "Global Citizen", description: "Read 3 Geopolitics stories", icon: "🌍", color: "blue" },
  { id: "market_watcher", name: "Market Watcher", description: "Read 3 Markets stories", icon: "📈", color: "green" },
  { id: "tech_lover", name: "Tech Lover", description: "Read 3 Technology stories", icon: "💻", color: "blue" },
  { id: "politics_watcher", name: "Politics Watcher", description: "Read 3 Politics stories", icon: "🏛️", color: "purple" },
  { id: "business_minded", name: "Business Minded", description: "Read 3 Business stories", icon: "💼", color: "orange" },
  { id: "health_focused", name: "Health Focused", description: "Read 3 Healthcare stories", icon: "❤️", color: "rose" },
  { id: "green_guardian", name: "Green Guardian", description: "Read 3 Climate Change stories", icon: "🍃", color: "green" },
  { id: "science_geek", name: "Science Geek", description: "Read 3 Science stories", icon: "🧪", color: "blue" },
  { id: "culture_vulture", name: "Culture Vulture", description: "Read 3 Entertainment stories", icon: "🎭", color: "purple" },
  { id: "travel_seeker", name: "Travel Seeker", description: "Read 3 Transportation stories", icon: "✈️", color: "blue" },
  { id: "crypto_curious", name: "Crypto Curious", description: "Read 3 Crypto stories", icon: "₿", color: "orange" },
  { id: "ai_enthusiast", name: "AI Enthusiast", description: "Read 3 Artificial Intelligence stories", icon: "🤖", color: "purple" },
  { id: "sports_fan", name: "Sports Fan", description: "Read 3 Sports stories", icon: "⚽", color: "green" },
  { id: "photo_lover", name: "Photo Lover", description: "Open 10 articles with a photo", icon: "📷", color: "rose" },
  { id: "video_watcher", name: "Video Watcher", description: "Open Watch Next", icon: "▶️", color: "rose" },
  { id: "audio_listener", name: "Audio Listener", description: "Play a briefing narration", icon: "🎧", color: "blue" },
  { id: "sharer", name: "Sharer", description: "Share an article or briefing", icon: "🔗", color: "blue" },
  { id: "completionist", name: "Completionist", description: "Unlock every other badge", icon: "👑", color: "gold" },
];

// Topic-specific badges map to this app's real topic names (utils/topicsList.ts).
// A few mockup names have no exact match — mapped to the closest real topic,
// noted here so the approximation is traceable:
//   Global Citizen -> "Geopolitics" (no "World" topic exists)
//   Health Focused -> "Healthcare"
//   Green Guardian -> "Climate Change"
//   Culture Vulture -> "Entertainment"
//   Travel Seeker -> "Transportation" (no "Travel" topic exists — weakest mapping)
export const TOPIC_BADGE_MAP: Partial<Record<BadgeId, string>> = {
  global_citizen: "Geopolitics",
  market_watcher: "Markets",
  tech_lover: "Technology",
  politics_watcher: "Politics",
  business_minded: "Business",
  health_focused: "Healthcare",
  green_guardian: "Climate Change",
  science_geek: "Science",
  culture_vulture: "Entertainment",
  travel_seeker: "Transportation",
  crypto_curious: "Crypto",
  ai_enthusiast: "Artificial Intelligence",
  sports_fan: "Sports",
};

/**
 * Reads of one specific topic needed to unlock that topic's badge (e.g.
 * Tech Lover, AI Enthusiast) — raised from 1 to 3 (2026-07-11, same day
 * as the badge system shipped) per direct user feedback: unlocking a
 * topic badge from a single article felt too easy. Does not apply to the
 * breadth badges (Topic Explorer / Knowledge Seeker), which already
 * require touching 5/10 *different* topics — that bar was never the
 * complaint.
 */
export const TOPIC_BADGE_UNLOCK_THRESHOLD = 3;

export type AchievementInput = {
  longestStreak: number;
  totalActiveDays: number;
  streakHistory: Record<string, number>;
  /** Per-topic distinct-article-read counts (not just which topics were touched). */
  topicReadCounts: Record<string, number>;
  totalArticlesRead: number;
  earlyBirdUnlocked: boolean;
  nightOwlUnlocked: boolean;
  hasUsedShare: boolean;
  hasPlayedAudio: boolean;
  hasViewedWatchNext: boolean;
  photoArticlesOpened: number;
};

export type Badge = BadgeDef & { unlocked: boolean };

function isWeekendActiveDay(streakHistory: Record<string, number>): boolean {
  return Object.entries(streakHistory).some(([dateStr, count]) => {
    if (count < STREAK_ACTIVE_THRESHOLD) return false;
    const day = new Date(`${dateStr}T00:00:00`).getDay();
    return day === 0 || day === 6; // Sunday=0, Saturday=6
  });
}

function maxArticlesInOneDay(streakHistory: Record<string, number>): number {
  const values = Object.values(streakHistory);
  return values.length > 0 ? Math.max(...values) : 0;
}

/** Pure derivation — every badge's unlocked state computed fresh from input, nothing persisted here. */
export function computeUnlockedIds(input: AchievementInput): Set<BadgeId> {
  const unlocked = new Set<BadgeId>();
  // Breadth (any topic touched at all) vs. depth (read enough of one
  // specific topic) are different bars — see TOPIC_BADGE_UNLOCK_THRESHOLD.
  const topicsTouched = new Set(Object.keys(input.topicReadCounts));

  if (input.totalArticlesRead >= 1) unlocked.add("first_steps");
  if (input.longestStreak >= 3) unlocked.add("streak_3");
  if (input.longestStreak >= 7) unlocked.add("streak_7");
  if (input.longestStreak >= 14) unlocked.add("streak_14");
  if (input.longestStreak >= 30) unlocked.add("streak_30");
  if (input.earlyBirdUnlocked) unlocked.add("early_bird");
  if (input.nightOwlUnlocked) unlocked.add("night_owl");
  if (isWeekendActiveDay(input.streakHistory)) unlocked.add("weekend_warrior");
  if (topicsTouched.size >= 5) unlocked.add("topic_explorer");
  if (input.totalArticlesRead >= 25) unlocked.add("news_enthusiast");
  if (input.totalArticlesRead >= 50) unlocked.add("deep_reader");
  if (maxArticlesInOneDay(input.streakHistory) >= 5) unlocked.add("quick_catch");
  if (input.totalActiveDays >= 10) unlocked.add("consistent_reader");
  if (topicsTouched.size >= 10) unlocked.add("knowledge_seeker");
  if (input.photoArticlesOpened >= 10) unlocked.add("photo_lover");
  if (input.hasViewedWatchNext) unlocked.add("video_watcher");
  if (input.hasPlayedAudio) unlocked.add("audio_listener");
  if (input.hasUsedShare) unlocked.add("sharer");

  for (const [badgeId, topicName] of Object.entries(TOPIC_BADGE_MAP)) {
    if ((input.topicReadCounts[topicName] ?? 0) >= TOPIC_BADGE_UNLOCK_THRESHOLD) {
      unlocked.add(badgeId as BadgeId);
    }
  }

  // Meta-badge: everything else unlocked.
  const others = BADGE_DEFS.filter((b) => b.id !== "completionist");
  if (others.every((b) => unlocked.has(b.id))) unlocked.add("completionist");

  return unlocked;
}

export function computeBadges(input: AchievementInput): Badge[] {
  const unlockedIds = computeUnlockedIds(input);
  return BADGE_DEFS.map((def) => ({ ...def, unlocked: unlockedIds.has(def.id) }));
}
