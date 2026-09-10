import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Platform,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import DateTimePicker, {
  DateTimePickerAndroid,
} from "@react-native-community/datetimepicker";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useTranslation } from "react-i18next";
import {
  AppleAuthenticationButton,
  AppleAuthenticationButtonStyle,
  AppleAuthenticationButtonType,
} from "expo-apple-authentication";
import { ONBOARDING_COMPLETED_KEY } from "../config";
import { useAuth } from "../context/AuthContext";
import { useUserPreferences } from "../context/UserPreferencesContext";
import { registerForPushNotifications } from "../services/pushNotifications";
import type { NotificationTime } from "../services/localNotifications";
import { isAppleSignInAvailable } from "../services/socialAuth";
import { trackEvent } from "../services/analytics";
import { colors, radii, shadows } from "../theme";
import { validateEmailPassword } from "../utils/authErrors";
import { getTopicDisplayName } from "../utils/getTopicDisplayName";
import { ALL_TOPICS } from "../utils/topicsList";
import { getHeadlineFontFamily } from "../utils/headlineFont";
import GoogleSignInButtonLazy from "../components/GoogleSignInButtonLazy";
import { TopicIcon } from "../components/TopicIcon";
import BadgeWall from "../components/BadgeWall";
import { SvgXml } from "react-native-svg";
import heroBriefingImage from "../assets/onboarding/hero_briefing.jpg";
import pillarCuratedImage from "../assets/onboarding/pillar_curated.jpg";
import pillarVoiceImage from "../assets/onboarding/pillar_voice.jpg";
import pillarWimImage from "../assets/onboarding/pillar_wim.png";

// ── Editorial chrome — a thin rule + small-caps label, used throughout
// instead of any custom illustration. Leans entirely on typography
// (Newsreader serif headlines, already this app's established identity —
// see AppHeader.tsx/ArticleDetailScreen.tsx) rather than hand-drawn or
// composited artwork, deliberately: illustration fidelity was the exact
// thing that took many rounds to get right last time.
function Rule({ spaced }: { spaced?: boolean } = {}) {
  return <View style={[styles.rule, spaced && styles.ruleSpaced]} />;
}

// ── Color accents — same soft-pastel-bg/saturated-fg 8-color pairing
// already shipped in BadgeHexagon.tsx (the badge system), reused here
// rather than inventing a new palette. Expressed as flat accent bars,
// tinted text, and tag pills — deliberately NOT the emoji-in-a-pastel-
// circle badge this screen used at first: direct user feedback flagged
// that exact pattern as reading like a generic AI-generated UI template,
// so it was removed everywhere in favor of quieter, more editorial color
// (a colored rule, a colored numeral, a tinted tag) instead of a floating
// icon bubble.
const ACCENT_COLORS: { bg: string; fg: string }[] = [
  { bg: "#E3EDFB", fg: "#2D5FB0" }, // blue
  { bg: "#FDECD9", fg: "#C1671B" }, // orange
  { bg: "#E3F2E8", fg: "#2E7D46" }, // green
  { bg: "#EEE7FA", fg: "#6B3FA0" }, // purple
  { bg: "#FBE7EC", fg: "#C43A5C" }, // rose
  { bg: "#FDF3D0", fg: "#B8860B" }, // yellow
  { bg: "#E4E6F5", fg: "#2B2E6B" }, // navy
  { bg: "#FBF0D6", fg: "#A8790A" }, // gold
];

function accentForIndex(i: number) {
  return ACCENT_COLORS[i % ACCENT_COLORS.length];
}

// Monochrome Lucide line icons for the Time Picker's feature-detail card.
const CLOCK_XML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
const SLIDERS_XML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/></svg>`;
const CHECK_XML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
const LOCK_XML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`;
const BELL_XML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>`;
// Solid (filled) bell for the notifications illustration — a crisp vector,
// not the flat color emoji, so it reads as a designed icon.
const BELL_SOLID_XML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 22a2.6 2.6 0 0 0 2.55-2.1h-5.1A2.6 2.6 0 0 0 12 22Zm7.3-5.02-1.55-1.55V10.3a5.75 5.75 0 0 0-4.5-5.61V4a1.25 1.25 0 0 0-2.5 0v.69a5.75 5.75 0 0 0-4.5 5.61v5.13L4.7 16.98A1.02 1.02 0 0 0 5.42 18.7h13.16a1.02 1.02 0 0 0 .72-1.72Z"/></svg>`;

