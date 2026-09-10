import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useTranslation } from "react-i18next";
import SearchIcon from "./SearchIcon";
import { colors, shadows } from "../theme";
import { formatTimeAgo } from "../utils/formatTimeAgo";
import { NEWSREADER_FONT_FAMILY } from "../utils/headlineFont";

type Props = {
  onRefresh: () => void;
  lastUpdated: Date | null;
  onExportPdf?: () => void;
  isExporting?: boolean;
  onSearchPress?: () => void;
};

export default function AppHeader({
  onRefresh,
  lastUpdated,
  onExportPdf,
  isExporting,
  onSearchPress,
}: Props) {
  const { t } = useTranslation();
  return (
    <>
      <View style={styles.brand}>
        <View style={styles.brandTap}>
          <Text style={styles.brandName}>WhatsNews</Text>
          <Text style={styles.brandTagline}>{t("appHeader.tagline")}</Text>
        </View>

        <View style={styles.actions}>
          {onSearchPress ? (
            <TouchableOpacity
              onPress={onSearchPress}
              activeOpacity={0.6}
              style={styles.actionBtn}
              accessibilityLabel={t("search.title")}
              accessibilityRole="button"
            >
              <SearchIcon size={16} color={colors.muted} />
            </TouchableOpacity>
          ) : null}

          {onExportPdf ? (
            <TouchableOpacity
              onPress={onExportPdf}
              activeOpacity={0.6}
              style={styles.actionBtn}
              disabled={isExporting}
              accessibilityLabel={t("appHeader.exportPdf")}
              accessibilityRole="button"
            >
              {isExporting ? (
                <ActivityIndicator size="small" color={colors.muted} />
              ) : (
                <Text style={styles.actionIcon}>{"⎙"}</Text>
              )}
            </TouchableOpacity>
          ) : null}

          <TouchableOpacity onPress={onRefresh} activeOpacity={0.6} style={styles.actionBtn}>
            <Text style={styles.actionIcon}>{"↻"}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {lastUpdated ? (
        <Text style={styles.lastUpdated}>
          {t("appHeader.updated", { time: formatTimeAgo(lastUpdated.toISOString()) })}
        </Text>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  brand: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  brandTap: {
    gap: 3,
  },
  brandName: {
    fontFamily: NEWSREADER_FONT_FAMILY.bold,
    fontSize: 30,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.3,
  },
  brandTagline: {
    fontSize: 11,
    fontWeight: "400",
    color: colors.metaText,
    letterSpacing: 0.3,
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  actionBtn: {
    backgroundColor: colors.cardBg,
    borderRadius: 20,
    width: 38,
    height: 38,
    alignItems: "center",
    justifyContent: "center",
    ...shadows.card,
  },
  actionIcon: {
    fontSize: 17,
    color: colors.muted,
  },
  lastUpdated: {
    fontSize: 11,
    color: colors.faint,
    marginBottom: 14,
    letterSpacing: 0.1,
  },
});
