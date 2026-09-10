import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useTranslation } from "react-i18next";
import { colors, radii, spacing } from "../theme";

type Props = {
  visible: boolean;
  onDismiss: () => void;
};

/**
 * One-time (ever, not per-article) explainer shown the first time a user
 * opens an article — full-text scraping was dropped 2026-07-11 (see
 * docs/ENGINEERING.md), so Read mode now only ever shows the summary. This tells
 * people where the original article still is: Web Mode or the "•••" menu's
 * "Open in Browser." Illustration reuses the exact glyphs the real Web
 * Mode FAB / more-menu already render (🌐 / •••), rather than a drawn
 * abstraction — showing the literal icon the user will tap.
 */
export default function FullTextNoticeModal({ visible, onDismiss }: Props) {
  const { t } = useTranslation();

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onDismiss}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>{t("articleDetail.fullTextNoticeTitle")}</Text>
          <Text style={styles.body}>{t("articleDetail.fullTextNoticeBody")}</Text>

          <View style={styles.illustrationRow}>
            <View style={styles.illustrationItem}>
              <View style={styles.iconCircle}>
                <Text style={styles.iconGlyph}>🌐</Text>
              </View>
              <Text style={styles.illustrationLabel}>
                {t("articleDetail.fullTextNoticeWebModeLabel")}
              </Text>
            </View>
            <Text style={styles.orText}>{t("common.or")}</Text>
            <View style={styles.illustrationItem}>
              <View style={styles.iconCircle}>
                <Text style={styles.iconGlyphDots}>•••</Text>
              </View>
              <Text style={styles.illustrationLabel}>
                {t("articleDetail.fullTextNoticeMoreMenuLabel")}
              </Text>
            </View>
          </View>

          <TouchableOpacity style={styles.gotItBtn} onPress={onDismiss} activeOpacity={0.85}>
            <Text style={styles.gotItText}>{t("articleDetail.fullTextNoticeGotIt")}</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.screenPaddingH,
  },
  card: {
    width: "100%",
    maxWidth: 360,
    backgroundColor: colors.cardBg,
    borderRadius: radii.lg,
    padding: 22,
    alignItems: "center",
  },
  title: {
    fontSize: 17,
    fontWeight: "800",
    color: colors.ink,
    textAlign: "center",
    marginBottom: 8,
  },
  body: {
    fontSize: 13.5,
    lineHeight: 20,
    color: colors.muted,
    textAlign: "center",
    marginBottom: 20,
  },
  illustrationRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    marginBottom: 22,
  },
  illustrationItem: { alignItems: "center", gap: 6, width: 96 },
  iconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  iconGlyph: { fontSize: 20 },
  iconGlyphDots: { fontSize: 16, fontWeight: "700", color: colors.ink, letterSpacing: 1 },
  illustrationLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.muted,
    textAlign: "center",
  },
  orText: { fontSize: 11, fontWeight: "700", color: colors.faint },
  gotItBtn: {
    alignSelf: "stretch",
    backgroundColor: colors.ink,
    borderRadius: radii.pill,
    paddingVertical: 13,
    alignItems: "center",
  },
  gotItText: { fontSize: 14, fontWeight: "700", color: colors.white },
});
