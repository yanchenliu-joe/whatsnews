import type { ComponentType } from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";
import AccountScreen from "../screens/AccountScreen";
import AccountTabIcon from "../components/AccountTabIcon";
import ArchiveTabIcon from "../components/ArchiveTabIcon";
import BriefingScreen from "../screens/BriefingScreen";
import BriefingTabIcon from "../components/BriefingTabIcon";
import HistoryScreenContainer from "../screens/HistoryScreenContainer";
import StreakScreen from "../screens/StreakScreen";
import StreakTabIcon from "../components/StreakTabIcon";
import { colors } from "../theme";
import type { MainTabParamList } from "./types";

const Tab = createBottomTabNavigator<MainTabParamList>();

type TabIconComponent = ComponentType<{ size?: number; color?: string }>;

// Module-level constant, outside the component — can't call t() here, so
// this stores translation keys, looked up via t() inside WhatsNewsTabBar.
// Icon is a real react-native-svg component, not an approximate Unicode
// character — Unicode glyphs render inconsistently across iOS font/OS
// versions, same reasoning as SearchIcon/FilterIcon/PlayPauseIcon.
const TAB_CONFIG: Record<string, { Icon: TabIconComponent; labelKey: string | null }> = {
  Briefing: { Icon: BriefingTabIcon, labelKey: "tabs.briefing" },
  Archive:  { Icon: ArchiveTabIcon, labelKey: "tabs.archive" },
  Streak:   { Icon: StreakTabIcon, labelKey: "tabs.streak" },
  Account:  { Icon: AccountTabIcon, labelKey: "tabs.account" },
};

function WhatsNewsTabBar({ state, navigation }: BottomTabBarProps) {
  const insets = useSafeAreaInsets();
  const { t } = useTranslation();

  return (
    <View style={styles.tabBarWrapper}>
      <View style={styles.tabBar}>
        {state.routes.map((route, index) => {
          const focused = state.index === index;
          const cfg = TAB_CONFIG[route.name] ?? { Icon: BriefingTabIcon, labelKey: null };
          const label = cfg.labelKey ? t(cfg.labelKey) : route.name;

          const onPress = () => {
            const event = navigation.emit({
              type: "tabPress",
              target: route.key,
              canPreventDefault: true,
            });
            if (!focused && !event.defaultPrevented) {
              navigation.navigate(route.name);
            }
          };

          return (
            <TouchableOpacity
              key={route.key}
              style={styles.tabSlot}
              onPress={onPress}
              activeOpacity={0.8}
              accessibilityRole="tab"
              accessibilityState={{ selected: focused }}
            >
              {focused ? (
                <View style={styles.activePill}>
                  <cfg.Icon size={17} color={colors.white} />
                  <Text style={styles.activeLabel}>{label}</Text>
                </View>
              ) : (
                <cfg.Icon size={22} color={colors.muted} />
              )}
            </TouchableOpacity>
          );
        })}
      </View>
      {/* Pure reachability spacing above the home indicator — kept separate
          from `tabBar` above so its own vertical padding stays symmetric
          and the tab row visually centers in the bar instead of being
          pushed toward the top by a lopsided safe-area inset. */}
      <View style={{ height: Math.max(insets.bottom, 3) }} />
    </View>
  );
}

export default function MainTabNavigator() {
  return (
    <Tab.Navigator
      tabBar={(props) => <WhatsNewsTabBar {...props} />}
      screenOptions={{ headerShown: false }}
    >
      <Tab.Screen name="Briefing" component={BriefingScreen} />
      <Tab.Screen name="Archive" component={HistoryScreenContainer} />
      <Tab.Screen name="Streak" component={StreakScreen} />
      <Tab.Screen name="Account" component={AccountScreen} />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  tabBarWrapper: {
    backgroundColor: colors.bg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  tabBar: {
    flexDirection: "row",
    alignItems: "center",
    // Asymmetric on purpose: reducing paddingVertical symmetrically only
    // shrinks the bar's total height without moving the icon row's actual
    // position — a bigger paddingTop (vs. a near-zero paddingBottom) is
    // what actually pushes the row down, closer to the safe-area spacer
    // below, instead of leaving it centered in a now-smaller box.
    paddingTop: 18,
    paddingBottom: 0,
    paddingHorizontal: 12,
    gap: 8,
  },
  tabSlot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  activePill: {
    alignSelf: "stretch",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    backgroundColor: colors.ink,
    paddingVertical: 6,
    borderRadius: 999,
  },
  activeLabel: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.white,
  },
});
