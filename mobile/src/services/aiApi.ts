/**
 * AI chat API service — streaming SSE client for POST /ai/chat.
 *
 * The frontend never knows which model responded. All model selection
 * happens inside the backend AI Gateway.
 */

import { API_BASE_URL } from "../config";
import { getDeviceId } from "../utils/deviceId";

export type AIChatArticle = {
  title: string;
  url: string;
  source: string;
  topic: string;
  summary: string;
  why_it_matters: string;
  body_text?: string; // Added 2026-07-05 (Phase 32) for full-article translation
};

export type AIChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type AIMode =
  | "article_insight"
  | "daily_brief"
  | "cross_topic"
  | "market_analysis"
  | "research"
  | "translation"
  | "social_media"
  | "newsletter";

export type AIChatRequest = {
  article: AIChatArticle;
  messages: AIChatMessage[];
  mode: AIMode;
  date?: string; // YYYY-MM-DD
  language?: string;
};

export type AIChatDoneMeta = {
  model: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
};

type SSEEvent =
  | { type: "delta"; text: string }
  | { type: "questions"; questions: string[] }
  | { type: "done"; model: string; input_tokens: number; output_tokens: number; latency_ms: number }
  | { type: "error"; message: string };

function parseSseLine(line: string): SSEEvent | null {
  if (!line.startsWith("data: ")) return null;
  const data = line.slice(6).trim();
  if (data === "[DONE]") return null;
  try {
    return JSON.parse(data) as SSEEvent;
  } catch {
    return null;
  }
}

/**
 * Streams an AI chat request and calls callbacks for each event type.
 *
 * Returns a cleanup function that can be called to abort the stream.
 * Call it on component unmount to avoid state updates after unmount.
 */
export function streamAIChat(
  request: AIChatRequest,
  callbacks: {
    onDelta: (text: string) => void;
    onQuestions: (questions: string[]) => void;
    onDone: (meta: AIChatDoneMeta) => void;
    onError: (message: string) => void;
  },
): () => void {
  const abortController = new AbortController();

  void (async () => {
    try {
      const deviceId = await getDeviceId();
      const response = await fetch(`${API_BASE_URL}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Device-Id": deviceId },
        body: JSON.stringify(request),
        signal: abortController.signal,
      });

      if (response.status === 429) {
        const retryAfter = response.headers.get("Retry-After");
        callbacks.onError(
          retryAfter
            ? `You've reached the AI chat limit. Try again in ${Math.ceil(Number(retryAfter) / 60)} min.`
            : "You've reached the AI chat limit. Please try again later.",
        );
        return;
      }

      if (!response.ok) {
        callbacks.onError(`Server error ${response.status}`);
        return;
      }

      if (!response.body) {
        // Fallback: read full body if streaming is unavailable
        const text = await response.text();
        for (const line of text.split("\n")) {
          const event = parseSseLine(line);
          if (!event) continue;
          if (event.type === "delta") callbacks.onDelta(event.text);
          if (event.type === "questions") callbacks.onQuestions(event.questions);
          if (event.type === "done") callbacks.onDone(event);
          if (event.type === "error") callbacks.onError(event.message);
        }
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const event = parseSseLine(line);
          if (!event) continue;
          if (event.type === "delta") callbacks.onDelta(event.text);
          if (event.type === "questions") callbacks.onQuestions(event.questions);
          if (event.type === "done") callbacks.onDone(event);
          if (event.type === "error") callbacks.onError(event.message);
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      callbacks.onError(err instanceof Error ? err.message : "Network error");
    }
  })();

  return () => abortController.abort();
}
