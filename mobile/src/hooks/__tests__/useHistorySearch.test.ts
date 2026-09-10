import { act, renderHook } from "@testing-library/react-native";
import { useHistorySearch } from "../useHistorySearch";
import { fetchHistorySearch } from "../../services/historyApi";

jest.mock("../../services/historyApi", () => ({
  fetchHistorySearch: jest.fn(),
}));

jest.mock("../../services/analytics", () => ({
  trackEvent: jest.fn(),
}));

const mockFetchHistorySearch = fetchHistorySearch as jest.MockedFunction<
  typeof fetchHistorySearch
>;

const DEBOUNCE_MS = 400;

function resultOf(query: string) {
  return {
    query,
    limit: 20,
    offset: 0,
    results: [
      {
        title: `Result for ${query}`,
        snippet: "snippet",
        source: "Reuters",
        url: "https://example.com/a",
        topic: "Technology",
        topic_id: 1,
        report_date: "2026-07-13",
        why_it_matters: "",
        image_url: null,
      },
    ],
    total: 1,
  };
}

describe("useHistorySearch", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockFetchHistorySearch.mockReset();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("does not enter search mode below the minimum query length", () => {
    const { result } = renderHook(() => useHistorySearch());

    act(() => {
      result.current.setQuery("ab");
    });
    act(() => {
      jest.advanceTimersByTime(DEBOUNCE_MS);
    });

    expect(result.current.isSearchMode).toBe(false);
    expect(result.current.isTyping).toBe(true);
    expect(mockFetchHistorySearch).not.toHaveBeenCalled();
  });

  it("fetches only after the debounce window elapses", async () => {
    mockFetchHistorySearch.mockResolvedValue(resultOf("abc"));
    const { result } = renderHook(() => useHistorySearch());

    act(() => {
      result.current.setQuery("abc");
    });
    expect(mockFetchHistorySearch).not.toHaveBeenCalled();

    await act(async () => {
      jest.advanceTimersByTime(DEBOUNCE_MS);
      await Promise.resolve();
    });

    expect(mockFetchHistorySearch).toHaveBeenCalledWith("abc");
    expect(result.current.isSearchMode).toBe(true);
    expect(result.current.results).toHaveLength(1);
    expect(result.current.total).toBe(1);
    expect(result.current.loading).toBe(false);
  });

  it("re-typing the same already-fetched query does not refetch", async () => {
    mockFetchHistorySearch.mockResolvedValue(resultOf("abc"));
    const { result } = renderHook(() => useHistorySearch());

    act(() => {
      result.current.setQuery("abc");
    });
    await act(async () => {
      jest.advanceTimersByTime(DEBOUNCE_MS);
      await Promise.resolve();
    });
    expect(mockFetchHistorySearch).toHaveBeenCalledTimes(1);

    // Clear and retype the identical query — same debounced value, should
    // hit the lastFetchedQueryRef dedup guard rather than firing again.
    act(() => {
      result.current.setQuery("ab");
    });
    act(() => {
      result.current.setQuery("abc");
    });
    await act(async () => {
      jest.advanceTimersByTime(DEBOUNCE_MS);
      await Promise.resolve();
    });

    expect(mockFetchHistorySearch).toHaveBeenCalledTimes(1);
  });

  it("retrySearch forces a refetch of the same query", async () => {
    mockFetchHistorySearch.mockResolvedValue(resultOf("abc"));
    const { result } = renderHook(() => useHistorySearch());

    act(() => {
      result.current.setQuery("abc");
    });
    await act(async () => {
      jest.advanceTimersByTime(DEBOUNCE_MS);
      await Promise.resolve();
    });
    expect(mockFetchHistorySearch).toHaveBeenCalledTimes(1);

    await act(async () => {
      result.current.retrySearch();
      await Promise.resolve();
    });

    expect(mockFetchHistorySearch).toHaveBeenCalledTimes(2);
  });

  it("surfaces a friendly error message and clears loading on failure", async () => {
    mockFetchHistorySearch.mockRejectedValue(new Error("network down"));
    const { result } = renderHook(() => useHistorySearch());

    act(() => {
      result.current.setQuery("abc");
    });
    await act(async () => {
      jest.advanceTimersByTime(DEBOUNCE_MS);
      await Promise.resolve();
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toMatch(/could not complete search/i);
  });

  it("clearQuery resets query and search mode", async () => {
    mockFetchHistorySearch.mockResolvedValue(resultOf("abc"));
    const { result } = renderHook(() => useHistorySearch());

    act(() => {
      result.current.setQuery("abc");
    });
    await act(async () => {
      jest.advanceTimersByTime(DEBOUNCE_MS);
      await Promise.resolve();
    });
    expect(result.current.isSearchMode).toBe(true);

    act(() => {
      result.current.clearQuery();
    });
    act(() => {
      jest.advanceTimersByTime(DEBOUNCE_MS);
    });

    expect(result.current.query).toBe("");
    expect(result.current.isSearchMode).toBe(false);
  });
});
