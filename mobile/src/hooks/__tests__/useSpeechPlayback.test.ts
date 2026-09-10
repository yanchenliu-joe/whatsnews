import { act, renderHook } from "@testing-library/react-native";
import { Platform } from "react-native";
import * as Speech from "expo-speech";
import { useSpeechPlayback } from "../useSpeechPlayback";

// expo-speech is a native module with no jest-expo built-in mock (unlike
// expo-localization/expo-constants) — this is the first test in the repo
// to mock it. Every method returns a promise, matching the real API.
jest.mock("expo-speech", () => ({
  speak: jest.fn(),
  stop: jest.fn(() => Promise.resolve()),
  pause: jest.fn(() => Promise.resolve()),
  resume: jest.fn(() => Promise.resolve()),
}));

// expo-av (2026-07-13, background audio session setup) — same gap, no
// jest-expo built-in mock. Its real module calls requireNativeModule at
// import time, which throws in the test environment regardless of any
// runtime guard, same as expo-speech above.
jest.mock("expo-av", () => ({
  Audio: { setAudioModeAsync: jest.fn(() => Promise.resolve()) },
  InterruptionModeIOS: { DoNotMix: 1 },
  InterruptionModeAndroid: { DoNotMix: 1 },
}));

const mockSpeak = Speech.speak as jest.MockedFunction<typeof Speech.speak>;
const mockStop = Speech.stop as jest.MockedFunction<typeof Speech.stop>;
const mockPause = Speech.pause as jest.MockedFunction<typeof Speech.pause>;
const mockResume = Speech.resume as jest.MockedFunction<typeof Speech.resume>;

// expo-speech's own SpeechOptions types onStart/onStopped/onDone/onBoundary
// as `void | SpeechEventCallback` unions carrying a web-only `this:
// SpeechSynthesisUtterance` context, which doesn't match how the hook
// under test actually invokes them (plain zero/one-arg calls, matching
// the "Native-only callback" shape expo-speech's own docs describe for
// iOS/Android). Re-typed locally to what's actually called at runtime,
// rather than fighting that union at every call site below.
type TestSpeakOptions = {
  rate?: number;
  language?: string;
  onStart?: () => void;
  onStopped?: () => void;
  onDone?: () => void;
  onError?: (error?: Error) => void;
  onBoundary?: (ev: { charIndex: number; charLength: number }) => void;
};

function lastSpeakOptions(): TestSpeakOptions {
  const call = mockSpeak.mock.calls[mockSpeak.mock.calls.length - 1];
  return call[1] as TestSpeakOptions;
}

function lastSpeakText(): string {
  const call = mockSpeak.mock.calls[mockSpeak.mock.calls.length - 1];
  return call[0];
}

