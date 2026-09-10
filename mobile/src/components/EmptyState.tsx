import { StyleSheet, Text, View } from "react-native";
import { colors } from "../theme";

type Props = {
  title: string;
  message?: string;
};

export default function EmptyState({ title, message }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      {message ? <Text style={styles.message}>{message}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingTop: 40,
    paddingHorizontal: 24,
    alignItems: "center",
    gap: 10,
  },
  title: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.ink,
    textAlign: "center",
    lineHeight: 22,
  },
  message: {
    fontSize: 13,
    color: colors.muted,
    textAlign: "center",
    lineHeight: 20,
    maxWidth: 300,
  },
});
