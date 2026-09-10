import { createNativeStackNavigator } from "@react-navigation/native-stack";
import AIAssistantScreen from "../screens/AIAssistantScreen";
import AllBadgesScreen from "../screens/AllBadgesScreen";
import ArticleDetailScreen from "../screens/ArticleDetailScreen";
import LanguagePickerScreen from "../screens/LanguagePickerScreen";
import ManageTopicsScreen from "../screens/ManageTopicsScreen";
import PaywallScreen from "../screens/PaywallScreen";
import SavedScreen from "../screens/SavedScreen";
import SearchScreen from "../screens/SearchScreen";
import SignInScreen from "../screens/SignInScreen";
import MainTabNavigator from "./MainTabNavigator";
import type { RootStackParamList } from "./types";

const Stack = createNativeStackNavigator<RootStackParamList>();

// ─── Product flows ─────────────────────────────────────────────────────────────
//
// Flow A — Reading:  Briefing → ArticleDetail → AIAssistant → goBack
// Flow B — Saved:    Account "Saved Articles" row → Saved → ArticleDetail → goBack
// Flow C — History:  HistoryScreen → ArticleDetail → goBack
// Flow D — Topics:   Account "Manage Topics" row → ManageTopics → goBack

export default function RootNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="MainTabs" component={MainTabNavigator} />

      <Stack.Screen name="ArticleDetail" component={ArticleDetailScreen} />

      {/* AIAssistant — context-aware intelligence hub (Phase 22). Route kept
          registered but currently unreachable: the "Ask AI" entry point was
          removed from ArticleDetail as part of the 2026-07-10 free-version
          pivot (no OpenAI key in production, and this endpoint has no
          rule-based fallback). See docs/ENGINEERING.md's AI Pipeline section. */}
      <Stack.Screen name="AIAssistant" component={AIAssistantScreen} />

      {/* Paywall — subscription gate. Route kept registered but currently
          unreachable: all premium gating (Archive lock, AccountScreen's
          upgrade banner) was removed as part of the 2026-07-10 free-version
          pivot — the app has no paid tier. See docs/ENGINEERING.md's Mobile
          pivot" / "Subscription removal". */}
      <Stack.Screen
        name="Paywall"
        component={PaywallScreen}
        options={{ presentation: "modal" }}
      />

      {/* SignIn — dedicated auth screen (Phase 36). Presented as a modal from
          AccountScreen's "Sign In / Sign Up" row. */}
      <Stack.Screen
        name="SignIn"
        component={SignInScreen}
        options={{ presentation: "modal" }}
      />

      {/* ManageTopics / Saved — pushed sub-screens off AccountScreen's
          Settings-list redesign (Phase 37). */}
      <Stack.Screen name="ManageTopics" component={ManageTopicsScreen} />
      <Stack.Screen name="Saved" component={SavedScreen} />

      {/* LanguagePicker — 12-language UI switch (Phase 38). */}
      <Stack.Screen name="LanguagePicker" component={LanguagePickerScreen} />

      {/* AllBadges — full 32-badge achievement grid (2026-07-11 design pass),
          pushed off StreakScreen's "View All Badges" button. */}
      <Stack.Screen name="AllBadges" component={AllBadgesScreen} />

      {/* Search — global cross-topic search (2026-07-13), reachable from
          AppHeader's search icon anywhere the header renders. Reuses
          GET /history/search exactly as Archive's own inline search does. */}
      <Stack.Screen name="Search" component={SearchScreen} />

      {/*
       * ── Future root-stack screens ──────────────────────────────────────────
       *
       * Notifications — push history and opt-in management.
       *   <Stack.Screen name="Notifications" component={NotificationsScreen} />
       */}
    </Stack.Navigator>
  );
}
