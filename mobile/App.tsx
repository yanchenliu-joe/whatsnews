import { useEffect, useRef, useState } from "react";
import { NavigationContainer, createNavigationContainerRef } from "@react-navigation/native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Notifications from "expo-notifications";
import * as Sentry from "@sentry/react-native";
import * as SplashScreen from "expo-splash-screen";
import {
  useFonts,
  Newsreader_400Regular,
  Newsreader_500Medium,
  Newsreader_600SemiBold,
  Newsreader_600SemiBold_Italic,
  Newsreader_700Bold,
} from "@expo-google-fonts/newsreader";
import "./src/i18n";
import { AuthProvider } from "./src/context/AuthContext";
import { SavedArticlesProvider } from "./src/context/SavedArticlesContext";
import { UserPreferencesProvider } from "./src/context/UserPreferencesContext";
import { ReadingProgressProvider } from "./src/context/ReadingProgressContext";
import { AchievementsProvider } from "./src/context/AchievementsContext";
import { ReadingSettingsProvider } from "./src/context/ReadingSettingsContext";
import { SubscriptionProvider } from "./src/context/SubscriptionContext";
import LanguageSync from "./src/components/LanguageSync";
import BadgeUnlockNotifier from "./src/components/BadgeUnlockNotifier";
import RootNavigator from "./src/navigation/RootNavigator";
import type { RootStackParamList } from "./src/navigation/types";
import OnboardingScreen from "./src/screens/OnboardingScreen";
import { ONBOARDING_COMPLETED_KEY, SENTRY_DSN } from "./src/config";
import {
  handleNotificationResponse,
  registerForPushNotifications,
  registerNotificationTapHandler,
} from "./src/services/pushNotifications";

// Crash/error monitoring (2026-07-09). No-op when EXPO_PUBLIC_SENTRY_DSN is
// unset, same pattern as every other optional integration in this app.
if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    // Error monitoring only — no performance tracing (matches the Sentry
    // project's onboarding selection, keeps well within the free tier).
    tracesSampleRate: 0,
  });
}

// Keeps the native splash screen up until fonts + the onboarding-flag check
// below both resolve — without this, useFonts() loading async would show a
// blank white frame before the Newsreader headline font is ready.
SplashScreen.preventAutoHideAsync().catch(() => {});

const navigationRef = createNavigationContainerRef<RootStackParamList>();

function App() {
  // Editorial headline typeface (2026-07-11 design pass) — see
  // src/utils/headlineFont.ts for why only these 5 weights are loaded and
  // which UI languages actually use it.
  const [fontsLoaded] = useFonts({
    Newsreader_400Regular,
    Newsreader_500Medium,
    Newsreader_600SemiBold,
    Newsreader_600SemiBold_Italic,
    Newsreader_700Bold,
  });
  // null = loading, false = needs onboarding, true = onboarding done
  const [onboardingDone, setOnboardingDone] = useState<boolean | null>(null);
  // Cold start: app launched by tapping a notification. Recommended API per
  // expo-notifications docs (getLastNotificationResponseAsync is deprecated
  // in favor of this hook for exactly this use case).
  const lastNotificationResponse = Notifications.useLastNotificationResponse();
  const handledColdStartRef = useRef(false);

  useEffect(() => {
    AsyncStorage.getItem(ONBOARDING_COMPLETED_KEY).then((val) => {
      setOnboardingDone(val === "true");
    }).catch(() => {
      setOnboardingDone(true); // on storage error, skip onboarding
    });
  }, []);

  // Register for push notifications only after onboarding is complete.
  // This prevents the permission dialog from firing mid-onboarding.
  useEffect(() => {
    if (onboardingDone === true) {
      void registerForPushNotifications();
    }
  }, [onboardingDone]);

  // Warm taps: app already running (foreground or backgrounded) when tapped.
  useEffect(() => {
    if (onboardingDone !== true) return;
    return registerNotificationTapHandler(navigationRef);
  }, [onboardingDone]);

  // Cold-start tap: app was killed, this notification launched it.
  useEffect(() => {
    if (onboardingDone !== true || !lastNotificationResponse) return;
    if (handledColdStartRef.current) return;
    handledColdStartRef.current = true;
    handleNotificationResponse(navigationRef, lastNotificationResponse);
  }, [onboardingDone, lastNotificationResponse]);

  useEffect(() => {
    if (fontsLoaded && onboardingDone !== null) {
      void SplashScreen.hideAsync();
    }
  }, [fontsLoaded, onboardingDone]);

  if (!fontsLoaded || onboardingDone === null) {
    // Loading fonts and/or the onboarding flag from storage — native splash
    // screen stays up (see preventAutoHideAsync() above), nothing to render.
    return null;
  }

  return (
    <SafeAreaProvider>
      <AuthProvider>
        <SavedArticlesProvider>
          <UserPreferencesProvider>
            <SubscriptionProvider>
            <ReadingProgressProvider>
            <AchievementsProvider>
            <ReadingSettingsProvider>
              <LanguageSync />
              <BadgeUnlockNotifier />
              {!onboardingDone ? (
                <OnboardingScreen onComplete={() => setOnboardingDone(true)} />
              ) : (
                <NavigationContainer ref={navigationRef}>
                  <RootNavigator />
                </NavigationContainer>
              )}
            </ReadingSettingsProvider>
            </AchievementsProvider>
            </ReadingProgressProvider>
            </SubscriptionProvider>
          </UserPreferencesProvider>
        </SavedArticlesProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}

export default Sentry.wrap(App);
