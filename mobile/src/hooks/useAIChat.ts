/**
 * useAIChat — manages the full AI assistant session state.
 *
 * On mount: immediately requests the proactive "Today's Insight" from the
 * backend (empty messages → AI generates initial context).
 *
 * On sendMessage: appends the user message, streams the assistant response,
 * accumulates delta chunks into the last assistant bubble.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AIChatArticle,
  AIChatDoneMeta,
  AIChatMessage,
  streamAIChat,
} from "../services/aiApi";

export type ChatBubble = {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
};

let _bubbleCounter = 0;
function nextId() {
  _bubbleCounter += 1;
  return `bubble_${_bubbleCounter}`;
}

export function useAIChat(article: AIChatArticle, dateStr?: string) {
  const [bubbles, setBubbles] = useState<ChatBubble[]>([]);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasInsight, setHasInsight] = useState(false);

  // Keep a ref to conversation history for the API (non-rendered format)
  const historyRef = useRef<AIChatMessage[]>([]);
  // Cleanup function for the current stream
  const cleanupRef = useRef<(() => void) | null>(null);

  const cancelStream = useCallback(() => {
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }
  }, []);

  // ─── Streaming core ──────────────────────────────────────────────────────────

  const startStream = useCallback(
    (userQuestion: string | null) => {
      cancelStream();
      setError(null);
      setIsStreaming(true);

      // Add user bubble immediately (skip for the initial insight call)
      if (userQuestion !== null) {
        const userBubble: ChatBubble = {
          id: nextId(),
          role: "user",
          content: userQuestion,
        };
        setBubbles((prev) => [...prev, userBubble]);
        historyRef.current = [
          ...historyRef.current,
          { role: "user", content: userQuestion },
        ];
      }

      // Placeholder assistant bubble for streaming
      const assistantId = nextId();
      setBubbles((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "", isStreaming: true },
      ]);

      let accumulated = "";

      const cleanup = streamAIChat(
        {
          article,
          messages: historyRef.current.slice(-20), // cap context window
          mode: "article_insight",
          date: dateStr,
        },
        {
          onDelta: (text) => {
            accumulated += text;
            setBubbles((prev) =>
              prev.map((b) =>
                b.id === assistantId ? { ...b, content: accumulated } : b,
              ),
            );
          },
          onQuestions: (questions) => {
            setSuggestedQuestions(questions);
          },
          onDone: (_meta: AIChatDoneMeta) => {
            setBubbles((prev) =>
              prev.map((b) =>
                b.id === assistantId ? { ...b, isStreaming: false } : b,
              ),
            );
            historyRef.current = [
              ...historyRef.current,
              { role: "assistant", content: accumulated },
            ];
            setIsStreaming(false);
            if (userQuestion === null) setHasInsight(true);
          },
          onError: (message) => {
            setError(message);
            setBubbles((prev) => prev.filter((b) => b.id !== assistantId));
            setIsStreaming(false);
          },
        },
      );

      cleanupRef.current = cleanup;
    },
    [article, dateStr, cancelStream],
  );

  // ─── Initial insight on mount ────────────────────────────────────────────────

  useEffect(() => {
    if (!hasInsight) {
      startStream(null);
    }
    return cancelStream;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Public API ──────────────────────────────────────────────────────────────

  const sendMessage = useCallback(
    (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || isStreaming) return;
      startStream(trimmed);
    },
    [isStreaming, startStream],
  );

  const retry = useCallback(() => {
    setError(null);
    if (!hasInsight) {
      historyRef.current = [];
      setBubbles([]);
      setSuggestedQuestions([]);
      startStream(null);
    }
  }, [hasInsight, startStream]);

  return {
    bubbles,
    suggestedQuestions,
    isStreaming,
    error,
    sendMessage,
    retry,
  };
}
