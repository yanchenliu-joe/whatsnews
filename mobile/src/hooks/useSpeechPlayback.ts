import { useCallback, useEffect, useRef, useState } from "react";
import { Platform } from "react-native";
import { Audio, InterruptionModeAndroid, InterruptionModeIOS } from "expo-av";
import * as Speech from "expo-speech";

// Not exported from expo-speech's public entry point, so declared locally
// to type the onBoundary callback below.
type BoundaryEvent = { charIndex: number; charLength: number };

// Narrative script_text is authored in English server-side; when on-device
// translation (2026-07-13, see useOnDeviceTranslation.ts) produces a
// translated script, callers pass the matching BCP-47 locale here so the
// OS speech engine reads it in the right language/voice instead of an
// English voice misreading foreign text.
const DEFAULT_SPEECH_LANGUAGE = "en-US";

const RATE_OPTIONS = [0.5, 1, 1.5, 2] as const;

// Background playback (2026-07-13) — scoped deliberately to "keeps talking
// when the screen locks," not full lock-screen Now Playing controls (a
// separate, much bigger feature: MPNowPlayingInfoCenter/RemoteCommandCenter
// only ever bind to a real playable audio file/URL, and expo-speech has no
// "synthesize to file" API — see the "Morning Brief background playback"
// note in docs/ENGINEERING.md for the full tradeoff). `expo-av` is already a listed
// dependency (orphaned since the old server-MP3 player was removed in the
// free-version pivot, no JS import anywhere) — reused here purely for
// `Audio.setAudioModeAsync()`'s OS-level audio-session configuration, not
// for its own playback APIs. `staysActiveInBackground` only takes effect in
// a real build (not Expo Go) and requires `UIBackgroundModes: ["audio"]` in
// app.json, per expo-av's own docs.
let backgroundAudioSessionConfigured = false;

async function ensureBackgroundAudioSession(): Promise<void> {
  if (backgroundAudioSessionConfigured) return;
  backgroundAudioSessionConfigured = true;
  try {
    await Audio.setAudioModeAsync({
      staysActiveInBackground: true,
      playsInSilentModeIOS: true,
      interruptionModeIOS: InterruptionModeIOS.DoNotMix,
      shouldDuckAndroid: false,
      interruptionModeAndroid: InterruptionModeAndroid.DoNotMix,
    });
  } catch {
    // Best-effort — a failure here just means playback stops when the
    // screen locks (the pre-existing behavior), not a crash.
    backgroundAudioSessionConfigured = false;
  }
}

type UseSpeechPlaybackOptions = {
  text: string | null;
  language?: string;
};

/**
 * On-device text-to-speech playback (2026-07-10) — replaces the old
 * server-generated-MP3 model (useVoicePlayback.ts) to remove per-briefing
 * OpenAI TTS cost. Reads the already-generated (free, rule-based) narrative
 * script text aloud using the OS's own speech engine via expo-speech.
 *
 * Real platform gap: Speech.pause()/resume() are iOS-only ("not available
 * on Android" per expo-speech's own docs). Worked around by tracking the
 * character index reached (via onBoundary) and, on Android, treating
 * "pause" as stop + remembered position, "resume" as re-speaking the
 * remaining text slice from that position — an approximate resume, not a
 * true pause, but avoids restarting from the beginning.
 *
 * No arbitrary seek/scrub (the old SeekableProgressBar + skip ±10s) — the
 * OS speech engine has no equivalent capability, only play from a given
 * character offset onward.
 */
