import { act, renderHook, waitFor } from "@testing-library/react-native";
import { useOnDeviceTranslation } from "../useOnDeviceTranslation";
import { translateFieldsFromEnglish } from "../../utils/onDeviceTranslation";

// This hook's own job is request-sequencing (races, English no-op, the
// "View original" toggle) — the underlying native translation call itself
// is covered separately by mocking at this module boundary, the same way
// useSpeechPlayback.test.ts mocks expo-speech rather than re-testing
// expo-speech's own internals.
jest.mock("../../utils/onDeviceTranslation", () => ({
  translateFieldsFromEnglish: jest.fn(),
}));

let mockLanguage = "en";
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { get language() { return mockLanguage; } } }),
}));

const mockTranslate = translateFieldsFromEnglish as jest.MockedFunction<
  typeof translateFieldsFromEnglish
>;

describe("useOnDeviceTranslation", () => {
  beforeEach(() => {
    mockLanguage = "en";
    mockTranslate.mockReset();
  });

  it("no-ops entirely when the UI language is English", async () => {
    const { result } = renderHook(() => useOnDeviceTranslation({ summary: "Hello" }));

    expect(result.current.fields).toEqual({ summary: "Hello" });
    expect(result.current.isTranslated).toBe(false);
    expect(result.current.isTranslating).toBe(false);
    expect(mockTranslate).not.toHaveBeenCalled();
  });

  it("translates the fields when the UI language is non-English", async () => {
    mockLanguage = "es";
    mockTranslate.mockResolvedValue({ summary: "Hola" });

    const { result } = renderHook(() => useOnDeviceTranslation({ summary: "Hello" }));

    expect(result.current.isTranslating).toBe(true);
    await waitFor(() => expect(result.current.isTranslated).toBe(true));

    expect(result.current.fields).toEqual({ summary: "Hola" });
    expect(result.current.isTranslating).toBe(false);
    expect(mockTranslate).toHaveBeenCalledWith({ summary: "Hello" }, "es");
  });

  it("falls back to the original fields when translation fails/returns null", async () => {
    mockLanguage = "fr";
    mockTranslate.mockResolvedValue(null);

    const { result } = renderHook(() => useOnDeviceTranslation({ summary: "Hello" }));

    await waitFor(() => expect(result.current.isTranslating).toBe(false));

    expect(result.current.isTranslated).toBe(false);
    expect(result.current.fields).toEqual({ summary: "Hello" });
  });

  it("toggleShowOriginal flips back to the English fields and back again", async () => {
    mockLanguage = "ja";
    mockTranslate.mockResolvedValue({ summary: "Konnichiwa" });

    const { result } = renderHook(() => useOnDeviceTranslation({ summary: "Hello" }));
    await waitFor(() => expect(result.current.isTranslated).toBe(true));

    act(() => result.current.toggleShowOriginal());
    expect(result.current.showingOriginal).toBe(true);
    expect(result.current.fields).toEqual({ summary: "Hello" });

    act(() => result.current.toggleShowOriginal());
    expect(result.current.showingOriginal).toBe(false);
    expect(result.current.fields).toEqual({ summary: "Konnichiwa" });
  });

  it("ignores a stale in-flight request when fields change before it resolves", async () => {
    mockLanguage = "es";
    let resolveFirst!: (v: { summary: string } | null) => void;
    const first = new Promise<{ summary: string } | null>((resolve) => {
      resolveFirst = resolve;
    });
    mockTranslate.mockReturnValueOnce(first);
    mockTranslate.mockResolvedValueOnce({ summary: "Segundo" });

    const { result, rerender } = renderHook(
      ({ fields }: { fields: { summary: string } }) => useOnDeviceTranslation(fields),
      { initialProps: { fields: { summary: "First" } } },
    );

    rerender({ fields: { summary: "Second" } });
    await waitFor(() => expect(result.current.isTranslated).toBe(true));
    expect(result.current.fields).toEqual({ summary: "Segundo" });

    // The stale first request resolving afterward must not clobber the
    // second, already-applied translation.
    act(() => resolveFirst({ summary: "Primero" }));
    await Promise.resolve();
    expect(result.current.fields).toEqual({ summary: "Segundo" });
  });
});
