import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Modal,
  Share,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import * as Print from "expo-print";
import * as ExpoSharing from "expo-sharing";
import * as Haptics from "expo-haptics";
import { useTranslation } from "react-i18next";
import { prefetchImagesToBase64 } from "../utils/pdfImageHelper";
import { colors, radii } from "../theme";
import type { Narrative, NewsItem } from "../types";
import { SPEECH_RATE_OPTIONS, useSpeechPlayback } from "../hooks/useSpeechPlayback";
import { useOnDeviceTranslation } from "../hooks/useOnDeviceTranslation";
import { speechLocaleFor } from "../utils/onDeviceTranslation";
import type { SupportedLanguage } from "../i18n";
import { trackEvent } from "../services/analytics";
import { formatDate } from "../utils/formatDate";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";
import { formatDuration } from "../utils/formatDuration";
import { getHeadlineFontFamily } from "../utils/headlineFont";
import PlayPauseIcon from "./PlayPauseIcon";
import ShareIcon from "./ShareIcon";
import AnchoredMenu from "./AnchoredMenu";
import { useAchievements } from "../context/AchievementsContext";
import { isNarrativeScriptReady, type VoiceCardState } from "../utils/narrativeUtils";

// Decorative waveform silhouette drawn over the hero image (2026-07-11
// design pass, animated 2026-07-11 same day) — on-device TTS has no real
// amplitude/volume data to visualize (no audio file exists at all; the OS
// speech engine synthesizes and plays it internally, expo-speech exposes no
// buffer or volume meter), so the per-bar heights below are still a fixed
// pattern, not a reflection of the actual narrative script's audio. What IS
// real: each bar now pulses via useWaveformPulse while isPlaying is true
// (frozen/reset the moment playback pauses or stops), so it reads as a live
// audio-reactive visualizer rather than a static decoration, even though the
// pulse motion itself is randomized rather than sampled from real audio.
const WAVEFORM_HEIGHTS = [
  8, 14, 10, 18, 22, 16, 24, 12, 20, 26, 18, 10, 16, 22, 28, 20, 14, 24, 18, 12,
  20, 26, 22, 16, 10, 18, 24, 20, 14, 22, 28, 18, 12, 20, 16, 24, 10, 18, 22, 14,
  20, 26, 16, 12, 18, 24, 20, 14,
];

/**
 * Drives each waveform bar's scaleY between a randomized low point and its
 * resting height, looped while `active` — staggered per-bar start/duration
 * so bars don't pulse in lockstep, which is what actually sells the "live"
 * look. All native-driver transforms, so this costs nothing on the JS
 * thread once started. Stops and snaps back to resting scale the instant
 * `active` goes false (pause/stop), rather than finishing its current cycle.
 */
function useWaveformPulse(barCount: number, active: boolean): Animated.Value[] {
  const animsRef = useRef<Animated.Value[]>(
    Array.from({ length: barCount }, () => new Animated.Value(1)),
  );

  useEffect(() => {
    const anims = animsRef.current;

    if (!active) {
      anims.forEach((anim) => {
        anim.stopAnimation();
        Animated.timing(anim, { toValue: 1, duration: 180, useNativeDriver: true }).start();
      });
      return;
    }

    const loops = anims.map((anim) => {
      const duration = 260 + Math.random() * 340;
      const minScale = 0.3 + Math.random() * 0.35;
      return Animated.loop(
        Animated.sequence([
          Animated.timing(anim, { toValue: minScale, duration, useNativeDriver: true }),
          Animated.timing(anim, { toValue: 1, duration, useNativeDriver: true }),
        ]),
      );
    });
    const timers = loops.map((loop, i) => setTimeout(() => loop.start(), i * 25));

    return () => {
      timers.forEach(clearTimeout);
      loops.forEach((loop) => loop.stop());
    };
  }, [active]);

  return animsRef.current;
}

type Variant = "today" | "history";

type Props = {
  variant?: Variant;
  narrative: Narrative | null;
  loadState: VoiceCardState;
  error: string | null;
  onRetry?: () => void;
  articles?: NewsItem[];
};

function StatusBadge({ label, tone }: { label: string; tone: "ready" | "pending" | "muted" }) {
  const toneStyle =
    tone === "ready"
      ? styles.badgeReady
      : tone === "pending"
        ? styles.badgePending
        : styles.badgeMuted;

  return (
    <View style={[styles.badge, toneStyle]}>
      <Text style={[styles.badgeText, tone === "ready" && styles.badgeTextReady]}>
        {label}
      </Text>
    </View>
  );
}