export function useSpeechPlayback({ text, language }: UseSpeechPlaybackOptions) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [progressRatio, setProgressRatio] = useState(0);
  const [rate, setRateState] = useState<number>(1);
  const [error, setError] = useState<string | null>(null);

  const textRef = useRef(text);
  const languageRef = useRef(language ?? DEFAULT_SPEECH_LANGUAGE);
  const charIndexRef = useRef(0);
  const totalLengthRef = useRef(text?.length ?? 0);

  useEffect(() => {
    textRef.current = text;
    totalLengthRef.current = text?.length ?? 0;
  }, [text]);

  useEffect(() => {
    languageRef.current = language ?? DEFAULT_SPEECH_LANGUAGE;
  }, [language]);

  // Reset playback state whenever the underlying text or speech language
  // changes (e.g. topic switch, a fresher narrative version loads in, or a
  // translated script arrives asynchronously after the English original).
  useEffect(() => {
    void Speech.stop();
    charIndexRef.current = 0;
    setIsPlaying(false);
    setIsPaused(false);
    setProgressRatio(0);
    setError(null);
  }, [text, language]);

  useEffect(() => {
    return () => {
      void Speech.stop();
    };
  }, []);

  const speakFrom = useCallback((startCharIndex: number, speechRate: number) => {
    const full = textRef.current;
    if (!full) return;
    const segment = full.slice(startCharIndex);
    if (!segment.trim()) return;

    // Configure the shared audio session for background playback before
    // this utterance starts — useApplicationAudioSession below tells
    // AVSpeechSynthesizer to use that session instead of its own private
    // one, which is what actually makes staysActiveInBackground apply to
    // speech playback (confirmed by reading expo-speech's iOS native
    // source, SpeechModule.swift).
    void ensureBackgroundAudioSession();

    Speech.speak(segment, {
      language: languageRef.current,
      rate: speechRate,
      useApplicationAudioSession: true,
      onStart: () => {
        setIsPlaying(true);
        setIsPaused(false);
        setError(null);
      },
      onDone: () => {
        charIndexRef.current = totalLengthRef.current;
        setIsPlaying(false);
        setIsPaused(false);
        setProgressRatio(1);
      },
      onStopped: () => {
        setIsPlaying(false);
      },
      onError: () => {
        setIsPlaying(false);
        setIsPaused(false);
        setError("Couldn't read this aloud. Try again.");
      },
      onBoundary: (ev: BoundaryEvent) => {
        const absoluteIndex = startCharIndex + ev.charIndex;
        charIndexRef.current = absoluteIndex;
        const total = totalLengthRef.current;
        if (total > 0) setProgressRatio(Math.min(1, absoluteIndex / total));
      },
    });
  }, []);

  const play = useCallback(() => {
    if (!textRef.current) return;
    charIndexRef.current = 0;
    setProgressRatio(0);
    speakFrom(0, rate);
  }, [speakFrom, rate]);

  const pause = useCallback(async () => {
    if (Platform.OS === "android") {
      await Speech.stop();
      setIsPlaying(false);
      setIsPaused(true);
    } else {
      await Speech.pause();
      setIsPlaying(false);
      setIsPaused(true);
    }
  }, []);

  const resume = useCallback(async () => {
    if (Platform.OS === "android") {
      speakFrom(charIndexRef.current, rate);
    } else {
      await Speech.resume();
      setIsPlaying(true);
      setIsPaused(false);
    }
  }, [speakFrom, rate]);

  const stop = useCallback(async () => {
    await Speech.stop();
    charIndexRef.current = 0;
    setIsPlaying(false);
    setIsPaused(false);
    setProgressRatio(0);
  }, []);

  const togglePlayPause = useCallback(async () => {
    if (!textRef.current) return;
    if (isPlaying) {
      await pause();
    } else if (isPaused) {
      await resume();
    } else {
      play();
    }
  }, [isPlaying, isPaused, pause, resume, play]);

  // Changing rate mid-speech has no live-adjustment API — restart from the
  // current position at the new rate, same approach on both platforms.
  const setRate = useCallback(
    async (newRate: number) => {
      setRateState(newRate);
      if (isPlaying || isPaused) {
        await Speech.stop();
        speakFrom(charIndexRef.current, newRate);
      }
    },
    [isPlaying, isPaused, speakFrom],
  );

  return {
    isPlaying,
    isPaused,
    progressRatio,
    playbackRate: rate,
    error,
    canPlay: Boolean(text),
    togglePlayPause,
    stop,
    setRate,
  };
}

export { RATE_OPTIONS as SPEECH_RATE_OPTIONS };
