import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants, { ExecutionEnvironment } from "expo-constants";
import { PREMIUM_KEY, REVENUECAT_IOS_KEY } from "../config";

export type PlanId = "annual" | "monthly";

export type SubscriptionPlan = {
  id: PlanId;
  label: string;
  price: string;
  period: string;
  badge?: string;
};

export const PLANS: SubscriptionPlan[] = [
  { id: "annual",  label: "Annual",  price: "$39.99", period: "/ year",  badge: "Save 33%" },
  { id: "monthly", label: "Monthly", price: "$4.99",  period: "/ month" },
];

// Use mock mode when:
//   • Running in Expo Go (StoreClient) — native modules not available
//   • No RevenueCat API key configured
const IS_EXPO_GO =
  Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
const USE_MOCK = IS_EXPO_GO || !REVENUECAT_IOS_KEY;

const ENTITLEMENT_ID = "premium";
const PACKAGE_IDS: Record<PlanId, string> = { annual: "annual", monthly: "monthly" };

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Configures RevenueCat, optionally identified as `appUserID` (the Supabase
 * auth user id) from the start — used on cold start when a session is
 * already persisted. When no user is signed in yet, RC assigns its own
 * anonymous id; call identifyPurchaser() once sign-in completes to link it.
 */
export function initPurchases(appUserID?: string): void {
  if (USE_MOCK) return;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const RC = require("react-native-purchases");
    const Purchases = RC.default;
    const { LOG_LEVEL } = RC;
    Purchases.setLogLevel(__DEV__ ? LOG_LEVEL.DEBUG : LOG_LEVEL.ERROR);
    Purchases.configure(appUserID ? { apiKey: REVENUECAT_IOS_KEY, appUserID } : { apiKey: REVENUECAT_IOS_KEY });
  } catch {
    // Non-fatal — app works without RC
  }
}

/**
 * Links the current RevenueCat identity (anonymous or otherwise) to the
 * given Supabase auth user id. Call on sign-in so the backend entitlements
 * table (keyed by profiles.id) matches what RevenueCat reports in webhooks.
 * Any purchase made before sign-in is transferred to this id by RevenueCat.
 */
export async function identifyPurchaser(userId: string): Promise<void> {
  if (USE_MOCK) return;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Purchases = require("react-native-purchases").default;
    await Purchases.logIn(userId);
  } catch {
    // Non-fatal — purchases still work under the previous (anonymous) id
  }
}

/** Reverts RevenueCat to an anonymous identity. Call on sign-out. */
export async function resetPurchaser(): Promise<void> {
  if (USE_MOCK) return;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Purchases = require("react-native-purchases").default;
    await Purchases.logOut();
  } catch {
    // Non-fatal
  }
}

export async function getIsPremium(): Promise<boolean> {
  if (USE_MOCK) {
    return (await AsyncStorage.getItem(PREMIUM_KEY)) === "true";
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Purchases = require("react-native-purchases").default;
    const info = await Purchases.getCustomerInfo();
    return info.entitlements.active[ENTITLEMENT_ID] !== undefined;
  } catch {
    return false;
  }
}

export async function purchasePlan(planId: PlanId): Promise<void> {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 800));
    await AsyncStorage.setItem(PREMIUM_KEY, "true");
    return;
  }
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Purchases = require("react-native-purchases").default;
  const offerings = await Purchases.getOfferings();
  const pkg = offerings.current?.availablePackages.find(
    (p: { identifier: string }) => p.identifier === PACKAGE_IDS[planId],
  );
  if (!pkg) throw new Error(`Package "${planId}" not found`);
  const { customerInfo } = await Purchases.purchasePackage(pkg);
  if (!customerInfo.entitlements.active[ENTITLEMENT_ID]) {
    throw new Error("Entitlement not active after purchase");
  }
}

export async function restorePurchases(): Promise<boolean> {
  if (USE_MOCK) {
    return (await AsyncStorage.getItem(PREMIUM_KEY)) === "true";
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const Purchases = require("react-native-purchases").default;
    const info = await Purchases.restorePurchases();
    return info.entitlements.active[ENTITLEMENT_ID] !== undefined;
  } catch {
    return false;
  }
}

export async function _devResetPremium(): Promise<void> {
  await AsyncStorage.removeItem(PREMIUM_KEY);
}
