import { StyleSheet, Text, View } from "react-native";
import { colors } from "../theme";

type Props = {
  label: string;
};

export default function SectionHeader({ label }: Props) {
  return (
    <View style={styles.sectionHeader}>
      <Text style={styles.sectionLabel}>{label}</Text>
      <View style={styles.sectionDivider} />
    </View>
  );
}

const styles = StyleSheet.create({
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 10,
    fontWeight: "800",
    color: colors.muted,
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  sectionDivider: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
});
