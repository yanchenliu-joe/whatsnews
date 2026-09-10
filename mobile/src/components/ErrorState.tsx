import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useTranslation } from "react-i18next";
import { colors } from "../theme";

type Props = {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  compact?: boolean;
};

export default function ErrorState({
  message,
  onRetry,
  retryLabel,
  compact = false,
}: Props) {
  const { t } = useTranslation();
  return (
    <View style={[styles.container, compact && styles.compact]}>
      <Text style={styles.message}>{message}</Text>
      {onRetry ? (
        <TouchableOpacity
          style={styles.retryBtn}
          onPress={onRetry}
          activeOpacity={0.8}
        >
          <Text style={styles.retryText}>{retryLabel ?? t("errorState.tryAgain")}</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingTop: 48,
    paddingHorizontal: 24,
    alignItems: "center",
    gap: 16,
  },
  compact: {
    paddingTop: 8,
    paddingHorizontal: 0,
    gap: 12,
  },
  message: {
    fontSize: 14,
    color: colors.danger,
    textAlign: "center",
    lineHeight: 22,
  },
  retryBtn: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: colors.accentSoft,
  },
  retryText: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.accent,
  },
});
