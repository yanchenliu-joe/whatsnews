import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHistoryDateDetail, fetchHistoryDates } from "../services/historyApi";
import { trackEvent } from "../services/analytics";
import type { HistoryDateDetail, HistoryDatesResponse } from "../types";

export function useHistory(options?: { pauseDetail?: boolean }) {
  const pauseDetail = options?.pauseDetail ?? false;
  const [datesData, setDatesData] = useState<HistoryDatesResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [detail, setDetail] = useState<HistoryDateDetail | null>(null);

  const [datesLoading, setDatesLoading] = useState(true);
  const [datesError, setDatesError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  // Session-scoped cache (not persisted — Archive dates are already-published
  // history, so a date fetched once this session never needs refetching).
  // Re-selecting a date chip previously showed a full spinner every time.
  const detailCacheRef = useRef<Map<string, HistoryDateDetail>>(new Map());

  const applyDatesResponse = useCallback((data: HistoryDatesResponse) => {
    setDatesData(data);
    if (data.dates.length > 0) {
      setSelectedDate((prev) => {
        if (prev && data.dates.some((d) => d.date === prev)) {
          return prev;
        }
        return data.dates[0].date;
      });
    } else {
      setSelectedDate(null);
      setDetail(null);
    }
  }, []);

  const loadDates = useCallback(async (isRefresh = false) => {
    if (!isRefresh) {
      setDatesLoading(true);
      setDatesError(null);
    }
    try {
      const data = await fetchHistoryDates(90);
      applyDatesResponse(data);
      setDatesLoading(false);
      return data;
    } catch {
      setDatesError("Couldn't load archive dates. Pull down to try again.");
      setDatesLoading(false);
      return null;
    }
  }, [applyDatesResponse]);

  const loadDetail = useCallback(async (reportDate: string, forceRefresh = false) => {
    const cached = !forceRefresh ? detailCacheRef.current.get(reportDate) : undefined;
    if (cached) {
      setDetail(cached);
      setDetailError(null);
      setDetailLoading(false);
      trackEvent("briefing_archive_viewed", {
        metadata_text: reportDate,
      });
      return cached;
    }

    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);
    try {
      const data = await fetchHistoryDateDetail(reportDate);
      detailCacheRef.current.set(reportDate, data);
      setDetail(data);
      setDetailLoading(false);
      trackEvent("briefing_archive_viewed", {
        metadata_text: reportDate,
      });
      return data;
    } catch (e) {
      const status = (e as Error & { status?: number }).status;
      if (status === 404) {
        setDetailError(
          "No publishable briefings for this date.\nTry another date from the row above.",
        );
      } else {
        setDetailError("Could not load briefings for this date.\nPull down to retry.");
      }
      setDetailLoading(false);
      return null;
    }
  }, []);

  useEffect(() => {
    loadDates();
  }, [loadDates]);

  useEffect(() => {
    if (!selectedDate || pauseDetail) return;
    loadDetail(selectedDate);
  }, [selectedDate, loadDetail, pauseDetail]);

  const selectDate = useCallback(
    (date: string) => {
      if (date === selectedDate) return;
      trackEvent("briefing_date_changed", {
        metadata_text: `${selectedDate ?? "none"} -> ${date}`,
      });
      setSelectedDate(date);
    },
    [selectedDate],
  );

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    const data = await loadDates(true);
    if (data && selectedDate && !pauseDetail) {
      await loadDetail(selectedDate, true);
    }
    setRefreshing(false);
  }, [loadDates, loadDetail, selectedDate, pauseDetail]);

  const retryDates = useCallback(() => {
    loadDates();
  }, [loadDates]);

  const retryDetail = useCallback(() => {
    if (selectedDate) loadDetail(selectedDate, true);
  }, [loadDetail, selectedDate]);

  return {
    datesData,
    selectedDate,
    detail,
    datesLoading,
    datesError,
    detailLoading,
    detailError,
    refreshing,
    selectDate,
    handleRefresh,
    retryDates,
    retryDetail,
  };
}