describe("useSpeechPlayback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Platform.OS = "ios";
  });

  it("canPlay is false with no text and true once text is provided", () => {
    const { result, rerender } = renderHook(
      ({ text }: { text: string | null }) => useSpeechPlayback({ text }),
      { initialProps: { text: null } },
    );
    expect(result.current.canPlay).toBe(false);

    rerender({ text: "Hello world" });
    expect(result.current.canPlay).toBe(true);
  });

  it("play() speaks the full text from the start and onStart flips isPlaying", () => {
    const { result } = renderHook(() =>
      useSpeechPlayback({ text: "Hello world, this is a briefing." }),
    );

    act(() => {
      result.current.togglePlayPause();
    });

    expect(mockSpeak).toHaveBeenCalledTimes(1);
    expect(lastSpeakText()).toBe("Hello world, this is a briefing.");
    expect(lastSpeakOptions().rate).toBe(1);

    act(() => {
      lastSpeakOptions().onStart?.();
    });
    expect(result.current.isPlaying).toBe(true);
    expect(result.current.isPaused).toBe(false);
  });

  it("onBoundary advances progressRatio proportionally to text length", () => {
    const text = "0123456789"; // 10 chars, easy fractions
    const { result } = renderHook(() => useSpeechPlayback({ text }));

    act(() => {
      result.current.togglePlayPause();
    });
    act(() => {
      lastSpeakOptions().onBoundary?.({ charIndex: 5, charLength: 1 });
    });

    expect(result.current.progressRatio).toBeCloseTo(0.5);
  });

  it("onDone completes progress to 1 and stops playing", () => {
    const { result } = renderHook(() => useSpeechPlayback({ text: "short text" }));

    act(() => {
      result.current.togglePlayPause();
    });
    act(() => {
      lastSpeakOptions().onDone?.();
    });

    expect(result.current.progressRatio).toBe(1);
    expect(result.current.isPlaying).toBe(false);
  });

  it("onError surfaces a friendly message and stops playing", () => {
    const { result } = renderHook(() => useSpeechPlayback({ text: "short text" }));

    act(() => {
      result.current.togglePlayPause();
    });
    act(() => {
      lastSpeakOptions().onError?.();
    });

    expect(result.current.isPlaying).toBe(false);
    expect(result.current.isPaused).toBe(false);
    expect(result.current.error).toMatch(/couldn't read this aloud/i);
  });

  describe("iOS pause/resume — uses the real native pause/resume API", () => {
    it("pause() calls Speech.pause(), not Speech.stop()", async () => {
      const { result } = renderHook(() => useSpeechPlayback({ text: "hello" }));
      // The reset-on-text-change effect also fires once on initial mount,
      // calling Speech.stop() before any play/pause under test happens.
      mockStop.mockClear();

      act(() => {
        result.current.togglePlayPause();
      });
      act(() => {
        lastSpeakOptions().onStart?.();
      });

      await act(async () => {
        await result.current.togglePlayPause();
      });

      expect(mockPause).toHaveBeenCalledTimes(1);
      expect(mockStop).not.toHaveBeenCalled();
      expect(result.current.isPaused).toBe(true);
      expect(result.current.isPlaying).toBe(false);
    });

    it("resume() calls Speech.resume(), not a fresh Speech.speak()", async () => {
      const { result } = renderHook(() => useSpeechPlayback({ text: "hello" }));

      act(() => {
        result.current.togglePlayPause(); // play
      });
      act(() => {
        lastSpeakOptions().onStart?.();
      });
      await act(async () => {
        await result.current.togglePlayPause(); // pause
      });
      mockSpeak.mockClear();

      await act(async () => {
        await result.current.togglePlayPause(); // resume
      });

      expect(mockResume).toHaveBeenCalledTimes(1);
      expect(mockSpeak).not.toHaveBeenCalled();
      expect(result.current.isPlaying).toBe(true);
      expect(result.current.isPaused).toBe(false);
    });
  });

  describe("Android pause/resume — expo-speech has no native pause API on Android", () => {
    beforeEach(() => {
      Platform.OS = "android";
    });

    it("pause() calls Speech.stop() and remembers the character position", async () => {
      const text = "0123456789";
      const { result } = renderHook(() => useSpeechPlayback({ text }));
      mockStop.mockClear(); // clear the initial-mount reset-effect call

      act(() => {
        result.current.togglePlayPause(); // play
      });
      act(() => {
        lastSpeakOptions().onStart?.();
      });
      act(() => {
        lastSpeakOptions().onBoundary?.({ charIndex: 4, charLength: 1 });
      });

      await act(async () => {
        await result.current.togglePlayPause(); // pause
      });

      expect(mockStop).toHaveBeenCalledTimes(1);
      expect(mockPause).not.toHaveBeenCalled();
      expect(result.current.isPaused).toBe(true);
    });

    it("resume() re-speaks only the remaining text from the remembered position", async () => {
      const text = "0123456789";
      const { result } = renderHook(() => useSpeechPlayback({ text }));

      act(() => {
        result.current.togglePlayPause(); // play
      });
      act(() => {
        lastSpeakOptions().onStart?.();
      });
      act(() => {
        lastSpeakOptions().onBoundary?.({ charIndex: 4, charLength: 1 });
      });
      await act(async () => {
        await result.current.togglePlayPause(); // pause (Speech.stop())
      });
      mockSpeak.mockClear();

      act(() => {
        result.current.togglePlayPause(); // resume
      });

      expect(mockResume).not.toHaveBeenCalled();
      expect(mockSpeak).toHaveBeenCalledTimes(1);
      // The hook's onBoundary reports charIndex relative to the segment
      // spoken so far (index 0 at play time), so absoluteIndex === 4 —
      // resume must re-speak text.slice(4), not the full string again.
      expect(lastSpeakText()).toBe(text.slice(4));
    });
  });

  it("stop() resets progress and playback state", async () => {
    const { result } = renderHook(() => useSpeechPlayback({ text: "hello world" }));

    act(() => {
      result.current.togglePlayPause();
    });
    act(() => {
      lastSpeakOptions().onStart?.();
    });
    act(() => {
      lastSpeakOptions().onBoundary?.({ charIndex: 5, charLength: 1 });
    });

    await act(async () => {
      await result.current.stop();
    });

    expect(mockStop).toHaveBeenCalled();
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.isPaused).toBe(false);
    expect(result.current.progressRatio).toBe(0);
  });

  it("changing the text resets playback state and stops any in-flight speech", () => {
    const { result, rerender } = renderHook(
      ({ text }: { text: string }) => useSpeechPlayback({ text }),
      { initialProps: { text: "first narrative" } },
    );

    act(() => {
      result.current.togglePlayPause();
    });
    act(() => {
      lastSpeakOptions().onStart?.();
    });
    expect(result.current.isPlaying).toBe(true);

    mockStop.mockClear();
    rerender({ text: "second, fresher narrative" });

    expect(mockStop).toHaveBeenCalled();
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.progressRatio).toBe(0);
  });

  it("setRate mid-playback stops and restarts speech at the new rate from the current position", async () => {
    const text = "0123456789";
    const { result } = renderHook(() => useSpeechPlayback({ text }));

    act(() => {
      result.current.togglePlayPause();
    });
    act(() => {
      lastSpeakOptions().onStart?.();
    });
    act(() => {
      lastSpeakOptions().onBoundary?.({ charIndex: 3, charLength: 1 });
    });
    mockSpeak.mockClear();

    await act(async () => {
      await result.current.setRate(1.5);
    });

    expect(mockStop).toHaveBeenCalled();
    expect(mockSpeak).toHaveBeenCalledTimes(1);
    expect(lastSpeakText()).toBe(text.slice(3));
    expect(lastSpeakOptions().rate).toBe(1.5);
    expect(result.current.playbackRate).toBe(1.5);
  });

  it("passes the given BCP-47 language to Speech.speak, defaulting to en-US", () => {
    const { result, rerender } = renderHook(
      ({ language }: { language?: string }) =>
        useSpeechPlayback({ text: "hola", language }),
      { initialProps: { language: undefined as string | undefined } },
    );

    act(() => {
      result.current.togglePlayPause();
    });
    expect(lastSpeakOptions().language).toBe("en-US");

    act(() => {
      lastSpeakOptions().onStopped?.();
    });
    rerender({ language: "es-ES" });
    act(() => {
      result.current.togglePlayPause();
    });
    expect(lastSpeakOptions().language).toBe("es-ES");
  });
});
