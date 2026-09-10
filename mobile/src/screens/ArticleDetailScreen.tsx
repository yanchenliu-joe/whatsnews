import {
  ActivityIndicator,
  Alert,
  Platform,
  ScrollView,
  Share,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Image } from "expo-image";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { WebView } from "react-native-webview";
import * as WebBrowser from "expo-web-browser";
import * as Haptics from "expo-haptics";
import * as ExpoSharing from "expo-sharing";
import * as Print from "expo-print";
import { imageUrlToBase64 } from "../utils/pdfImageHelper";
import { captureRef } from "react-native-view-shot";
import { useEffect, useRef, useState } from "react";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useTranslation } from "react-i18next";
import ShareCard from "../components/ShareCard";
import RelatedArticlesSection from "../components/RelatedArticlesSection";
import ArticleToolsSheet from "../components/ArticleToolsSheet";
import AnchoredMenu from "../components/AnchoredMenu";
import FullTextNoticeModal from "../components/FullTextNoticeModal";
import { FULL_TEXT_NOTICE_SEEN_KEY } from "../config";
import { useSavedArticles } from "../hooks/useSavedArticles";
import { useOnDeviceTranslation } from "../hooks/useOnDeviceTranslation";
import { useReadingProgress } from "../context/ReadingProgressContext";
import { useAchievements } from "../context/AchievementsContext";
import { useReadingSettings } from "../context/ReadingSettingsContext";
import type { RootStackParamList } from "../navigation/types";
import { scheduleArticleReminder } from "../services/localNotifications";
import { trackEvent } from "../services/analytics";
import { colors, radii, spacing } from "../theme";
import { normalizeNullableString, normalizeString } from "../utils/dataContracts";
import { formatTimeAgo } from "../utils/formatTimeAgo";
import { getHeadlineFontFamily } from "../utils/headlineFont";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";
import { estimateReadingTime, formatReadingTime } from "../utils/readingTime";
import { backArrow, isRTL } from "../utils/rtl";

type Props = NativeStackScreenProps<RootStackParamList, "ArticleDetail">;
type ArticleTab = "summary" | "wim";
type ViewMode = "read" | "web";