// ── Real product screenshots (2026-07-12 follow-up — "lacks real images,
// combine the intro with the real mobile app") — direct captures of this
// app's own live screens, cropped and compressed, bundled as static assets.
// Deliberately not a drawn phone mockup or stock photo: showing the actual
// product is the most honest way to answer "this looks generic" — see
// docs/ENGINEERING.md's Mobile section.
const HERO_ASPECT_RATIO = 700 / 1522;
// Square feature tiles for the compact horizontal-row layout (2026-07-12 —
// the earlier image-on-top cards were ~1000pt tall total and forced the user
// to scroll to see all three pillars). All three are slices of the SAME
// vivid story shown in page 1's hero (the "Rare Woodland Butterfly" wildlife
// piece): the butterfly photo (curated), a composed "Why It Matters" card,
// and the teal Morning Brief audio tile with a play glyph. One coherent
// narrative, matching page 1's premium quality.
const PILLAR_TILES: number[] = [
  pillarCuratedImage,
  pillarWimImage,
  pillarVoiceImage,
];

// A realistic iPhone silhouette around the hero screenshot — rounded
// bezel, side-button nubs, a Dynamic-Island-style pill at the top. No
// illustration inside it, just the real screenshot.
function PhoneFrame({ width }: { width: number }) {
  return (
    <View style={[styles.phoneFrame, { width, aspectRatio: HERO_ASPECT_RATIO }]}>
      <Image source={heroBriefingImage} style={styles.phoneImage} resizeMode="cover" />
      <View style={[styles.phoneButton, styles.phoneButtonPower]} />
      <View style={[styles.phoneButton, styles.phoneButtonVolUp]} />
      <View style={[styles.phoneButton, styles.phoneButtonVolDown]} />
    </View>
  );
}

const MIN_TOPICS = 3;
type AuthFormMode = "sign_in" | "sign_up";


type Props = {
  onComplete: () => void;
};

export default function OnboardingScreen({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectedTime, setSelectedTime] = useState<Date>(() => {
    const d = new Date();
    d.setHours(7, 0, 0, 0);
    return d;
  });
  const { updatePreferences } = useUserPreferences();

  const canAdvance = selected.size >= MIN_TOPICS;

  function toggleTopic(topic: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(topic)) {
        next.delete(topic);
      } else {
        next.add(topic);
      }
      return next;
    });
  }

  async function savePreferencesAndAdvance(enableNotifications: boolean) {
    const h = String(selectedTime.getHours()).padStart(2, "0");
    const m = String(selectedTime.getMinutes()).padStart(2, "0");
    const notificationTime: NotificationTime = `${h}:${m}`;
    if (enableNotifications) {
      await registerForPushNotifications(notificationTime);
    }
    const topicList = [...selected];
    await updatePreferences({
      ...(topicList.length > 0 && {
        default_topic: topicList[0],
        selected_topics: topicList,
      }),
      notification_time: notificationTime,
      push_notifications_enabled: enableNotifications,
    });
    trackEvent("onboarding_completed", {
      metadata_text: `topics:${topicList.length} notifications:${enableNotifications} time:${notificationTime}`,
    });
    advance();
  }

  async function finishOnboarding() {
    await AsyncStorage.setItem(ONBOARDING_COMPLETED_KEY, "true");
    onComplete();
  }

  function advance() {
    setStep((s) => s + 1);
  }

  return (
    <View style={styles.root}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />
      {/* Pure-white full-screen background on the Topic Picker only — spans
          the entire screen (behind the safe-area insets) so there's no color
          seam at the bottom. Color now lives only in the tinted topic icons. */}
      {step === 3 ? (
        <View style={styles.whiteBackdrop} pointerEvents="none" />
      ) : null}
      <SafeAreaView style={styles.safe}>

      {step === 0 ? <Welcome onNext={advance} /> : null}
      {step === 1 ? <HowItWorks onNext={advance} /> : null}
      {step === 2 ? <StreakStep onNext={advance} /> : null}
      {step === 3 ? (
        <TopicPicker
          selected={selected}
          canAdvance={canAdvance}
          onToggle={toggleTopic}
          onNext={advance}
        />
      ) : null}
      {step === 4 ? (
        <TimePicker
          selectedTime={selectedTime}
          onSelect={setSelectedTime}
          onNext={advance}
        />
      ) : null}
      {step === 5 ? (
        <NotificationsStep onComplete={savePreferencesAndAdvance} />
      ) : null}
      {step === 6 ? <AuthStep onDone={finishOnboarding} /> : null}
      </SafeAreaView>
    </View>
  );
}

// ── Step 0: Welcome ───────────────────────────────────────────────────────────

