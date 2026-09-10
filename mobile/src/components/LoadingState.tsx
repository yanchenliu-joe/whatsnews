import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { colors } from "../theme";

type Props = {
  message: string;
  compact?: boolean;
};

export default function LoadingState({ message, compact = false }: Props) {
  return (
    <View style={[styles.container, compact && styles.compact]}>
      <ActivityIndicator size="small" color={colors.accent} />
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingTop: 48,
    paddingHorizontal: 24,
    alignItems: "center",
    gap: 14,
  },
  compact: {
    paddingTop: 12,
    paddingHorizontal: 0,
    gap: 10,
  },
  message: {
    fontSize: 14,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 20,
  },
});
