/**
 * Reading font size preference (Phase 32, added 2026-07-05).
 * Global, persisted, app-wide — set from ArticleToolsSheet, applied wherever
 * article body/summary text renders.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { READING_FONT_SIZE_KEY } from "../config";

export type FontSizeOption = "S" | "M" | "L";

export const FONT_SIZE_SCALE: Record<FontSizeOption, number> = {
  S: 0.875,
  M: 1,
  L: 1.2,
};

type ReadingSettingsState = {
  fontSize: FontSizeOption;
  fontScale: number;
  setFontSize: (size: FontSizeOption) => void;
};

const ReadingSettingsContext = createContext<ReadingSettingsState>({
  fontSize: "M",
  fontScale: 1,
  setFontSize: () => {},
});

export function useReadingSettings(): ReadingSettingsState {
  return useContext(ReadingSettingsContext);
}

function isFontSizeOption(value: unknown): value is FontSizeOption {
  return value === "S" || value === "M" || value === "L";
}

export function ReadingSettingsProvider({ children }: { children: ReactNode }) {
  const [fontSize, setFontSizeState] = useState<FontSizeOption>("M");

  useEffect(() => {
    AsyncStorage.getItem(READING_FONT_SIZE_KEY)
      .then((stored) => {
        if (isFontSizeOption(stored)) setFontSizeState(stored);
      })
      .catch(() => {
        // non-fatal — default to Medium
      });
  }, []);

  const setFontSize = useCallback((size: FontSizeOption) => {
    setFontSizeState(size);
    void AsyncStorage.setItem(READING_FONT_SIZE_KEY, size);
  }, []);

  return (
    <ReadingSettingsContext.Provider
      value={{ fontSize, fontScale: FONT_SIZE_SCALE[fontSize], setFontSize }}
    >
      {children}
    </ReadingSettingsContext.Provider>
  );
}