function Welcome({ onNext }: { onNext: () => void }) {
  const { t } = useTranslation();
  return (
    <View style={styles.step}>
      <View style={styles.welcomeTop}>
        <Text style={[styles.brandBig, { fontFamily: getHeadlineFontFamily("bold") }]}>
          WhatsNews
        </Text>
        <Text style={styles.welcomeSub}>{t("onboarding.welcomeSub")}</Text>

        <View style={styles.backdrop}>
          <PhoneFrame width={205} />
        </View>
      </View>
      <TouchableOpacity style={styles.btnPrimary} onPress={onNext} activeOpacity={0.85}>
        <Text style={styles.btnPrimaryText}>{t("onboarding.getStarted")}</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Step 1: How It Works ──────────────────────────────────────────────────────

function HowItWorks({ onNext }: { onNext: () => void }) {
  const { t } = useTranslation();
  return (
    <View style={styles.step}>
      <ProgressDots step={1} />
      <ScrollView style={styles.scrollArea} showsVerticalScrollIndicator={false}>
        <Text style={styles.stepEyebrow}>{t("onboarding.howItWorksEyebrow")}</Text>
        <Text style={[styles.stepHeadline, { fontFamily: getHeadlineFontFamily("bold") }]}>
          {t("onboarding.howItWorksHeadline")}
        </Text>
        <Rule spaced />

        <View style={styles.pillars}>
          <Pillar
            index={0}
            title={t("onboarding.pillar1Title")}
            body={t("onboarding.pillar1Body")}
          />
          <Pillar
            index={1}
            title={t("onboarding.pillar2Title")}
            body={t("onboarding.pillar2Body")}
          />
          <Pillar
            index={2}
            title={t("onboarding.pillar3Title")}
            body={t("onboarding.pillar3Body")}
          />
        </View>
      </ScrollView>
      <TouchableOpacity style={styles.btnPrimary} onPress={onNext} activeOpacity={0.85}>
        <Text style={styles.btnPrimaryText}>{t("common.continue")}</Text>
      </TouchableOpacity>
    </View>
  );
}

function Pillar({ index, title, body }: { index: number; title: string; body: string }) {
  return (
    <View style={styles.pillarCard}>
      <View style={styles.pillarTileWrap}>
        <Image source={PILLAR_TILES[index]} style={styles.pillarTile} resizeMode="cover" />
      </View>
      <View style={styles.pillarText}>
        <Text style={styles.pillarNum}>
          {String(index + 1).padStart(2, "0")}
        </Text>
        <Text style={[styles.pillarTitle, { fontFamily: getHeadlineFontFamily("bold") }]}>
          {title}
        </Text>
        <Text style={styles.pillarBody}>{body}</Text>
      </View>
    </View>
  );
}

// ── Step 2: Streak ────────────────────────────────────────────────────────────

// Illustrative preview values — mirrors the real Streak tab (StreakScreen.tsx)
// so onboarding shows exactly what the shipped feature looks like. A 7-day
// example unlocks the first two milestones (3-day, 1-week) in the reused
// BadgeWall, reading as an aspirational "streak in progress".
const STREAK_PREVIEW = { streak: 7, longest: 7, activeDays: 12 } as const;

function StreakStep({ onNext }: { onNext: () => void }) {
  const { t } = useTranslation();
  return (
    <View style={styles.step}>
      <ProgressDots step={2} />
      <Text style={styles.stepEyebrow}>{t("onboarding.streakEyebrow")}</Text>
      <Text style={[styles.stepHeadline, { fontFamily: getHeadlineFontFamily("bold") }]}>
        {t("onboarding.streakHeadline")}
      </Text>
      <Rule spaced />
      <Text style={styles.stepSub}>{t("onboarding.streakSub")}</Text>

      <View style={styles.streakBody}>
        {/* Header — same 🔥 + number + unit + "Keep it going!" as StreakScreen */}
        <View style={styles.streakHeader}>
          <Text style={styles.streakEmoji}>🔥</Text>
          <Text style={styles.streakNum}>{STREAK_PREVIEW.streak}</Text>
          <Text style={styles.streakUnit}>{t("streak.days", { count: STREAK_PREVIEW.streak })}</Text>
        </View>
        <Text style={styles.streakKeepGoing}>{t("streak.keepItGoing")}</Text>

        {/* Stats — mirrors StreakScreen's LONGEST STREAK / ACTIVE DAYS card */}
        <View style={styles.streakStatsRow}>
          <View style={styles.streakStat}>
            <Text style={styles.streakStatNum}>{STREAK_PREVIEW.longest}</Text>
            <Text style={styles.streakStatLabel}>{t("streak.longestStreak")}</Text>
          </View>
          <View style={styles.streakStatDivider} />
          <View style={styles.streakStat}>
            <Text style={styles.streakStatNum}>{STREAK_PREVIEW.activeDays}</Text>
            <Text style={styles.streakStatLabel}>{t("streak.activeDays")}</Text>
          </View>
        </View>

        {/* Milestones — the real BadgeWall component, exact visual match */}
        <View style={styles.streakMilestonesCard}>
          <Text style={styles.streakSectionLabel}>{t("streak.milestones")}</Text>
          <BadgeWall longestStreak={STREAK_PREVIEW.longest} />
        </View>
      </View>

      <TouchableOpacity style={styles.btnPrimary} onPress={onNext} activeOpacity={0.85}>
        <Text style={styles.btnPrimaryText}>{t("common.continue")}</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Step 3: Topic Picker ──────────────────────────────────────────────────────

function TopicPicker({
  selected,
  canAdvance,
  onToggle,
  onNext,
}: {
  selected: Set<string>;
  canAdvance: boolean;
  onToggle: (t: string) => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  const remaining = MIN_TOPICS - selected.size;

  return (
    <View style={styles.step}>
      <ProgressDots step={3} />
      <Text style={styles.stepEyebrow}>{t("onboarding.interestsEyebrow")}</Text>
      <Text style={[styles.stepHeadline, { fontFamily: getHeadlineFontFamily("bold") }]}>
        {t("onboarding.interestsHeadline")}
      </Text>
      <Rule spaced />
      <Text style={styles.stepSub}>
        {t("onboarding.interestsSub", { count: MIN_TOPICS })}
      </Text>

      <ScrollView
        style={styles.scrollArea}
        contentContainerStyle={styles.topicsScrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.topicsGrid}>
          {ALL_TOPICS.map((topic, i) => {
            const isSelected = selected.has(topic);
            const accent = accentForIndex(i);
            return (
              <TouchableOpacity
                key={topic}
                style={[styles.topicChip, isSelected && styles.topicChipSelected]}
                onPress={() => onToggle(topic)}
                activeOpacity={0.75}
              >
                <TopicIcon
                  topic={topic}
                  size={17}
                  color={isSelected ? colors.bg : accent.fg}
                />
                <Text
                  style={[styles.topicChipText, isSelected && styles.topicChipTextSelected]}
                  numberOfLines={1}
                >
                  {getTopicDisplayName(topic)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>

      <View style={styles.topicFooter}>
        <Text style={styles.selectionHint}>
          {remaining > 0
            ? t("onboarding.selectMoreToContinue", { count: remaining })
            : t("onboarding.selectedCount", { count: selected.size })}
        </Text>
        <TouchableOpacity
          style={[styles.btnPrimary, !canAdvance && styles.btnDisabled]}
          onPress={canAdvance ? onNext : undefined}
          activeOpacity={0.85}
          disabled={!canAdvance}
        >
          <Text style={styles.btnPrimaryText}>{t("common.continue")}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── Step 4: Time Picker ───────────────────────────────────────────────────────

function TimePicker({
  selectedTime,
  onSelect,
  onNext,
}: {
  selectedTime: Date;
  onSelect: (d: Date) => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();

  const openAndroidPicker = () => {
    DateTimePickerAndroid.open({
      value: selectedTime,
      mode: "time",
      is24Hour: false,
      minuteInterval: 5,
      onChange: (_event, date) => { if (date) onSelect(date); },
    });
  };

  return (
    <View style={styles.step}>
      <ProgressDots step={4} />
      <Text style={[styles.stepEyebrow, { color: colors.ink }]}>
        {t("onboarding.scheduleEyebrow")}
      </Text>
      <Text style={[styles.stepHeadline, { fontFamily: getHeadlineFontFamily("bold") }]}>
        {t("onboarding.scheduleHeadline")}
      </Text>
      <Rule spaced />
      <Text style={styles.stepSub}>
        {t("onboarding.scheduleSub")}
      </Text>

      <View style={styles.timeBody}>
        <View style={styles.timePickerWrap}>
          {/* Android has no true inline picker — display="spinner" still
              opens an imperative modal dialog on mount, same underlying
              platform difference documented for AccountScreen's Briefing
              Time row. Here it's worse un-fixed: after the one-time dialog
              closes there was no fallback UI at all, leaving Android users
              with no way to see or change the selected time. Fixed with a
              tappable time label + DateTimePickerAndroid.open(). */}
          {Platform.OS === "android" ? (
            <TouchableOpacity onPress={openAndroidPicker} activeOpacity={0.7} style={styles.timePickerAndroidBtn}>
              <Text style={styles.timePickerAndroidText}>
                {selectedTime.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
              </Text>
            </TouchableOpacity>
          ) : (
            <DateTimePicker
              value={selectedTime}
              mode="time"
              display="spinner"
              onChange={(_event, date) => { if (date) onSelect(date); }}
              minuteInterval={5}
              style={styles.timePicker}
              textColor={colors.ink}
            />
          )}
        </View>

        {/* Feature-detail card — fills the space under the picker and explains
            what choosing a time actually does (2026-07-12). Monochrome line
            icons + editorial rows, matching this page's black-type direction. */}
        <View style={styles.scheduleCard}>
          <View style={styles.scheduleRow}>
            <View style={styles.scheduleIcon}>
              <SvgXml xml={CLOCK_XML} width={20} height={20} color={colors.ink} />
            </View>
            <View style={styles.scheduleRowText}>
              <Text style={styles.scheduleRowTitle}>
                {t("onboarding.scheduleCardTitle1")}
              </Text>
              <Text style={styles.scheduleRowBody}>
                {t("onboarding.scheduleCardBody1")}
              </Text>
            </View>
          </View>
          <View style={styles.scheduleDivider} />
          <View style={styles.scheduleRow}>
            <View style={styles.scheduleIcon}>
              <SvgXml xml={SLIDERS_XML} width={20} height={20} color={colors.ink} />
            </View>
            <View style={styles.scheduleRowText}>
              <Text style={styles.scheduleRowTitle}>
                {t("onboarding.scheduleCardTitle2")}
              </Text>
              <Text style={styles.scheduleRowBody}>
                {t("onboarding.scheduleCardBody2")}
              </Text>
            </View>
          </View>
        </View>
      </View>

      <TouchableOpacity style={styles.btnPrimary} onPress={onNext} activeOpacity={0.85}>
        <Text style={styles.btnPrimaryText}>{t("common.continue")}</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Step 5: Notifications ─────────────────────────────────────────────────────

function NotificationsStep({
  onComplete,
}: {
  onComplete: (enable: boolean) => void;
}) {
  const { t } = useTranslation();
  return (
    <View style={[styles.step, styles.stepCentered]}>
      <ProgressDots step={5} />
      <View style={styles.notifContent}>
        <Text style={styles.stepEyebrow}>
          {t("onboarding.notifEyebrow")}
        </Text>
        <Text style={[styles.stepHeadline, { fontFamily: getHeadlineFontFamily("bold") }]}>
          {t("onboarding.notifHeadline")}
        </Text>
        <Text style={[styles.stepSub, styles.notifSubTight]}>{t("onboarding.notifSub")}</Text>
        <Text style={styles.notifSub2}>{t("onboarding.notifSub2")}</Text>

        {/* Bell illustration — soft cream disc + bell emoji, amber "ringing"
            ticks, and a dark confirm badge (2026-07-12, replicating the target
            mockup). */}
        <View style={styles.notifBellWrap}>
          <View style={[styles.notifRing, styles.notifRingA]} />
          <View style={[styles.notifRing, styles.notifRingB]} />
          <View style={[styles.notifRing, styles.notifRingC]} />
          <View style={styles.notifBellCircle}>
            <SvgXml xml={BELL_SOLID_XML} width={68} height={68} color="#E0A02B" />
          </View>
          <View style={styles.notifCheckBadge}>
            <SvgXml xml={CHECK_XML} width={15} height={15} color="#FFFFFF" />
          </View>
        </View>

        <View style={styles.notifInfoCard}>
          <View style={styles.notifInfoIcon}>
            <SvgXml xml={LOCK_XML} width={18} height={18} color={colors.ink} />
          </View>
          <View style={styles.notifInfoText}>
            <Text style={styles.notifInfoTitle}>{t("onboarding.notifInfoTitle")}</Text>
            <Text style={styles.notifInfoBody}>{t("onboarding.notifInfoBody")}</Text>
          </View>
        </View>
      </View>
      <View style={styles.notifButtons}>
        <TouchableOpacity
          style={styles.btnPrimary}
          onPress={() => onComplete(true)}
          activeOpacity={0.85}
        >
          <View style={styles.btnPrimaryRow}>
            <SvgXml xml={BELL_XML} width={18} height={18} color="#FFFFFF" />
            <Text style={styles.btnPrimaryText}>{t("onboarding.turnOnNotifications")}</Text>
          </View>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.btnGhost}
          onPress={() => onComplete(false)}
          activeOpacity={0.7}
        >
          <Text style={styles.btnGhostText}>{t("onboarding.maybeLater")}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── Step 6: Auth ───────────────────────────────────────────────────────────────
//
// Deliberately last — by this point the user has already invested time
// personalizing topics/schedule, which converts better than asking upfront.
// Email/password form is shown ABOVE the Apple/Google buttons (explicit
// product choice, opposite of AccountScreen's ordering).
// "Continue as Guest" always available; nothing here is required.

function AuthStep({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const {
    authEnabled,
    authBusy,
    signInWithEmail,
    signUpWithEmail,
    signInWithApple,
    signInWithGoogle,
  } = useAuth();
  const [mode, setMode] = useState<AuthFormMode>("sign_up");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [appleAvailable, setAppleAvailable] = useState(false);

  useEffect(() => {
    void isAppleSignInAvailable().then(setAppleAvailable);
  }, []);

  // Auth is a master switch (ENABLE_AUTH) — when it's off, none of the sign-in
  // methods below can work, so skip straight to guest rather than show dead UI.
  useEffect(() => {
    if (!authEnabled) onDone();
  }, [authEnabled, onDone]);

  if (!authEnabled) {
    return null;
  }

  async function handleEmailSubmit() {
    setFormError(null);
    const validationError = validateEmailPassword(
      email,
      password,
      mode === "sign_up" ? confirmPassword : undefined,
    );
    if (validationError) {
      setFormError(validationError);
      return;
    }
    const result =
      mode === "sign_up" ? await signUpWithEmail(email, password) : await signInWithEmail(email, password);
    if (!result.ok) {
      setFormError(result.message);
      return;
    }
    onDone();
  }

  async function handleAppleSignIn() {
    setFormError(null);
    const result = await signInWithApple();
    if (result.ok) {
      onDone();
      return;
    }
    if (result.message) setFormError(result.message);
  }

  async function handleGoogleSignIn() {
    setFormError(null);
    const result = await signInWithGoogle();
    if (result.ok) {
      onDone();
      return;
    }
    if (result.message) setFormError(result.message);
  }

  return (
    <View style={styles.step}>
      <ProgressDots step={6} />
      <ScrollView
        style={styles.scrollArea}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.stepEyebrow}>{t("onboarding.authEyebrow")}</Text>
        <Text style={styles.stepHeadline}>{t("onboarding.authHeadline")}</Text>
        <Text style={styles.stepSub}>{t("onboarding.authSub")}</Text>

        <TextInput
          style={styles.authInput}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          textContentType="emailAddress"
          placeholder={t("signIn.email")}
          placeholderTextColor={colors.muted}
          editable={!authBusy}
        />
        <TextInput
          style={styles.authInput}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          textContentType={mode === "sign_up" ? "newPassword" : "password"}
          placeholder={t("signIn.password")}
          placeholderTextColor={colors.muted}
          editable={!authBusy}
        />
        {mode === "sign_up" ? (
          <TextInput
            style={styles.authInput}
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            textContentType="newPassword"
            placeholder={t("signIn.confirmPassword")}
            placeholderTextColor={colors.muted}
            editable={!authBusy}
          />
        ) : null}

        {formError ? <Text style={styles.authError}>{formError}</Text> : null}

        <TouchableOpacity
          style={styles.btnPrimary}
          onPress={() => void handleEmailSubmit()}
          activeOpacity={0.85}
          disabled={authBusy}
        >
          {authBusy ? (
            <ActivityIndicator color={colors.white} />
          ) : (
            <Text style={styles.btnPrimaryText}>
              {mode === "sign_up" ? t("signIn.createAccountBtn") : t("signIn.signIn")}
            </Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          onPress={() => setMode(mode === "sign_up" ? "sign_in" : "sign_up")}
          activeOpacity={0.7}
          style={styles.authModeSwitch}
        >
          <Text style={styles.authModeSwitchText}>
            {mode === "sign_up" ? t("onboarding.alreadyHaveAccount") : t("onboarding.newHere")}
          </Text>
        </TouchableOpacity>

        <View style={styles.dividerRow}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerLabel}>{t("onboarding.orContinueWith")}</Text>
          <View style={styles.dividerLine} />
        </View>

        {appleAvailable ? (
          <AppleAuthenticationButton
            buttonType={AppleAuthenticationButtonType.CONTINUE}
            buttonStyle={AppleAuthenticationButtonStyle.BLACK}
            cornerRadius={10}
            style={styles.socialBtn}
            onPress={() => void handleAppleSignIn()}
          />
        ) : null}
        <GoogleSignInButtonLazy
          onPress={() => void handleGoogleSignIn()}
          disabled={authBusy}
          style={styles.socialBtn}
        />
      </ScrollView>

      <TouchableOpacity onPress={onDone} activeOpacity={0.7} style={styles.btnGhost}>
        <Text style={styles.btnGhostText}>{t("onboarding.continueAsGuest")}</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Progress dots ─────────────────────────────────────────────────────────────

function ProgressDots({ step }: { step: number }) {
  return (
    <View style={styles.dots}>
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <View key={i} style={[styles.dot, step >= i && styles.dotActive]} />
      ))}
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  safe: {
    flex: 1,
  },
  whiteBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#FFFFFF",
  },
  step: {
    flex: 1,
    paddingHorizontal: 28,
    paddingTop: 24,
    paddingBottom: 32,
    justifyContent: "space-between",
  },
  stepCentered: {
    justifyContent: "space-between",
  },

  // Progress
  dots: {
    flexDirection: "row",
    gap: 6,
    marginBottom: 32,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.border,
  },
  dotActive: {
    backgroundColor: colors.ink,
  },

  // Welcome — editorial masthead: a thin rule, a small-caps dateline label,
  // a large serif wordmark, another rule, a centered tagline, then a
  // numbered index of the 3 value props. No illustration.
  rule: {
    height: 1,
    backgroundColor: colors.ink,
    opacity: 0.18,
    width: "100%",
  },
  ruleSpaced: {
    marginBottom: 16,
  },
  phoneFrame: {
    padding: 10,
    borderRadius: 46,
    backgroundColor: colors.ink,
    alignItems: "center",
    zIndex: 2,
    ...shadows.elevated,
  },
  phoneImage: {
    width: "100%",
    height: "100%",
    borderRadius: 36,
  },
  phoneButton: {
    position: "absolute",
    backgroundColor: colors.ink,
    borderRadius: 3,
  },
  phoneButtonPower: {
    right: -3,
    top: "24%",
    width: 3,
    height: 74,
  },
  phoneButtonVolUp: {
    left: -3,
    top: "17%",
    width: 3,
    height: 34,
  },
  phoneButtonVolDown: {
    left: -3,
    top: "26%",
    width: 3,
    height: 34,
  },
  backdrop: {
    flex: 1,
    width: "100%",
    alignItems: "center",
    justifyContent: "center",
    // Biased slightly above dead-center — pure centering (paddingBottom: 0)
    // read as "too low" once seen live, since the heavy black "Get Started"
    // button below pulls the eye down more than the lighter header text
    // above pulls it up.
    paddingBottom: 56,
  },
  welcomeTop: {
    flex: 1,
    justifyContent: "flex-start",
    alignItems: "center",
    paddingTop: 12,
  },
  brandBig: {
    fontSize: 50,
    fontWeight: "800",
    color: colors.ink,
    letterSpacing: -1,
    textAlign: "center",
  },
  welcomeHeadline: {
    fontSize: 42,
    fontWeight: "800",
    color: colors.ink,
    lineHeight: 48,
    letterSpacing: -1,
    marginBottom: 20,
  },
  welcomeSub: {
    fontSize: 16,
    color: colors.summary,
    lineHeight: 24,
    textAlign: "center",
    marginTop: 6,
  },

  // Step common
  scrollArea: {
    flex: 1,
    marginBottom: 16,
  },
  stepEyebrow: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 8,
  },
  stepHeadline: {
    fontSize: 32,
    fontWeight: "800",
    color: colors.ink,
    lineHeight: 38,
    letterSpacing: -0.5,
    marginBottom: 10,
  },
  stepSub: {
    fontSize: 15,
    color: colors.muted,
    lineHeight: 22,
    marginBottom: 24,
  },

  // How it works — compact horizontal rows so all three pillars (01/02/03)
  // fit on one screen without scrolling (2026-07-12). A small square tile
  // on the left, number + serif title + blurb on the right.
  pillars: {
    gap: 12,
  },
  pillarCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    padding: 12,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    ...shadows.card,
  },
  pillarTileWrap: {
    width: 96,
    height: 96,
    borderRadius: radii.sm,
    overflow: "hidden",
    backgroundColor: colors.cardBg,
  },
  pillarTile: {
    width: "100%",
    height: "100%",
  },
  pillarText: {
    flex: 1,
    paddingTop: 2,
  },
  pillarNum: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1,
    marginBottom: 4,
  },
  pillarTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.ink,
    marginBottom: 5,
    lineHeight: 23,
    letterSpacing: -0.3,
  },
  pillarBody: {
    fontSize: 13.5,
    color: colors.summary,
    lineHeight: 19,
  },

  // Topic picker — a 3-column pill grid (2026-07-12) so all 20 topics fit on
  // one screen with no scroll. Lucide line icons tinted a soft per-topic color
  // (reusing the badge palette) add color without the "AI-generated" emoji look;
  // selected is a solid-ink pill with a white icon + label.
  // ScrollView content is top-aligned (no vertical centering — that created a
  // big gap under the subtitle). The grid sits right under the header; the
  // footer/Continue lives OUTSIDE this ScrollView so it's always visible. On
  // tall phones the 7 rows fit with no scroll; on small phones it scrolls.
  topicsScrollContent: {
    flexGrow: 1,
  },
  topicsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    // Separate column/row gaps: a tight columnGap keeps 3 chips per row (a
    // larger shared `gap` overflowed and forced a 2-column wrap). Compact
    // rowGap + pill height so all 20 fit on one screen with no scroll.
    columnGap: 8,
    rowGap: 9,
  },
  topicChip: {
    width: "31.5%",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 8,
    paddingVertical: 12,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.cardBg,
  },
  topicChipSelected: {
    backgroundColor: colors.ink,
    borderColor: colors.ink,
  },
  topicChipText: {
    flex: 1,
    fontSize: 12.5,
    fontWeight: "500",
    color: colors.ink,
    letterSpacing: -0.2,
  },
  topicChipTextSelected: {
    color: colors.bg,
    fontWeight: "600",
  },
  topicFooter: {
    gap: 12,
  },
  selectionHint: {
    fontSize: 13,
    color: colors.metaText,
    textAlign: "center",
  },

  // Time picker
  timeBody: {
    flex: 1,
    justifyContent: "center",
  },
  timePickerWrap: {
    alignItems: "center",
  },
  timePicker: {
    width: "100%",
    height: 180,
  },
  timePickerAndroidBtn: {
    paddingVertical: 24,
    paddingHorizontal: 32,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
  },
  timePickerAndroidText: {
    fontSize: 40,
    fontWeight: "700",
    color: colors.ink,
  },
  scheduleCard: {
    marginTop: 16,
    padding: 16,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  scheduleRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
  scheduleIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  scheduleRowText: {
    flex: 1,
  },
  scheduleRowTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.ink,
    marginBottom: 3,
  },
  scheduleRowBody: {
    fontSize: 13.5,
    color: colors.muted,
    lineHeight: 19,
  },
  scheduleDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 14,
  },

  // Streak — mirrors StreakScreen.tsx's header/stats/milestones styling
  streakBody: {
    flex: 1,
    justifyContent: "flex-start",
    paddingTop: 28,
  },
  streakHeader: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
  },
  streakEmoji: { fontSize: 34, marginBottom: 6 },
  streakNum: { fontSize: 52, fontWeight: "900", color: colors.ink, lineHeight: 56 },
  streakUnit: { fontSize: 17, fontWeight: "600", color: colors.muted, marginBottom: 9 },
  streakKeepGoing: { fontSize: 15, color: colors.muted, marginTop: 2, marginBottom: 18 },

  streakStatsRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 16,
    marginBottom: 14,
  },
  streakStat: { flex: 1, alignItems: "center", gap: 4 },
  streakStatDivider: { width: 1, height: 32, backgroundColor: colors.border },
  streakStatNum: { fontSize: 24, fontWeight: "800", color: colors.ink },
  streakStatLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 0.6,
  },

  streakMilestonesCard: {
    backgroundColor: colors.cardBg,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 16,
  },
  streakSectionLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 1,
    marginBottom: 12,
  },

  // Notifications
  notifContent: {
    flex: 1,
    justifyContent: "flex-start",
    paddingTop: 24,
  },
  notifSubTight: {
    marginBottom: 4,
  },
  notifSub2: {
    fontSize: 15,
    color: colors.muted,
    lineHeight: 22,
  },
  notifBellWrap: {
    width: 132,
    height: 132,
    alignSelf: "center",
    marginTop: 36,
    marginBottom: 8,
  },
  notifBellCircle: {
    width: 132,
    height: 132,
    borderRadius: 66,
    backgroundColor: "#FBEFD2",
    alignItems: "center",
    justifyContent: "center",
  },
  notifCheckBadge: {
    position: "absolute",
    top: 2,
    right: 2,
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.ink,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 3,
    borderColor: colors.bg,
  },
  notifRing: {
    position: "absolute",
    backgroundColor: "#E6A73B",
    borderRadius: 2,
  },
  notifRingA: {
    width: 18,
    height: 3,
    top: 10,
    left: -8,
    transform: [{ rotate: "-40deg" }],
  },
  notifRingB: {
    width: 3,
    height: 18,
    top: -12,
    left: 34,
  },
  notifRingC: {
    width: 18,
    height: 3,
    top: 6,
    left: 118,
    transform: [{ rotate: "40deg" }],
  },
  notifInfoCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: 28,
    padding: 16,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  notifInfoIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  notifInfoText: {
    flex: 1,
  },
  notifInfoTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.ink,
    marginBottom: 3,
  },
  notifInfoBody: {
    fontSize: 13.5,
    color: colors.muted,
    lineHeight: 19,
  },
  notifPreview: {
    marginTop: 32,
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  notifPreviewHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 8,
  },
  notifPreviewDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  notifPreviewApp: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.metaText,
    letterSpacing: 0.8,
  },
  notifPreviewTime: {
    fontSize: 11,
    color: colors.faint,
  },
  notifPreviewTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: colors.ink,
    marginBottom: 4,
  },
  notifPreviewBody: {
    fontSize: 13.5,
    color: colors.muted,
    lineHeight: 19,
  },
  notifButtons: {
    gap: 12,
  },

  // Buttons
  btnPrimary: {
    backgroundColor: colors.ink,
    borderRadius: 6,
    paddingVertical: 16,
    alignItems: "center",
  },
  btnPrimaryRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  btnPrimaryText: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.white,
  },
  btnDisabled: {
    backgroundColor: colors.surfaceMuted,
  },
  btnGhost: {
    paddingVertical: 14,
    alignItems: "center",
  },
  btnGhostText: {
    fontSize: 15,
    fontWeight: "500",
    color: colors.muted,
  },

  // Auth step
  authInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 6,
    paddingHorizontal: 14,
    paddingVertical: 13,
    fontSize: 15,
    color: colors.ink,
    marginBottom: 10,
  },
  authError: {
    fontSize: 13,
    color: "#C0392B",
    marginBottom: 10,
  },
  authModeSwitch: {
    alignItems: "center",
    paddingVertical: 14,
  },
  authModeSwitchText: {
    fontSize: 13,
    color: colors.metaText,
    fontWeight: "500",
  },
  socialBtn: {
    width: "100%",
    height: 48,
    marginBottom: 10,
  },
  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginVertical: 16,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  dividerLabel: {
    fontSize: 12,
    color: colors.muted,
  },
});
