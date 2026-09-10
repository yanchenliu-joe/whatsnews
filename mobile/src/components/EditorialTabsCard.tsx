import { useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useTranslation } from "react-i18next";
import { colors } from "../theme";
import { useAchievements } from "../context/AchievementsContext";
import type { Perspective, WatchNext } from "../types";

type Tab = "perspective" | "watchnext";

type Props = {
  perspective: Perspective | null;
  watchNext: WatchNext | null;
};

export default function EditorialTabsCard({ perspective, watchNext }: Props) {
  const { t } = useTranslation();
  const { recordWatchNextView } = useAchievements();
  const hasPerspective = Boolean(perspective?.headline || perspective?.perspective);
  const hasWatchNext = Boolean(watchNext && (watchNext.items ?? []).length > 0);

  // null = collapsed, tab name = expanded
  const [activeTab, setActiveTab] = useState<Tab | null>(null);

  if (!hasPerspective && !hasWatchNext) return null;

  function handleTabPress(tab: Tab) {
    setActiveTab((prev) => {
      const next = prev === tab ? null : tab;
      if (tab === "watchnext" && next === "watchnext") recordWatchNextView();
      return next;
    });
  }

  const showContent = activeTab !== null;

  return (
    <View style={s.card}>
      {/* Tab row */}
      <View style={[s.tabRow, showContent && s.tabRowOpen]}>
        <TouchableOpacity
          style={[s.tab, activeTab === "perspective" && s.tabActive]}
          onPress={() => handleTabPress("perspective")}
          activeOpacity={0.75}
          disabled={!hasPerspective}
        >
          <Text style={[s.tabText, activeTab === "perspective" && s.tabTextActive]}>
            {t("editorialTabs.editorsTake")}
          </Text>
          {activeTab === "perspective" ? (
            <Text style={s.chevron}>▲</Text>
          ) : (
            <Text style={s.chevronMuted}>▼</Text>
          )}
        </TouchableOpacity>

        <View style={s.tabDivider} />

        <TouchableOpacity
          style={[s.tab, activeTab === "watchnext" && s.tabActive]}
          onPress={() => handleTabPress("watchnext")}
          activeOpacity={0.75}
          disabled={!hasWatchNext}
        >
          <Text style={[s.tabText, activeTab === "watchnext" && s.tabTextActive]}>
            {t("editorialTabs.watchNext")}
          </Text>
          {activeTab === "watchnext" ? (
            <Text style={s.chevron}>▲</Text>
          ) : (
            <Text style={s.chevronMuted}>▼</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Content — only visible when a tab is active */}
      {activeTab === "perspective" && hasPerspective ? (
        <View style={s.content}>
          <PerspectiveContent perspective={perspective!} />
        </View>
      ) : null}
      {activeTab === "watchnext" && hasWatchNext ? (
        <View style={s.content}>
          <WatchNextContent watchNext={watchNext!} />
        </View>
      ) : null}
    </View>
  );
}

function PerspectiveContent({ perspective }: { perspective: Perspective }) {
  const { headline, perspective: body, themes } = perspective;

  return (
    <View>
      {headline ? <Text style={s.headline}>{headline}</Text> : null}
      {body ? <Text style={s.body}>{body}</Text> : null}
      {themes && themes.length > 0 ? (
        <View style={s.themes}>
          {themes.map((t) => (
            <View key={t} style={s.theme}>
              <Text style={s.themeText}>{t}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function WatchNextContent({ watchNext }: { watchNext: WatchNext }) {
  const items = (watchNext.items ?? []).slice(0, 5);

  return (
    <View>
      {items.map((item, i) => (
        <View key={i} style={[s.watchItem, i < items.length - 1 && s.watchItemBorder]}>
          <Text style={s.watchNum}>{i + 1}</Text>
          <View style={s.watchBody}>
            <Text style={s.watchText}>{item.text}</Text>
            {item.reason ? (
              <Text style={s.watchReason}>{item.reason}</Text>
            ) : null}
            {item.topics && item.topics.length > 0 ? (
              <Text style={s.watchTopics}>{item.topics.join(" · ")}</Text>
            ) : null}
          </View>
        </View>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  card: {
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 12,
    overflow: "hidden",
  },

  // Tabs
  tabRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  tabRowOpen: {
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tab: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 5,
    paddingVertical: 11,
  },
  tabActive: {},
  tabDivider: {
    width: 1,
    height: 16,
    backgroundColor: colors.border,
  },
  tabText: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.muted,
    letterSpacing: 0.1,
  },
  tabTextActive: {
    color: colors.ink,
    fontWeight: "700",
  },
  chevron: {
    fontSize: 7,
    color: colors.ink,
    marginTop: 1,
  },
  chevronMuted: {
    fontSize: 7,
    color: colors.faint,
    marginTop: 1,
  },

  // Content area
  content: {
    padding: 14,
  },

  // Editor's Take
  headline: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.ink,
    lineHeight: 21,
    marginBottom: 8,
  },
  body: {
    fontSize: 14,
    color: colors.summary,
    lineHeight: 21,
  },
  themes: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 10,
  },
  theme: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    backgroundColor: colors.surfaceMuted,
  },
  themeText: {
    fontSize: 11,
    fontWeight: "500",
    color: colors.muted,
  },

  // Watch Next
  watchItem: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 11,
  },
  watchItemBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  watchNum: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.faint,
    width: 14,
    marginTop: 1,
  },
  watchBody: {
    flex: 1,
    gap: 3,
  },
  watchText: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.ink,
    lineHeight: 20,
  },
  watchReason: {
    fontSize: 13,
    color: colors.summary,
    lineHeight: 18,
  },
  watchTopics: {
    fontSize: 11,
    color: colors.metaText,
    marginTop: 2,
  },
});
