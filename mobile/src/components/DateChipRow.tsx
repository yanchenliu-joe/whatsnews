import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useTranslation } from "react-i18next";
import { colors, radii } from "../theme";
import type { HistoryDateEntry } from "../types";
import { formatDateShort } from "../utils/formatDateShort";

type Props = {
  dates: HistoryDateEntry[];
  selectedDate: string | null;
  onSelectDate: (date: string) => void;
};

export default function DateChipRow({ dates, selectedDate, onSelectDate }: Props) {
  const { t } = useTranslation();
  const years = dates.map((d) => d.date.slice(0, 4));
  const showYear = years.length > 0 && new Set(years).size > 1;

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{t("dateChipRow.selectDate")}</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.row}
      >
        {dates.map((entry) => {
          const selected = entry.date === selectedDate;
          return (
            <TouchableOpacity
              key={entry.date}
              onPress={() => onSelectDate(entry.date)}
              activeOpacity={0.7}
              style={[styles.chip, selected && styles.chipSelected]}
              accessibilityRole="button"
              accessibilityLabel={t("dateChipRow.briefingDate", {
                date: formatDateShort(entry.date, showYear),
              })}
              accessibilityState={{ selected }}
            >
              <Text
                style={[styles.chipText, selected && styles.chipTextSelected]}
                numberOfLines={1}
              >
                {formatDateShort(entry.date, showYear)}
              </Text>
              {entry.topics_available != null ? (
                <Text
                  style={[styles.chipMeta, selected && styles.chipMetaSelected]}
                  numberOfLines={1}
                >
                  {t("dateChipRow.topicsCount", { count: entry.topics_available })}
                </Text>
              ) : entry.article_count != null ? (
                <Text
                  style={[styles.chipMeta, selected && styles.chipMetaSelected]}
                  numberOfLines={1}
                >
                  {t("dateChipRow.storiesCount", { count: entry.article_count })}
                </Text>
              ) : null}
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: 20,
  },
  label: {
    fontSize: 10,
    fontWeight: "800",
    color: colors.muted,
    letterSpacing: 1.5,
    textTransform: "uppercase",
    marginBottom: 10,
  },
  row: {
    gap: 8,
    paddingRight: 4,
  },
  chip: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: radii.pill,
    backgroundColor: colors.surfaceMuted,
  },
  chipSelected: {
    backgroundColor: colors.ink,
  },
  chipText: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.muted,
  },
  chipTextSelected: {
    color: colors.white,
  },
  chipMeta: {
    fontSize: 10,
    fontWeight: "500",
    color: colors.muted,
    marginTop: 1,
  },
  chipMetaSelected: {
    color: colors.surfaceMuted,
  },
});