function ControlButton({
  label,
  onPress,
  disabled,
  primary,
}: {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  primary?: boolean;
}) {
  return (
    <TouchableOpacity
      style={[
        styles.controlButton,
        primary && styles.controlButtonPrimary,
        disabled && styles.controlButtonDisabled,
        primary && disabled && styles.controlButtonPrimaryDisabled,
      ]}
      onPress={onPress ?? (() => {})}
      disabled={disabled}
      activeOpacity={0.8}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Text
        style={[
          styles.controlButtonText,
          primary && styles.controlButtonTextPrimary,
          disabled && styles.controlButtonTextDisabled,
        ]}
      >
        {label}
      </Text>
    </TouchableOpacity>
  );
}

export default function VoiceBriefingCard({
  variant = "today",
  narrative,
  loadState,
  error,
  onRetry,
  articles = [],
}: Props) {
  const { t, i18n } = useTranslation();
  const { recordShare, recordAudioPlay } = useAchievements();
  const seenRef = useRef(false);
  const [isPdfLoading, setIsPdfLoading] = useState(false);
  const reportDate = narrative?.report_date;

  const scriptReady = isNarrativeScriptReady(narrative);
  const scriptText = narrative?.script_text ?? null;
  // Reuses the day's top story's own image — no per-narrative cover image
  // concept exists in the data model, and this needs zero backend changes
  // or new image sourcing (2026-07-11 design pass, confirmed with the user).
  // Used as a full-bleed hero for "today" and a small square thumbnail for
  // "history" (Phase 2) — same source, two different layouts.
  const heroImageUrl = articles[0]?.image_url ?? null;
  const headlineFontFamily = getHeadlineFontFamily("bold");

  // On-device translation (2026-07-13) — narrative script_text is always
  // authored in English; when the UI language isn't English, this
  // silently translates it and the TTS below reads the translated text in
  // a matching voice/locale. Falls back to the English original whenever
  // translation isn't available (Expo Go, iOS < 18, model unavailable).
  const { fields: scriptFields } = useOnDeviceTranslation(
    scriptReady && scriptText ? { script: scriptText } : { script: "" },
  );
  const spokenScriptText = scriptReady ? (scriptFields.script || scriptText) : null;
  const speechLanguage = speechLocaleFor(i18n.language as SupportedLanguage);

  const {
    isPlaying,
    isPaused,
    progressRatio,
    playbackRate,
    error: playbackError,
    canPlay,
    togglePlayPause,
    setRate,
  } = useSpeechPlayback({ text: spokenScriptText, language: speechLanguage });

  const waveformAnims = useWaveformPulse(WAVEFORM_HEIGHTS.length, isPlaying);

  function handleTogglePlayPause() {
    const startingFresh = !isPlaying && !isPaused;
    if (!isPlaying) recordAudioPlay();
    void togglePlayPause();
    const eventName = isPlaying
      ? "voice_paused"
      : variant === "history"
        ? "voice_history_play_started"
        : "voice_play_started";
    trackEvent(eventName, { metadata_text: reportDate });
    if (startingFresh && !canPlay) {
      trackEvent(
        variant === "history" ? "voice_history_play_failed" : "voice_play_failed",
        { metadata_text: reportDate },
      );
    }
  }

  async function handleShareText() {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    recordShare();
    const dateLabel = narrative?.report_date
      ? formatDate(narrative.report_date)
      : new Date().toLocaleDateString(i18n.language, { month: "long", day: "numeric", year: "numeric" });
    const lines = articles.slice(0, 5).map((a, i) => `${i + 1}. ${a.title} — ${a.source}`);
    const text = `WhatsNews · ${dateLabel}\n\n${lines.join("\n")}\n\n${t("voiceBriefing.sentFrom")}`;
    await Share.share({ message: text });
  }

  async function handleSavePDF() {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    recordShare();
    setIsPdfLoading(true);
    trackEvent("briefing_shared_pdf", {});
    const dateLabel = narrative?.report_date
      ? formatDate(narrative.report_date)
      : new Date().toLocaleDateString(i18n.language, { month: "long", day: "numeric", year: "numeric" });

    const imageMap = await prefetchImagesToBase64(articles.map((a) => a.image_url));

    // PDF export HTML is a self-contained document, not a live-rendered
    // screen — deliberately left English-only for now (secondary/occasional
    // export path), same deferral as ArticleDetailScreen's PDF export.
    const articleSections = articles.map((a) => {
      const topicTag = a.topic ? getTopicDisplayName(a.topic).toUpperCase() : "";
      const imgSrc = a.image_url ? (imageMap[a.image_url] ?? a.image_url) : null;
      const imageHtml = imgSrc
        ? `<img class="hero" src="${imgSrc}" />`
        : "";
      // Full-text scraping was dropped 2026-07-11 — exports now use the
      // summary only, same as ArticleDetailScreen's Read mode.
      const bodyText = (a.summary || "").replace(/\n/g, "<br/>");
      const wimHtml = a.why_it_matters
        ? `<div class="wim-block">
             <div class="wim-label">WHY IT MATTERS</div>
             <p class="wim-text">${a.why_it_matters}</p>
           </div>`
        : "";
      return `
        <div class="article">
          ${topicTag ? `<div class="topic">${topicTag}</div>` : ""}
          <h2>${a.title}</h2>
          ${imageHtml}
          <div class="meta">${[a.source].filter(Boolean).join(" · ")}</div>
          <div class="body">${bodyText}</div>
          ${wimHtml}
        </div>
        <hr class="divider" />`;
    }).join("");

    const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
    background: #F9F9F7; color: #111;
    padding: 48px 44px; max-width: 700px; margin: 0 auto;
  }
  .cover-brand { font-size:11px; font-weight:700; letter-spacing:2px; color:#8A8A8A; text-transform:uppercase; margin-bottom:6px; }
  .cover-date  { font-size:28px; font-weight:800; letter-spacing:-0.5px; color:#111; margin-bottom:6px; }
  .cover-sub   { font-size:13px; color:#8A8A8A; margin-bottom:40px; }
  .article { margin-bottom:36px; }
  .topic  { font-size:10px; font-weight:700; letter-spacing:1.5px; color:#111; text-transform:uppercase; margin-bottom:8px; }
  h2 { font-size:20px; font-weight:800; line-height:1.35; letter-spacing:-0.3px; color:#111; margin-bottom:12px; }
  .hero { width:100%; max-height:280px; object-fit:cover; border-radius:8px; margin-bottom:10px; }
  .meta { font-size:11px; font-weight:600; color:#8A8A8A; text-transform:uppercase; letter-spacing:0.3px; margin-bottom:16px; }
  .body { font-size:14px; line-height:1.75; color:#3D3D3D; margin-bottom:20px; }
  .wim-block { background:#F4F4F2; border-radius:8px; padding:14px 16px; }
  .wim-label { font-size:9px; font-weight:700; letter-spacing:1px; color:#8A8A8A; text-transform:uppercase; margin-bottom:8px; }
  .wim-text  { font-size:13px; line-height:1.7; color:#2E2E2E; }
  hr.divider { border:none; border-top:1px solid #E4E4E2; margin:0 0 36px; }
  .footer { font-size:10px; color:#ABABAB; letter-spacing:0.5px; margin-top:24px; }
</style>
</head>
<body>
  <div class="cover-brand">WhatsNews</div>
  <div class="cover-date">${variant === "today" ? "Today's Brief" : "Daily Brief"}</div>
  <div class="cover-sub">${dateLabel} · ${articles.length} ${articles.length === 1 ? "story" : "stories"}</div>
  ${articleSections}
  <div class="footer">Generated by WhatsNews · ${dateLabel}</div>
</body>
</html>`;

    try {
      const { uri } = await Print.printToFileAsync({ html, base64: false });
      await ExpoSharing.shareAsync(uri, {
        mimeType: "application/pdf",
        dialogTitle: `WhatsNews · ${dateLabel}`,
        UTI: "com.adobe.pdf",
      });
    } catch {
      // user cancelled
    } finally {
      setIsPdfLoading(false);
    }
  }

  useEffect(() => {
    if (seenRef.current) return;
    if (loadState === "loading" || loadState === "hidden") return;
    seenRef.current = true;
    const eventName =
      variant === "history" ? "voice_history_card_seen" : "voice_card_seen";
    trackEvent(eventName, { metadata_text: reportDate ?? loadState });
  }, [loadState, reportDate, variant]);

  if (loadState === "hidden") {
    return null;
  }

  if (variant === "history" && loadState === "loading") {
    return null;
  }

  if (loadState === "loading") {
    return (
      <View style={styles.card}>
        <View style={styles.row}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={styles.loadingText}>{t("voiceBriefing.loadingBrief")}</Text>
        </View>
      </View>
    );
  }

  if (loadState === "error") {
    if (variant === "history") return null;

    return (
      <View style={[styles.card, styles.cardMuted]}>
        <View style={styles.headerRow}>
          <Text style={styles.eyebrow}>{t("voiceBriefing.morningBrief")}</Text>
          <StatusBadge label={t("voiceBriefing.unavailable")} tone="muted" />
        </View>
        {onRetry ? (
          <TouchableOpacity style={styles.retryButton} onPress={onRetry}>
            <Text style={styles.retryLabel}>{t("common.retry")}</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    );
  }

  if (loadState === "unavailable") {
    if (variant === "history") {
      return (
        <View style={[styles.card, styles.cardMuted, styles.cardSubtle]}>
          <View style={styles.headerRow}>
            <View style={styles.headerLeft}>
              <Text style={styles.eyebrow}>{t("voiceBriefing.morningBrief")}</Text>
              {reportDate ? <Text style={styles.date}>{formatDate(reportDate)}</Text> : null}
            </View>
            <StatusBadge label={t("voiceBriefing.noRecording")} tone="muted" />
          </View>
        </View>
      );
    }

    return (
      <View style={[styles.card, styles.cardMuted]}>
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={styles.eyebrow}>{t("voiceBriefing.morningBrief")}</Text>
            {reportDate ? <Text style={styles.date}>{formatDate(reportDate)}</Text> : null}
          </View>
          <StatusBadge label={t("voiceBriefing.notReady")} tone="pending" />
        </View>
      </View>
    );
  }

  if (!scriptReady) {
    return (
      <View style={[styles.card, styles.cardMuted]}>
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={styles.eyebrow}>{t("voiceBriefing.morningBrief")}</Text>
            {reportDate ? <Text style={styles.date}>{formatDate(reportDate)}</Text> : null}
          </View>
          <StatusBadge label={t("voiceBriefing.generating")} tone="pending" />
        </View>
      </View>
    );
  }

  // No server-generated audio metadata under on-device TTS — estimate total
  // duration from the narrative's own estimate (still sent by the backend)
  // and derive elapsed time from the hook's char-index-based progressRatio.
  const estimatedDurationSeconds =
    narrative?.estimated_duration_seconds ?? narrative?.audio?.duration_seconds ?? null;
  const elapsedSeconds =
    estimatedDurationSeconds != null ? Math.round(progressRatio * estimatedDurationSeconds) : null;
  const elapsedLabel = elapsedSeconds != null ? (formatDuration(elapsedSeconds) ?? "0:00") : "0:00";
  const totalLabel = estimatedDurationSeconds != null ? formatDuration(estimatedDurationSeconds) : null;

  const playLabel = isPlaying ? t("voiceBriefing.pause") : t("voiceBriefing.play");
  const statusLabel = t("voiceBriefing.audioReady");
  const statusTone: "ready" | "pending" | "muted" = "ready";
  const playEnabled = canPlay && loadState === "ready";

  const shareMenuItems = [
    { key: "share", label: t("articleDetail.share"), onSelect: () => void handleShareText() },
    { key: "save-pdf", label: t("articleDetail.saveAsPdf"), onSelect: () => void handleSavePDF() },
  ];

  // Phase 2 of the 2026-07-11 editorial design pass: Archive's voice card is
  // a compact horizontal layout (square thumbnail + play overlay, title/
  // subtitle beside it) — deliberately different from "today"'s full-bleed
  // hero below, matching the two distinct layouts in the reference mockups.
  if (variant === "history") {
    return (
      <View style={styles.card}>
        <Modal transparent visible={isPdfLoading} animationType="fade">
          <View style={styles.pdfOverlay}>
            <View style={styles.pdfOverlayBox}>
              <ActivityIndicator size="large" color={colors.ink} />
              <Text style={styles.pdfOverlayText}>{t("voiceBriefing.generatingPdf")}</Text>
            </View>
          </View>
        </Modal>

        <View style={styles.historyRow}>
          <View style={styles.historyThumbWrap}>
            {heroImageUrl ? (
              <Image
                source={{ uri: heroImageUrl }}
                style={StyleSheet.absoluteFillObject}
                contentFit="cover"
                cachePolicy="memory-disk"
                transition={150}
              />
            ) : null}
            <View style={styles.historyAudioBadge}>
              <Text style={styles.historyAudioBadgeText}>{t("voiceBriefing.audioBadge")}</Text>
            </View>
            <TouchableOpacity
              style={styles.historyPlayOverlay}
              onPress={handleTogglePlayPause}
              disabled={!playEnabled}
              activeOpacity={0.8}
              accessibilityRole="button"
              accessibilityLabel={playLabel}
            >
              <PlayPauseIcon playing={isPlaying} size={14} color={colors.white} />
            </TouchableOpacity>
          </View>
          <View style={styles.historyInfo}>
            <Text style={[styles.historyTitle, { fontFamily: headlineFontFamily }]}>
              {t("voiceBriefing.morningBrief")}
            </Text>
            <Text style={styles.historySubtitle} numberOfLines={2}>
              {reportDate ? formatDate(reportDate) : ""}
              {articles.length > 0 ? ` · ${t("history.storiesCount", { count: articles.length })}` : ""}
            </Text>
          </View>
        </View>

        <View style={styles.progressWrap}>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${Math.round(progressRatio * 100)}%` }]} />
          </View>
          <View style={styles.timeRow}>
            <Text style={styles.progressText}>{elapsedLabel}</Text>
            {totalLabel ? <Text style={styles.progressText}>{totalLabel}</Text> : null}
          </View>
        </View>

        <View style={styles.historyControlsRow}>
          <ControlButton
            label={playLabel}
            onPress={handleTogglePlayPause}
            disabled={!playEnabled}
            primary
          />
          <SpeedButton
            rate={playbackRate}
            onSelect={(r) => void setRate(r)}
            disabled={!playEnabled}
          />
          <View style={styles.historyControlsSpacer} />
          {articles.length > 0 ? (
            <AnchoredMenu items={shareMenuItems}>
              <TouchableOpacity
                activeOpacity={0.7}
                accessibilityRole="button"
                accessibilityLabel={t("voiceBriefing.shareBriefA11y")}
              >
                <View style={styles.historyShareBtn}>
                  <Text style={styles.historyShareLabel}>{t("articleDetail.share")}</Text>
                  <ShareIcon size={15} color={colors.ink} />
                </View>
              </TouchableOpacity>
            </AnchoredMenu>
          ) : null}
        </View>

        {playbackError ? <Text style={styles.playbackError}>{playbackError}</Text> : null}
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <Modal transparent visible={isPdfLoading} animationType="fade">
        <View style={styles.pdfOverlay}>
          <View style={styles.pdfOverlayBox}>
            <ActivityIndicator size="large" color={colors.ink} />
            <Text style={styles.pdfOverlayText}>{t("voiceBriefing.generatingPdf")}</Text>
          </View>
        </View>
      </Modal>

      {heroImageUrl ? (
        <View style={styles.hero}>
          <Image
            source={{ uri: heroImageUrl }}
            style={StyleSheet.absoluteFillObject}
            contentFit="cover"
            cachePolicy="memory-disk"
            transition={150}
          />
          <LinearGradient
            colors={["rgba(0,0,0,0.55)", "rgba(0,0,0,0.05)", "rgba(0,0,0,0.55)"]}
            locations={[0, 0.45, 1]}
            style={StyleSheet.absoluteFillObject}
          />
          <View style={styles.heroTopRow}>
            <View style={styles.headerLeft}>
              <Text style={[styles.heroEyebrow, { fontFamily: headlineFontFamily }]}>
                {t("voiceBriefing.morningBrief")}
              </Text>
              {reportDate ? <Text style={styles.heroDate}>{formatDate(reportDate)}</Text> : null}
            </View>
            <View style={styles.headerRight}>
              <StatusBadge label={statusLabel} tone={statusTone} />
              {totalLabel ? <Text style={styles.heroDuration}>{totalLabel}</Text> : null}
            </View>
          </View>
          <View style={styles.heroWaveform} pointerEvents="none">
            {WAVEFORM_HEIGHTS.map((h, i) => (
              <Animated.View
                key={i}
                style={[
                  styles.waveformBar,
                  { height: h, transform: [{ scaleY: waveformAnims[i] }] },
                ]}
              />
            ))}
          </View>
        </View>
      ) : (
        /* Header: title + duration on same row — fallback when the day has
           no top-story image to use as a hero (e.g. very early in a topic's
           lifecycle, or an og:image-less source) */
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={styles.eyebrow}>{t("voiceBriefing.morningBrief")}</Text>
            {reportDate ? <Text style={styles.date}>{formatDate(reportDate)}</Text> : null}
          </View>
          <View style={styles.headerRight}>
            <StatusBadge label={statusLabel} tone={statusTone} />
            {totalLabel ? <Text style={styles.durationMeta}>{totalLabel}</Text> : null}
          </View>
        </View>
      )}

      <View style={styles.progressWrap}>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${Math.round(progressRatio * 100)}%` }]} />
        </View>
        <View style={styles.timeRow}>
          <Text style={styles.progressText}>{elapsedLabel}</Text>
          {totalLabel ? <Text style={styles.progressText}>{totalLabel}</Text> : null}
        </View>
      </View>

      <View style={styles.controlsRow}>
        <ControlButton
          label={playLabel}
          onPress={handleTogglePlayPause}
          disabled={!playEnabled}
          primary
        />
        <SpeedButton
          rate={playbackRate}
          onSelect={(r) => void setRate(r)}
          disabled={!playEnabled}
        />
      </View>

      {playbackError ? <Text style={styles.playbackError}>{playbackError}</Text> : null}

      {articles.length > 0 ? (
        <AnchoredMenu items={shareMenuItems}>
          <TouchableOpacity
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel={
              variant === "today"
                ? t("voiceBriefing.shareTodaysBriefA11y")
                : t("voiceBriefing.shareBriefA11y")
            }
          >
            <View style={styles.shareRow}>
              <Text style={styles.shareLabel}>
                {variant === "today"
                  ? t("voiceBriefing.shareTodaysBrief")
                  : t("voiceBriefing.shareBrief")}
              </Text>
              <ShareIcon size={14} color={colors.ink} />
            </View>
          </TouchableOpacity>
        </AnchoredMenu>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 10,
    marginBottom: 12,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  hero: {
    height: 190,
    // Bleeds past the card's own padding to reach all four edges — the
    // card's overflow:hidden + matching borderRadius above clips this back
    // to rounded top corners.
    marginHorizontal: -10,
    marginTop: -10,
    marginBottom: 10,
    backgroundColor: colors.surfaceElevated,
    justifyContent: "space-between",
    padding: 12,
  },
  heroTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  heroEyebrow: {
    fontSize: 20,
    fontWeight: "800",
    color: colors.white,
    letterSpacing: -0.2,
    marginBottom: 2,
  },
  heroDate: {
    fontSize: 12,
    fontWeight: "500",
    color: "rgba(255,255,255,0.85)",
  },
  heroDuration: {
    fontSize: 12,
    fontWeight: "600",
    color: "rgba(255,255,255,0.85)",
  },
  heroWaveform: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 2,
    height: 28,
  },
  waveformBar: {
    flex: 1,
    borderRadius: 1,
    backgroundColor: "rgba(255,255,255,0.55)",
  },
  historyRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 10,
  },
  historyThumbWrap: {
    width: 104,
    height: 104,
    borderRadius: radii.md,
    overflow: "hidden",
    backgroundColor: colors.surfaceElevated,
  },
  historyAudioBadge: {
    position: "absolute",
    top: 6,
    left: 6,
    backgroundColor: colors.ink,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: radii.pill,
  },
  historyAudioBadgeText: {
    fontSize: 8,
    fontWeight: "700",
    color: colors.white,
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  historyPlayOverlay: {
    position: "absolute",
    top: "50%",
    left: "50%",
    marginTop: -18,
    marginLeft: -18,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "rgba(0,0,0,0.55)",
    alignItems: "center",
    justifyContent: "center",
  },
  historyInfo: {
    flex: 1,
    justifyContent: "center",
    gap: 4,
  },
  historyTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -0.1,
  },
  historySubtitle: {
    fontSize: 12,
    color: colors.metaText,
    lineHeight: 17,
  },
  historyControlsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 8,
  },
  historyControlsSpacer: {
    flex: 1,
  },
  historyShareBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  historyShareLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: colors.accent,
    letterSpacing: 0.1,
  },
  cardMuted: {
    backgroundColor: colors.surface,
  },
  cardSubtle: {
    paddingVertical: 10,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 6,
  },
  headerLeft: {
    flex: 1,
    marginRight: 8,
  },
  headerRight: {
    alignItems: "flex-end",
    gap: 4,
  },
  loadingText: {
    fontSize: 13,
    color: colors.muted,
  },
  eyebrow: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.ink,
    letterSpacing: 0.2,
    marginBottom: 2,
  },
  date: {
    fontSize: 11,
    color: colors.metaText,
  },
  durationMeta: {
    fontSize: 11,
    color: colors.metaText,
  },
  voiceSection: {
    marginBottom: 4,
  },
  badge: {
    alignSelf: "flex-start",
    paddingVertical: 3,
    paddingHorizontal: 9,
    borderRadius: 20,
    borderWidth: 1,
  },
  badgeReady: {
    backgroundColor: colors.ink,
    borderColor: "transparent",
  },
  badgePending: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
  },
  badgeMuted: {
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.borderStrong,
  },
  badgeText: {
    fontSize: 9,
    fontWeight: "700",
    color: colors.muted,
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  badgeTextReady: {
    color: colors.white,
  },
  progressWrap: {
    marginTop: 6,
    gap: 4,
  },
  progressTrack: {
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.surfaceElevated,
    overflow: "hidden",
  },
  progressFill: {
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.ink,
  },
  timeRow: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  progressText: {
    fontSize: 11,
    color: colors.metaText,
    fontVariant: ["tabular-nums"],
  },
  controlsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 8,
  },
  controlButton: {
    minWidth: 54,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  controlButtonPrimary: {
    minWidth: 90,
    borderColor: "transparent",
    backgroundColor: colors.ink,
    borderRadius: 20,
  },
  controlButtonDisabled: {
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
  },
  controlButtonPrimaryDisabled: {
    backgroundColor: colors.borderStrong,
    borderColor: "transparent",
  },
  controlButtonText: {
    fontSize: 13,
    fontWeight: "600",
    color: colors.muted,
  },
  controlButtonTextPrimary: {
    color: colors.white,
  },
  controlButtonTextDisabled: {
    color: colors.faint,
  },
  playbackError: {
    fontSize: 12,
    color: colors.danger,
    marginTop: 8,
    lineHeight: 17,
  },
  retryButton: {
    marginTop: 12,
    alignSelf: "flex-start",
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  retryLabel: {
    fontSize: 13,
    color: colors.ink,
    fontWeight: "600",
  },
  speedBtn: {
    minWidth: 44,
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  speedBtnActive: {
    backgroundColor: colors.ink,
    borderColor: "transparent",
  },
  speedBtnDisabled: {
    opacity: 0.35,
  },
  speedBtnText: {
    fontSize: 12,
    fontWeight: "700",
    color: colors.muted,
    letterSpacing: 0.2,
  },
  speedBtnTextActive: {
    color: colors.white,
  },
  shareRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  shareLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: colors.accent,
    letterSpacing: 0.1,
  },
  pdfOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.45)",
    alignItems: "center",
    justifyContent: "center",
  },
  pdfOverlayBox: {
    backgroundColor: colors.cardBg,
    borderRadius: radii.lg,
    paddingVertical: 28,
    paddingHorizontal: 40,
    alignItems: "center",
    gap: 14,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 8,
  },
  pdfOverlayText: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.ink,
    letterSpacing: 0.1,
  },
});

function formatRate(r: number) {
  return r === 1 ? "1×" : `${r}×`;
}

function SpeedButton({
  rate,
  onSelect,
  disabled,
}: {
  rate: number;
  onSelect: (r: number) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();

  const speedMenuItems = SPEECH_RATE_OPTIONS.map((r) => ({
    key: String(r),
    label: formatRate(r),
    onSelect: () => onSelect(r),
  }));

  const isNonDefault = rate !== 1;

  return (
    <AnchoredMenu
      items={speedMenuItems}
      triggerStyle={[
        styles.speedBtn,
        isNonDefault && styles.speedBtnActive,
        disabled && styles.speedBtnDisabled,
      ]}
    >
      <TouchableOpacity
        disabled={disabled}
        activeOpacity={0.75}
        accessibilityLabel={t("voiceBriefing.playbackSpeedA11y", { rate: formatRate(rate) })}
      >
        <Text style={[styles.speedBtnText, isNonDefault && styles.speedBtnTextActive]}>
          {formatRate(rate)}
        </Text>
      </TouchableOpacity>
    </AnchoredMenu>
  );
}
