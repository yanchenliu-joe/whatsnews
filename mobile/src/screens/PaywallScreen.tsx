import { useEffect, useRef, useState } from "react";
import * as Haptics from "expo-haptics";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useTranslation } from "react-i18next";
import { useSubscription } from "../context/SubscriptionContext";
import { PLANS } from "../services/purchases";
import type { PlanId } from "../services/purchases";
import type { RootStackParamList } from "../navigation/types";
import { colors, radii } from "../theme";
import { trackEvent } from "../services/analytics";
import { isRTL } from "../utils/rtl";

type Props = NativeStackScreenProps<RootStackParamList, "Paywall">;

const PLAN_LABEL_KEYS: Record<PlanId, string> = {
  annual: "paywall.planAnnual",
  monthly: "paywall.planMonthly",
};
const PLAN_PERIOD_KEYS: Record<PlanId, string> = {
  annual: "paywall.periodYear",
  monthly: "paywall.periodMonth",
};

export default function PaywallScreen({ route }: Props) {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const { purchase, restore } = useSubscription();

  const FEATURES = [
    { label: t("paywall.featureArchive") },
    { label: t("paywall.featureAiAssistant") },
    { label: t("paywall.featureSync") },
    { label: t("paywall.featureAdFree") },
  ];
  const [selectedPlan, setSelectedPlan] = useState<PlanId>("annual");
  const [busy, setBusy] = useState(false);

  const trigger = route.params?.trigger;
  const convertedRef = useRef(false);

  useEffect(() => {
    trackEvent("paywall_viewed", { metadata_text: trigger });
    return () => {
      // fires when modal closes — dismissed if user never purchased
      if (!convertedRef.current) {
        trackEvent("paywall_dismissed", { metadata_text: trigger });
      }
    };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function handlePurchase() {
    setBusy(true);
    const success = await purchase(selectedPlan);
    setBusy(false);
    if (success) {
      convertedRef.current = true;
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      trackEvent("paywall_converted", { metadata_text: selectedPlan });
      navigation.goBack();
    } else {
      Alert.alert(t("paywall.errorTitle"), t("paywall.errorMessage"));
    }
  }

  async function handleRestore() {
    setBusy(true);
    const found = await restore();
    setBusy(false);
    if (found) {
      navigation.goBack();
    } else {
      Alert.alert(t("paywall.noPurchasesFoundTitle"), t("paywall.noPurchasesFoundMessage"));
    }
  }

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      {/* Close */}
      <TouchableOpacity
        style={[styles.closeBtn, isRTL() && styles.closeBtnRTL]}
        onPress={() => navigation.goBack()}
        activeOpacity={0.7}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.brand}>WhatsNews</Text>
          <Text style={styles.tier}>{t("paywall.premium")}</Text>
          <Text style={styles.headline}>
            {trigger === "archive"
              ? t("paywall.headlineArchive")
              : trigger === "ai"
                ? t("paywall.headlineAi")
                : t("paywall.headlineDefault")}
          </Text>
        </View>

        {/* Divider */}
        <View style={styles.divider} />

        {/* Feature list */}
        <View style={styles.features}>
          <Text style={styles.featuresLabel}>{t("paywall.whatsIncluded")}</Text>
          {FEATURES.map((f) => (
            <View key={f.label} style={styles.featureRow}>
              <Text style={styles.featureCheck}>✓</Text>
              <Text style={styles.featureText}>{f.label}</Text>
            </View>
          ))}
        </View>

        <View style={styles.divider} />

        {/* Plan selector */}
        <View style={styles.plans}>
          {PLANS.map((plan) => {
            const selected = selectedPlan === plan.id;
            return (
              <TouchableOpacity
                key={plan.id}
                style={[styles.planCard, selected && styles.planCardSelected]}
                onPress={() => setSelectedPlan(plan.id)}
                activeOpacity={0.8}
              >
                <View style={styles.planLeft}>
                  <Text style={[styles.planLabel, selected && styles.planLabelSelected]}>
                    {t(PLAN_LABEL_KEYS[plan.id])}
                  </Text>
                  <Text style={[styles.planPrice, selected && styles.planPriceSelected]}>
                    {plan.price}
                    <Text style={styles.planPeriod}>{t(PLAN_PERIOD_KEYS[plan.id])}</Text>
                  </Text>
                </View>
                {plan.badge ? (
                  <View style={[styles.badge, selected && styles.badgeSelected]}>
                    <Text style={[styles.badgeText, selected && styles.badgeTextSelected]}>
                      {t("paywall.badgeSave33")}
                    </Text>
                  </View>
                ) : null}
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Subscribe button */}
        <TouchableOpacity
          style={[styles.subscribeBtn, busy && styles.subscribeBtnBusy]}
          onPress={handlePurchase}
          activeOpacity={0.85}
          disabled={busy}
        >
          {busy ? (
            <ActivityIndicator color={colors.white} />
          ) : (
            <Text style={styles.subscribeBtnText}>
              {t("paywall.startTrial")}
            </Text>
          )}
        </TouchableOpacity>

        <Text style={styles.trialNote}>
          {t("paywall.trialNote", {
            price: selectedPlan === "annual" ? "$39.99/year" : "$4.99/month",
          })}
        </Text>

        {/* Footer links */}
        <View style={styles.footer}>
          <TouchableOpacity onPress={handleRestore} activeOpacity={0.7}>
            <Text style={styles.footerLink}>{t("account.restorePurchases")}</Text>
          </TouchableOpacity>
          <Text style={styles.footerDot}>·</Text>
          <Text style={styles.footerMuted}>{t("paywall.termsShort")}</Text>
          <Text style={styles.footerDot}>·</Text>
          <Text style={styles.footerMuted}>{t("paywall.privacyShort")}</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  closeBtn: {
    position: "absolute",
    top: 56,
    right: 20,
    zIndex: 10,
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  closeBtnRTL: { right: undefined, left: 20 },
  closeText: {
    fontSize: 16,
    color: colors.muted,
  },
  scroll: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 28,
    paddingTop: 56,
    paddingBottom: 40,
  },

  // Header
  header: {
    marginBottom: 28,
  },
  brand: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginBottom: 8,
  },
  tier: {
    fontSize: 36,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -1,
    marginBottom: 12,
  },
  headline: {
    fontSize: 18,
    fontWeight: "500",
    color: colors.summary,
    lineHeight: 27,
  },

  // Divider
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 24,
  },

  // Features
  features: {
    gap: 14,
  },
  featuresLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 4,
  },
  featureRow: {
    flexDirection: "row",
    gap: 12,
    alignItems: "flex-start",
  },
  featureCheck: {
    fontSize: 14,
    fontWeight: "800",
    color: colors.ink,
    lineHeight: 23,
  },
  featureText: {
    fontSize: 15,
    color: colors.summary,
    lineHeight: 23,
    flex: 1,
  },

  // Plans
  plans: {
    gap: 10,
    marginBottom: 22,
  },
  planCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1.5,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingVertical: 18,
    paddingHorizontal: 18,
  },
  planCardSelected: {
    borderColor: colors.ink,
    backgroundColor: colors.ink,
  },
  planLeft: {
    gap: 3,
  },
  planLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  planLabelSelected: {
    color: "rgba(255,255,255,0.6)",
  },
  planPrice: {
    fontSize: 22,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.5,
  },
  planPriceSelected: {
    color: colors.white,
  },
  planPeriod: {
    fontSize: 13,
    fontWeight: "400",
  },
  badge: {
    borderRadius: 20,
    paddingVertical: 5,
    paddingHorizontal: 10,
    backgroundColor: colors.surfaceMuted,
  },
  badgeSelected: {
    backgroundColor: "rgba(255,255,255,0.15)",
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.muted,
    letterSpacing: 0.3,
  },
  badgeTextSelected: {
    color: colors.white,
  },

  // Subscribe button
  subscribeBtn: {
    backgroundColor: colors.ink,
    borderRadius: 14,
    paddingVertical: 18,
    alignItems: "center",
    marginBottom: 14,
  },
  subscribeBtnBusy: {
    backgroundColor: colors.muted,
  },
  subscribeBtnText: {
    fontSize: 17,
    fontWeight: "700",
    color: colors.white,
    letterSpacing: -0.2,
  },

  // Trial note
  trialNote: {
    fontSize: 12,
    color: colors.metaText,
    textAlign: "center",
    lineHeight: 18,
    marginBottom: 24,
  },

  // Footer
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  footerLink: {
    fontSize: 12,
    color: colors.ink,
    fontWeight: "500",
  },
  footerDot: {
    fontSize: 12,
    color: colors.faint,
  },
  footerMuted: {
    fontSize: 12,
    color: colors.muted,
  },
});
