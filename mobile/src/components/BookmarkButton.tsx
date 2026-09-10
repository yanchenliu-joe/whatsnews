import { StyleSheet, View, ViewStyle } from "react-native";
import { colors } from "../theme";

type Props = {
  filled?: boolean;
  style?: ViewStyle;
};

export default function BookmarkButton({ filled = false, style }: Props) {
  return (
    <View
      style={[
        styles.bookmarkIcon,
        filled && styles.bookmarkIconFilled,
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  bookmarkIcon: {
    width: 12,
    height: 16,
    borderWidth: 1.5,
    borderColor: colors.bookmarkBorder,
    borderTopLeftRadius: 2,
    borderTopRightRadius: 2,
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
  },
  bookmarkIconFilled: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
});
