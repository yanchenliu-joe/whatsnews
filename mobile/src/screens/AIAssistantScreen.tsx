/**
 * AIAssistantScreen — WhatsNews AI Intelligence Hub (Phase 22)
 *
 * Flow:
 *   1. Opens with article context injected from ArticleDetailScreen
 *   2. Immediately generates a proactive "Today's Insight" (no user prompt needed)
 *   3. Suggested question chips appear after the insight completes
 *   4. User can tap chips or type their own questions
 *   5. Conversation continues with full article context re-injected each turn
 *
 * The screen never knows which model answered — all routing is backend-side.
 */

import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useCallback, useEffect, useRef, useState } from "react";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useTranslation } from "react-i18next";
import type { RootStackParamList } from "../navigation/types";
import type { AIChatArticle } from "../services/aiApi";
import type { ChatBubble } from "../hooks/useAIChat";
import { useAIChat } from "../hooks/useAIChat";
import { colors, radii, spacing } from "../theme";
import { normalizeNullableString, normalizeString } from "../utils/dataContracts";
import { backArrow } from "../utils/rtl";

type Props = NativeStackScreenProps<RootStackParamList, "AIAssistant">;

// ─── Typing animation ─────────────────────────────────────────────────────────

function TypingDots() {
  const [dots, setDots] = useState(".");
  useEffect(() => {
    const id = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "." : prev + "."));
    }, 400);
    return () => clearInterval(id);
  }, []);
  return <Text style={styles.typingDots}>{dots}</Text>;
}

// ─── Chat bubble ──────────────────────────────────────────────────────────────

function Bubble({ bubble }: { bubble: ChatBubble }) {
  const isUser = bubble.role === "user";
  const isEmpty = !bubble.content && bubble.isStreaming;

  return (
    <View style={[styles.bubbleRow, isUser ? styles.bubbleRowUser : styles.bubbleRowAssistant]}>
      {!isUser && (
        <View style={styles.avatarDot}>
          <Text style={styles.avatarText}>AI</Text>
        </View>
      )}
      <View
        style={[
          styles.bubble,
          isUser ? styles.bubbleUser : styles.bubbleAssistant,
        ]}
      >
        {isEmpty ? (
          <TypingDots />
        ) : (
          <Text style={isUser ? styles.bubbleTextUser : styles.bubbleTextAssistant}>
            {bubble.content}
          </Text>
        )}
        {bubble.isStreaming && !isEmpty && (
          <View style={styles.streamingIndicator} />
        )}
      </View>
    </View>
  );
}

// ─── Suggested question chip ──────────────────────────────────────────────────

function QuestionChip({
  label,
  onPress,
  disabled,
}: {
  label: string;
  onPress: () => void;
  disabled: boolean;
}) {
  return (
    <Pressable
      style={({ pressed }) => [
        styles.chip,
        pressed && styles.chipPressed,
        disabled && styles.chipDisabled,
      ]}
      onPress={onPress}
      disabled={disabled}
    >
      <Text style={styles.chipText} numberOfLines={2}>
        {label}
      </Text>
    </Pressable>
  );
}

// ─── Main screen ──────────────────────────────────────────────────────────────

