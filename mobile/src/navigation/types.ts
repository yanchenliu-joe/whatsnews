import type { CompositeNavigationProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";

// ─── Article navigation params ─────────────────────────────────────────────────
// Unified structure passed to ArticleDetail from every call site.
// Rule: no screen fetches the article again if it already exists in these params.

export type ArticleDetailParams = {
  title: string;
  summary: string;
  bodyText?: string | null;
  source: string;
  url: string;
  topic: string;
  publishedAt?: string | null;
  whyItMatters?: string;
  articleId?: string;
  imageUrl?: string | null;
};

// ─── AI Assistant context ──────────────────────────────────────────────────────
// AI Assistant is NOT a chatbot — it is a news intelligence layer.
// It receives contextual params so it can pre-load insight without a second
// fetch. The `mode` field controls which intelligence path is activated.

export type AIAssistantContext = {
  article?: {
    title: string;
    url: string;
    topic: string;
    source?: string;
  };
  topic?: string;
  source?: string;
  // Must match a valid backend AIMode value. "simple_qa" is the general-purpose fallback.
  mode: "article_insight" | "daily_brief" | "simple_qa";
};

// ─── Paywall gate trigger ──────────────────────────────────────────────────────
// Kept only because the Paywall route itself is kept registered-but-unreachable
// (see RootStackParamList's Paywall entry below) — no longer read by SignIn,
// since all premium gating was removed in the 2026-07-10 free-version pivot.

export type PaywallTrigger = "archive" | "ai" | "export" | "generic";

// ─── Root stack ──────────────────────────────────────────────────────────────

export type RootStackParamList = {
  MainTabs: undefined;

  // ArticleDetail — full-content view. Article data is passed as params so the
  // screen never needs to fetch. Bridges into the AI Assistant layer.
  ArticleDetail: ArticleDetailParams;

  // AIAssistant — the application's intelligence hub (Phase 22+). Route kept
  // registered but currently unreachable — the "Ask AI" entry point was
  // removed from ArticleDetail in the 2026-07-10 free-version pivot (no
  // OpenAI key in production, and this endpoint has no rule-based fallback).
  AIAssistant: AIAssistantContext;

  // Paywall — subscription gate. Route kept registered but currently
  // unreachable — all premium gating was removed in the 2026-07-10
  // free-version pivot (the app has no paid tier).
  Paywall: { trigger: PaywallTrigger };

  // SignIn — dedicated auth screen (Phase 36, added 2026-07-06). Presented as
  // a modal, same as Paywall. Always opened from AccountScreen's own "Sign
  // In / Sign Up" row now — success just goes back to Account.
  SignIn: undefined;

  // ManageTopics — extracted from AccountScreen's inline topics grid
  // (Phase 37, added 2026-07-06). Pushed screen, not modal.
  ManageTopics: undefined;

  // Saved — re-wired in from the previously orphaned SavedScreen.tsx
  // (Phase 37, added 2026-07-06). Pushed screen, not modal.
  Saved: undefined;

  // LanguagePicker — app UI language switch, 12 languages (Phase 38, added
  // 2026-07-06). Pushed screen, not modal.
  LanguagePicker: undefined;

  // AllBadges — full 32-badge achievement grid (2026-07-11 design pass).
  // Pushed off StreakScreen's "View All Badges" button, not modal.
  AllBadges: undefined;

  // Search — global cross-topic article search (2026-07-13), reachable from
  // AppHeader's search icon. Reuses GET /history/search exactly as Archive's
  // own inline search already does — the query was already cross-topic, the
  // gap was discoverability. Pushed screen, not modal.
  Search: undefined;

  // ── Future root-stack screens ──────────────────────────────────────────────
  //
  // Notifications — push notification history and opt-in management.
  //   Notifications: undefined;
};

// ─── Main tab bar ─────────────────────────────────────────────────────────────

export type MainTabParamList = {
  Briefing: undefined;
  Archive: undefined;
  Streak: undefined;
  Account: undefined;
};

// ─── Composite navigation prop ───────────────────────────────────────────────
// Screens inside the tab bar may need to navigate to root-stack screens.
// Use this type with useNavigation() to get type-safe access to both
// tab routes and root-stack routes from a single call site.

export type AppNavigationProp = CompositeNavigationProp<
  BottomTabNavigationProp<MainTabParamList>,
  NativeStackNavigationProp<RootStackParamList>
>;
