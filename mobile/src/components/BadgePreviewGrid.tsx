import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import BadgeHexagon from "./BadgeHexagon";
import { colors } from "../theme";
import type { Badge } from "../utils/badges";

type Props = {
  badges: Badge[];
};

/** First-N preview strip on StreakScreen — the full 32-badge grid lives on AllBadgesScreen. */
export default function BadgePreviewGrid({ badges }: Props) {
  const { t } = useTranslation();
  return (
    <View style={styles.row}>
      {badges.map((badge) => (
        <View key={badge.id} style={styles.tile}>
          <BadgeHexagon icon={badge.icon} color={badge.color} locked={!badge.unlocked} size={56} />
          <Text style={styles.name} numberOfLines={2}>
            {badge.name}
          </Text>
          <Text style={[styles.status, badge.unlocked && styles.statusUnlocked]}>
            {badge.unlocked ? t("badges.unlocked") : t("badges.locked")}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 16,
  },
  tile: {
    flex: 1,
    alignItems: "center",
    gap: 6,
  },
  name: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.ink,
    textAlign: "center",
    lineHeight: 14,
  },
  status: {
    fontSize: 10,
    color: colors.faint,
  },
  statusUnlocked: {
    color: colors.success,
    fontWeight: "600",
  },
});