export default function AIAssistantScreen({ route, navigation }: Props) {
  const { t } = useTranslation();
  const p = route.params;

  // Normalize params at the boundary
  const topic = normalizeString(p.topic, "");
  const validModes = ["article_insight", "daily_brief", "simple_qa"] as const;
  const mode = validModes.includes(p.mode as (typeof validModes)[number])
    ? (p.mode as (typeof validModes)[number])
    : ("article_insight" as const);
  const rawArticle = p.article;
  const article: AIChatArticle = {
    title: normalizeString(rawArticle?.title, ""),
    url: normalizeString(rawArticle?.url, ""),
    source: normalizeNullableString(rawArticle?.source) ?? "",
    topic: normalizeString(rawArticle?.topic ?? topic, ""),
    summary: "",
    why_it_matters: "",
  };

  const today = new Date().toISOString().split("T")[0];

  const { bubbles, suggestedQuestions, isStreaming, error, sendMessage, retry } =
    useAIChat(article, today);

  const [inputText, setInputText] = useState("");
  const listRef = useRef<FlatList<ChatBubble>>(null);

  // Auto-scroll when new bubbles arrive
  useEffect(() => {
    if (bubbles.length > 0) {
      setTimeout(() => {
        listRef.current?.scrollToEnd({ animated: true });
      }, 50);
    }
  }, [bubbles.length]);

  const handleSend = useCallback(() => {
    const text = inputText.trim();
    if (!text) return;
    setInputText("");
    sendMessage(text);
  }, [inputText, sendMessage]);

  const handleChip = useCallback(
    (question: string) => {
      sendMessage(question);
    },
    [sendMessage],
  );

  const contextTitle =
    article.title || (topic ? t("aiAssistant.topicBriefing", { topic }) : t("aiAssistant.article"));
  const displayMode = mode.replace(/_/g, " ");

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 0 : 0}
    >
      <StatusBar barStyle="dark-content" backgroundColor={colors.bg} />

      {/* ── Header ── */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          activeOpacity={0.7}
          style={styles.backBtn}
          accessibilityRole="button"
          accessibilityLabel={t("common.back")}
        >
          <Text style={styles.backText}>{backArrow()} {t("common.back")}</Text>
        </TouchableOpacity>
        <View style={styles.headerCenter}>
          <Text style={styles.headerLabel}>WhatsNews AI</Text>
          <Text style={styles.headerMode}>{displayMode}</Text>
        </View>
        <View style={styles.headerRight} />
      </View>

      {/* ── Context pill ── */}
      <View style={styles.contextPill}>
        <Text style={styles.contextPillText} numberOfLines={1}>
          {contextTitle}
        </Text>
      </View>

      {/* ── Chat list ── */}
      {bubbles.length === 0 && !error ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator color={colors.accent} size="small" />
          <Text style={styles.loadingText}>{t("aiAssistant.generatingInsight")}</Text>
        </View>
      ) : error ? (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{t("common.error")}</Text>
          <Text style={styles.errorDetail}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={retry} activeOpacity={0.8}>
            <Text style={styles.retryText}>{t("aiAssistant.tryAgain")}</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          ref={listRef}
          data={bubbles}
          keyExtractor={(b) => b.id}
          renderItem={({ item }) => <Bubble bubble={item} />}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          onContentSizeChange={() =>
            listRef.current?.scrollToEnd({ animated: true })
          }
        />
      )}

      {/* ── Suggested question chips ── */}
      {suggestedQuestions.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.chipsScroll}
          contentContainerStyle={styles.chipsContent}
        >
          {suggestedQuestions.map((q) => (
            <QuestionChip
              key={q}
              label={q}
              onPress={() => handleChip(q)}
              disabled={isStreaming}
            />
          ))}
        </ScrollView>
      )}

      {/* ── Input bar ── */}
      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          value={inputText}
          onChangeText={setInputText}
          placeholder={t("aiAssistant.inputPlaceholder")}
          placeholderTextColor={colors.muted}
          multiline
          maxLength={500}
          editable={!isStreaming}
          returnKeyType="send"
          onSubmitEditing={handleSend}
          blurOnSubmit
        />
        <TouchableOpacity
          style={[styles.sendBtn, (isStreaming || !inputText.trim()) && styles.sendBtnDisabled]}
          onPress={handleSend}
          activeOpacity={0.8}
          disabled={isStreaming || !inputText.trim()}
        >
          {isStreaming ? (
            <ActivityIndicator color={colors.white} size="small" />
          ) : (
            <Text style={styles.sendBtnText}>↑</Text>
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingTop: spacing.screenPaddingTop,
    paddingHorizontal: spacing.screenPaddingH,
    paddingBottom: 12,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: { width: 60 },
  backText: {
    fontSize: 14,
    fontWeight: "500",
    color: colors.accent,
  },
  headerCenter: { flex: 1, alignItems: "center" },
  headerLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: colors.ink,
    letterSpacing: 0.3,
  },
  headerMode: {
    fontSize: 10,
    fontWeight: "600",
    color: colors.accent,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginTop: 2,
  },
  headerRight: { width: 60 },

  contextPill: {
    marginHorizontal: spacing.screenPaddingH,
    marginTop: 10,
    marginBottom: 4,
    backgroundColor: colors.wimSurface,
    borderRadius: radii.sm,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: colors.wimBorder,
  },
  contextPillText: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.wimText,
  },

  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  loadingText: {
    fontSize: 13,
    color: colors.muted,
  },

  errorContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.screenPaddingH,
    gap: 10,
  },
  errorText: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.danger,
  },
  errorDetail: {
    fontSize: 12,
    color: colors.muted,
    textAlign: "center",
  },
  retryBtn: {
    marginTop: 8,
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 24,
  },
  retryText: {
    fontSize: 14,
    fontWeight: "700",
    color: colors.white,
  },

  listContent: {
    paddingHorizontal: spacing.screenPaddingH,
    paddingTop: 12,
    paddingBottom: 8,
    gap: 12,
  },

  bubbleRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "flex-end",
  },
  bubbleRowUser: { justifyContent: "flex-end" },
  bubbleRowAssistant: { justifyContent: "flex-start" },

  avatarDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.accentSoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 2,
  },
  avatarText: {
    fontSize: 8,
    fontWeight: "800",
    color: colors.accent,
    letterSpacing: 0.5,
  },

  bubble: {
    maxWidth: "80%",
    borderRadius: radii.lg,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  bubbleUser: {
    backgroundColor: colors.accent,
    borderBottomRightRadius: 4,
  },
  bubbleAssistant: {
    backgroundColor: colors.white,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bubbleTextUser: {
    fontSize: 14,
    color: colors.white,
    lineHeight: 20,
  },
  bubbleTextAssistant: {
    fontSize: 14,
    color: colors.ink,
    lineHeight: 21,
  },

  typingDots: {
    fontSize: 18,
    color: colors.muted,
    letterSpacing: 2,
    minWidth: 36,
  },

  streamingIndicator: {
    marginTop: 6,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.accent,
    opacity: 0.6,
  },

  chipsScroll: {
    flexGrow: 0,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  chipsContent: {
    paddingHorizontal: spacing.screenPaddingH,
    paddingVertical: 10,
    gap: 8,
  },
  chip: {
    backgroundColor: colors.wimSurface,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: colors.wimBorder,
    maxWidth: 220,
  },
  chipPressed: {
    backgroundColor: colors.accentSoft,
  },
  chipDisabled: {
    opacity: 0.4,
  },
  chipText: {
    fontSize: 12,
    fontWeight: "500",
    color: colors.accent,
  },

  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 10,
    paddingHorizontal: spacing.screenPaddingH,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.white,
  },
  input: {
    flex: 1,
    backgroundColor: colors.bg,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: Platform.OS === "ios" ? 10 : 8,
    fontSize: 14,
    color: colors.ink,
    maxHeight: 100,
    borderWidth: 1,
    borderColor: colors.border,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  sendBtnDisabled: {
    backgroundColor: colors.surfaceMuted,
  },
  sendBtnText: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.white,
  },
});