export default function ArticleDetailScreen({ route, navigation }: Props) {
  const { t } = useTranslation();
  const p = route.params;
  const title = normalizeString(p.title, "Untitled");
  const summary = normalizeString(p.summary, "");
  // Full-text scraping was dropped 2026-07-11 — Read mode shows the
  // summary only now (p.bodyText is still passed through by callers,
  // just unused here). See FullTextNoticeModal + the in-tab hint line
  // below for how users are pointed to Web Mode / "Open in Browser" for
  // the full article.
  const articleBody = summary;
  const source = normalizeString(p.source, "Unknown");
  const url = normalizeString(p.url, "");
  const topic = normalizeString(p.topic, "");
  const publishedAt = normalizeNullableString(p.publishedAt);
  const whyItMatters = normalizeString(p.whyItMatters, "");
  const imageUrl = normalizeNullableString(p.imageUrl);

  const { savedUrls, toggleSaved } = useSavedArticles();
  const { markRead } = useReadingProgress();
  const { recordArticleRead, recordShare } = useAchievements();
  const { fontScale } = useReadingSettings();
  const headlineFontFamily = getHeadlineFontFamily("bold");
  const isSaved = Boolean(url && savedUrls.has(url));
  const timeLabel = formatTimeAgo(publishedAt);
  const readMins = estimateReadingTime(articleBody, whyItMatters);
  const readLabel = formatReadingTime(readMins);

  const shareCardRef = useRef<View>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [activeTab, setActiveTab] = useState<ArticleTab | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("read");
  const [showFullTextNotice, setShowFullTextNotice] = useState(false);

  const hasSummary = Boolean(summary);
  const hasWim = Boolean(whyItMatters);

  // On-device translation (2026-07-13) — see useOnDeviceTranslation.ts.
  // No-ops (returns the English original) when the UI language is
  // English, or when translation isn't available on this device/OS
  // version. `share`/`saveAsPdf`/`toggleSaved` deliberately keep using the
  // original English `summary`/`whyItMatters` variables below, matching
  // this screen's existing English-only export scope.
  const { fields: translatedFields, isTranslated, showingOriginal, toggleShowOriginal } =
    useOnDeviceTranslation({ summary, whyItMatters });
  const displaySummary = translatedFields.summary || summary;
  const displayWhyItMatters = translatedFields.whyItMatters || whyItMatters;

  useEffect(() => {
    if (url) markRead(url);
    // Additive to markRead — feeds the topic-coverage/volume/photo/time-of-day
    // badges (see AchievementsContext.tsx). Kept as a separate call rather
    // than extending markRead's signature, to avoid touching that already-
    // stable context at all for this feature.
    recordArticleRead(topic || null, Boolean(imageUrl));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // One-time (ever, not per-article) explainer — first article open only.
  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(FULL_TEXT_NOTICE_SEEN_KEY).then((seen) => {
      if (cancelled || seen) return;
      setShowFullTextNotice(true);
      void AsyncStorage.setItem(FULL_TEXT_NOTICE_SEEN_KEY, "true");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSavePDF() {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    trackEvent("article_saved_pdf", { topic_name: topic, metadata_text: title });
    recordShare();

    const topicDisplay = topic ? getTopicDisplayName(topic).toUpperCase() : "";
    const bodyContent = articleBody || summary;
    // PDF export HTML is a self-contained document, not a live-rendered
    // screen — deliberately left English-only for now (secondary/occasional
    // export path, not the primary reading surface this pass focused on).
    const wimSection = whyItMatters
      ? `<div class="wim-block">
           <div class="wim-label">WHY IT MATTERS</div>
           <p class="wim-text">${whyItMatters}</p>
         </div>`
      : "";
    const imgSrc = imageUrl ? ((await imageUrlToBase64(imageUrl)) ?? imageUrl) : null;
    const imageSection = imgSrc ? `<img class="hero" src="${imgSrc}" />` : "";
    const metaParts = [source, timeLabel, readLabel].filter(Boolean).join(" · ");

    const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    background: #F9F9F7;
    color: #111;
    padding: 48px 44px;
    max-width: 680px;
    margin: 0 auto;
  }
  .brand {
    font-size: 11px; font-weight: 700; letter-spacing: 2px;
    color: #8A8A8A; text-transform: uppercase; margin-bottom: 32px;
  }
  .topic {
    font-size: 10px; font-weight: 700; letter-spacing: 1.5px;
    color: #111; text-transform: uppercase; margin-bottom: 12px;
  }
  h1 {
    font-size: 26px; font-weight: 800; line-height: 1.3;
    letter-spacing: -0.4px; color: #111; margin-bottom: 16px;
  }
  .hero {
    width: 100%; max-height: 340px; object-fit: cover;
    border-radius: 10px; margin-bottom: 14px;
  }
  .meta {
    font-size: 11px; font-weight: 600; color: #8A8A8A;
    text-transform: uppercase; letter-spacing: 0.3px; margin-bottom: 24px;
  }
  hr { border: none; border-top: 1px solid #E4E4E2; margin-bottom: 24px; }
  .body {
    font-size: 15px; line-height: 1.75; color: #3D3D3D; margin-bottom: 32px;
  }
  .wim-block {
    background: #F4F4F2; border-radius: 10px;
    padding: 18px 20px; margin-top: 8px;
  }
  .wim-label {
    font-size: 10px; font-weight: 700; letter-spacing: 1px;
    color: #8A8A8A; text-transform: uppercase; margin-bottom: 10px;
  }
  .wim-text { font-size: 14px; line-height: 1.7; color: #2E2E2E; }
  .footer {
    margin-top: 48px; padding-top: 18px; border-top: 1px solid #E4E4E2;
    font-size: 10px; color: #ABABAB; letter-spacing: 0.5px;
  }
</style>
</head>
<body>
  <div class="brand">WhatsNews</div>
  ${topicDisplay ? `<div class="topic">${topicDisplay}</div>` : ""}
  <h1>${title}</h1>
  ${imageSection}
  <div class="meta">${metaParts}</div>
  <hr />
  <div class="body">${bodyContent.replace(/\n/g, "<br/>")}</div>
  ${wimSection}
  <div class="footer">Saved from WhatsNews · ${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}</div>
</body>
</html>`;

    try {
      const { uri } = await Print.printToFileAsync({ html, base64: false });
      await ExpoSharing.shareAsync(uri, {
        mimeType: "application/pdf",
        dialogTitle: title,
        UTI: "com.adobe.pdf",
      });
    } catch {
      // user cancelled or sharing failed — no error UI needed
    }
  }

  function handleOpenInBrowser() {
    if (!url) return;
    void WebBrowser.openBrowserAsync(url, {
      presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET,
      controlsColor: "#000000",
    });
    trackEvent("article_opened", { topic_name: topic, metadata_text: title });
  }

  function handleToggleSave() {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    toggleSaved(url, {
      title, source, topic,
      summary: summary || undefined,
      why_it_matters: whyItMatters || undefined,
      image_url: imageUrl ?? undefined,
    });
  }

  async function handleShare() {
    trackEvent("article_shared", { topic_name: topic, metadata_text: title });
    recordShare();
    const canShare = await ExpoSharing.isAvailableAsync();
    if (canShare && shareCardRef.current) {
      try {
        setIsSharing(true);
        await new Promise((r) => setTimeout(r, 50));
        const uri = await captureRef(shareCardRef, { format: "png", quality: 1, result: "tmpfile" });
        setIsSharing(false);
        await ExpoSharing.shareAsync(uri, { mimeType: "image/png", dialogTitle: title });
        return;
      } catch {
        setIsSharing(false);
      }
    }
    const body = whyItMatters ? `WHY IT MATTERS\n${whyItMatters}` : summary || "";
    const shareText = [title, body, `— ${source} via WhatsNews`].filter(Boolean).join("\n\n");
    void Share.share(
      Platform.OS === "ios"
        ? { message: shareText, url: url || undefined }
        : { message: shareText, title },
    );
  }

  function handleTabPress(tab: ArticleTab) {
    setActiveTab((prev) => (prev === tab ? null : tab));
  }

  function handleToggleViewMode() {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setViewMode((prev) => (prev === "read" ? "web" : "read"));
  }

  async function handleRemindMeLater(delaySeconds: number) {
    const scheduled = await scheduleArticleReminder({ title, url, topic }, delaySeconds);
    if (scheduled) {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      Alert.alert(t("articleDetail.reminderSetTitle"), t("articleDetail.reminderSetMessage"));
    } else {
      Alert.alert(
        t("articleDetail.notificationsDisabledTitle"),
        t("articleDetail.notificationsDisabledMessage"),
      );
    }
  }

  const moreMenuItems = [
    { key: "open-browser", label: t("articleDetail.openInBrowser"), onSelect: handleOpenInBrowser },
    { key: "share", label: t("articleDetail.share"), onSelect: () => void handleShare() },
    { key: "save-pdf", label: t("articleDetail.saveAsPdf"), onSelect: () => void handleSavePDF() },
    {
      key: "toggle-save",
      label: isSaved ? t("articleDetail.unsaveArticle") : t("articleDetail.saveArticle"),
      onSelect: handleToggleSave,
      destructive: isSaved,
    },
  ];

  return (
    <SafeAreaView style={s.root}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      {/* Off-screen share card */}
      <View
        ref={shareCardRef}
        style={[s.offscreen, isSharing && s.offscreenVisible]}
        collapsable={false}
      >
        <ShareCard title={title} summary={summary} source={source} topic={topic} whyItMatters={whyItMatters || undefined} />
      </View>

      {/* Top bar */}
      <View style={s.topBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} activeOpacity={0.7} style={s.backBtn} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Text style={s.backText}>{backArrow()} {t("common.back")}</Text>
        </TouchableOpacity>
        <AnchoredMenu items={moreMenuItems} triggerStyle={s.moreBtn}>
          <TouchableOpacity activeOpacity={0.7} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
            <Text style={s.moreText}>•••</Text>
          </TouchableOpacity>
        </AnchoredMenu>
      </View>

      {viewMode === "web" && url ? (
        <WebView
          source={{ uri: url }}
          style={s.webview}
          startInLoadingState
          renderLoading={() => (
            <View style={s.webviewLoading}>
              <ActivityIndicator color={colors.ink} />
            </View>
          )}
        />
      ) : (
        <ScrollView style={s.scroll} contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>

          {/* Topic + Title */}
          {topic ? <Text style={s.topicLabel}>{getTopicDisplayName(topic).toUpperCase()}</Text> : null}
          <Text
            style={[
              s.title,
              { fontFamily: headlineFontFamily, fontSize: 24 * fontScale, lineHeight: 32 * fontScale },
            ]}
          >
            {title}
          </Text>

          {/* Hero image */}
          {imageUrl ? (
            <Image
              source={{ uri: imageUrl }}
              style={s.heroImage}
              contentFit="cover"
              cachePolicy="memory-disk"
              transition={150}
            />
          ) : null}

          {/* Summary | Why It Matters tabs — always shown below image */}
          <View style={s.tabCard}>
            <View style={[s.tabRow, activeTab !== null && s.tabRowOpen]}>
              <TouchableOpacity style={s.tab} onPress={() => handleTabPress("summary")} activeOpacity={0.75}>
                <Text style={[s.tabText, activeTab === "summary" && s.tabTextActive]}>{t("articleDetail.summary")}</Text>
                <Text style={activeTab === "summary" ? s.chevron : s.chevronMuted}>
                  {activeTab === "summary" ? "▲" : "▼"}
                </Text>
              </TouchableOpacity>

              <View style={s.tabDivider} />

              <TouchableOpacity style={s.tab} onPress={() => handleTabPress("wim")} activeOpacity={0.75}>
                <Text style={[s.tabText, activeTab === "wim" && s.tabTextActive]}>{t("articleDetail.whyItMatters")}</Text>
                <Text style={activeTab === "wim" ? s.chevron : s.chevronMuted}>
                  {activeTab === "wim" ? "▲" : "▼"}
                </Text>
              </TouchableOpacity>
            </View>

            {activeTab === "summary" ? (
              <View style={s.tabContent}>
                {isTranslated ? (
                  <TouchableOpacity onPress={toggleShowOriginal} activeOpacity={0.7} style={s.translationPill}>
                    <Text style={s.translationPillText}>
                      {showingOriginal
                        ? t("translation.viewTranslation")
                        : t("translation.translatedFromEnglish")}
                    </Text>
                  </TouchableOpacity>
                ) : null}
                <Text style={[s.tabBody, { fontSize: 15 * fontScale, lineHeight: 24 * fontScale }]}>
                  {hasSummary ? displaySummary : t("articleDetail.noSummaryAvailable")}
                </Text>
              </View>
            ) : null}

            {activeTab === "wim" ? (
              <View style={s.tabContent}>
                <Text style={s.wimLabel}>{t("articleDetail.whyItMattersLabel")}</Text>
                {isTranslated ? (
                  <TouchableOpacity onPress={toggleShowOriginal} activeOpacity={0.7} style={s.translationPill}>
                    <Text style={s.translationPillText}>
                      {showingOriginal
                        ? t("translation.viewTranslation")
                        : t("translation.translatedFromEnglish")}
                    </Text>
                  </TouchableOpacity>
                ) : null}
                <Text style={[s.tabBody, { fontSize: 15 * fontScale, lineHeight: 24 * fontScale }]}>
                  {hasWim ? displayWhyItMatters : t("articleDetail.noAnalysisAvailable")}
                </Text>
              </View>
            ) : null}
          </View>

          {/* Meta */}
          <View style={s.metaRow}>
            <Text style={s.metaSource} numberOfLines={1}>{source}</Text>
            {timeLabel ? (<><Text style={s.metaDot}>·</Text><Text style={s.metaItem}>{timeLabel}</Text></>) : null}
            {readLabel ? (<><Text style={s.metaDot}>·</Text><Text style={s.metaItem}>{readLabel}</Text></>) : null}
          </View>

          <View style={s.divider} />

          {/* Main reading content — summary only (full-text scraping was
              dropped 2026-07-11); hint line points to Web Mode / the "•••"
              menu for the original article. */}
          {articleBody ? (
            <>
              {isTranslated ? (
                <TouchableOpacity onPress={toggleShowOriginal} activeOpacity={0.7} style={s.translationPill}>
                  <Text style={s.translationPillText}>
                    {showingOriginal
                      ? t("translation.viewTranslation")
                      : t("translation.translatedFromEnglish")}
                  </Text>
                </TouchableOpacity>
              ) : null}
              <Text style={[s.body, { fontSize: 16 * fontScale, lineHeight: 27 * fontScale }]}>
                {displaySummary || articleBody}
              </Text>
            </>
          ) : null}
          {articleBody ? (
            <Text style={s.summaryHint}>{t("articleDetail.summaryHintLine")}</Text>
          ) : null}

          <RelatedArticlesSection title={title} topic={topic} excludeUrl={url} />

          <View style={s.fabSpacer} />
        </ScrollView>
      )}

      {/* Fixed FAB row: read/web toggle (Ask AI removed — no OpenAI key) */}
      {url ? (
        <View style={[s.rightFabRow, isRTL() && s.rightFabRowRTL]}>
          <TouchableOpacity
            style={[s.webToggleFab, viewMode === "web" && s.webToggleFabActive]}
            onPress={handleToggleViewMode}
            activeOpacity={0.85}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Text style={[s.webToggleFabText, viewMode === "web" && s.webToggleFabTextActive]}>
              {viewMode === "web" ? "📄" : "🌐"}
            </Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {/* Fixed article tools FAB — Font Size / Remind Me Later (Phase 32) —
          native menu (zeego); positioned bottom-left via its own wrapper. */}
      <View style={[s.toolsFabWrap, isRTL() && s.toolsFabWrapRTL]}>
        <ArticleToolsSheet onRemindMeLater={(seconds) => void handleRemindMeLater(seconds)} />
      </View>

      <FullTextNoticeModal
        visible={showFullTextNotice}
        onDismiss={() => setShowFullTextNotice(false)}
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  offscreen: { position: "absolute", top: -2000, left: 0, opacity: 0 },
  offscreenVisible: { opacity: 1 },

  topBar: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: spacing.screenPaddingH, paddingTop: 8, paddingBottom: 8,
  },
  backBtn: { paddingVertical: 4 },
  backText: { fontSize: 15, fontWeight: "500", color: colors.accent },
  moreBtn: { paddingVertical: 4, paddingHorizontal: 4 },
  moreText: { fontSize: 18, fontWeight: "700", color: colors.ink, letterSpacing: 1 },

  scroll: { flex: 1 },
  content: { paddingHorizontal: spacing.screenPaddingH, paddingTop: 4, paddingBottom: 40 },

  topicLabel: {
    fontSize: 10, fontWeight: "700", color: colors.accent,
    letterSpacing: 1.2, marginBottom: 10,
  },
  title: {
    fontSize: 24, fontWeight: "800", color: colors.ink,
    lineHeight: 32, letterSpacing: -0.1, marginBottom: 16,
  },
  heroImage: {
    width: "100%", height: 200, borderRadius: 10,
    marginBottom: 12, backgroundColor: colors.surfaceMuted,
  },

  // Collapsible tab card (matches EditorialTabsCard)
  tabCard: {
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
    marginBottom: 14,
  },
  tabRow: { flexDirection: "row", alignItems: "center" },
  tabRowOpen: { borderBottomWidth: 1, borderBottomColor: colors.border },
  tab: {
    flex: 1, flexDirection: "row", alignItems: "center",
    justifyContent: "center", gap: 5, paddingVertical: 12,
  },
  tabDivider: { width: 1, height: 16, backgroundColor: colors.border },
  tabText: { fontSize: 12, fontWeight: "600", color: colors.muted },
  tabTextActive: { color: colors.ink, fontWeight: "700" },
  chevron: { fontSize: 7, color: colors.ink, marginTop: 1 },
  chevronMuted: { fontSize: 7, color: colors.faint, marginTop: 1 },
  tabContent: { padding: 14 },
  wimLabel: {
    fontSize: 10, fontWeight: "700", color: colors.metaText,
    letterSpacing: 1, marginBottom: 8,
  },
  tabBody: { fontSize: 15, color: colors.summary, lineHeight: 24 },
  translationPill: {
    alignSelf: "flex-start",
    backgroundColor: colors.surfaceMuted,
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginBottom: 10,
  },
  translationPillText: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.accent,
  },

  // Meta row
  metaRow: {
    flexDirection: "row", alignItems: "center",
    flexWrap: "wrap", gap: 5, marginBottom: 14,
  },
  metaSource: {
    fontSize: 11, fontWeight: "700", color: colors.metaText,
    letterSpacing: 0.3, textTransform: "uppercase",
  },
  metaDot: { fontSize: 11, color: colors.faint },
  metaItem: { fontSize: 11, fontWeight: "500", color: colors.metaText },
  divider: { height: 1, backgroundColor: colors.border, marginBottom: 20 },

  // Article body — summary text, styled larger than the tab card's copy
  // since this is the primary reading pane.
  body: { fontSize: 16, color: colors.summary, lineHeight: 27 },
  // Small, deliberately understated — discoverable if you're reading the
  // summary, not a banner shouting for attention. See FullTextNoticeModal
  // for the one-time (first article ever) version of the same message.
  summaryHint: {
    fontSize: 11,
    lineHeight: 16,
    color: colors.faint,
    fontStyle: "italic",
    marginTop: 10,
  },

  fabSpacer: { height: 80 },
  rightFabRow: {
    position: "absolute", bottom: 32, right: 20,
    flexDirection: "row", alignItems: "center", gap: 10,
  },
  rightFabRowRTL: { right: undefined, left: 20 },
  fab: {
    backgroundColor: colors.ink, borderRadius: 28,
    paddingVertical: 14, paddingHorizontal: 22,
    shadowColor: "#000", shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18, shadowRadius: 8, elevation: 6,
  },
  fabText: { fontSize: 15, fontWeight: "700", color: colors.white, letterSpacing: 0.2 },
  webToggleFab: {
    width: 48, height: 48, borderRadius: 24,
    backgroundColor: colors.cardBg, alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: colors.border,
    shadowColor: "#000", shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12, shadowRadius: 8, elevation: 4,
  },
  webToggleFabActive: { backgroundColor: colors.ink, borderColor: colors.ink },
  webToggleFabText: { fontSize: 18 },
  webToggleFabTextActive: { opacity: 0.9 },
  toolsFabWrap: { position: "absolute", bottom: 32, left: 20 },
  toolsFabWrapRTL: { left: undefined, right: 20 },

  webview: { flex: 1 },
  webviewLoading: {
    flex: 1, alignItems: "center", justifyContent: "center",
    backgroundColor: colors.bg,
  },
});
