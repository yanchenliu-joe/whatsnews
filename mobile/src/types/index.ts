export type Topic = {
  id: number;
  name: string;
  sort_order: number;
};

export type NewsItem = {
  title: string;
  summary: string;
  body_text?: string | null;
  source: string;
  url: string;
  why_it_matters: string;
  published_at?: string | null;
  image_url?: string | null;
  topic?: string | null;
};

export type DailyReport = {
  date: string;
  topic: string;
  items: NewsItem[];
};

export type HistoryDateEntry = {
  date: string;
  topics_available?: number;
  total_articles?: number;
  article_count?: number;
};

export type HistoryDatesResponse = {
  topic: string | null;
  dates: HistoryDateEntry[];
  earliest: string | null;
  latest: string | null;
  count: number;
};

export type HistoryTopicBriefing = {
  report_date: string;
  report_id: number;
  article_count: number;
  generated_at: string | null;
  headline: string | null;
  summary: string | null;
  quality_score: number | null;
  version: number | null;
  topic: string;
  topic_id: number;
  articles: NewsItem[];
};

export type HistoryDateDetail = {
  report_date: string;
  topics: HistoryTopicBriefing[];
  topic_count: number;
};

export type HistorySearchResult = {
  report_date: string;
  topic: string;
  topic_id: number;
  title: string;
  source: string;
  url: string | null;
  why_it_matters: string;
  snippet: string;
  image_url?: string | null;
};

export type HistorySearchResponse = {
  query: string;
  total: number;
  limit: number;
  offset: number;
  results: HistorySearchResult[];
};

export type SavedArticle = {
  url: string;
  title: string;
  source: string;
  topic?: string;
  saved_at?: string;
  summary?: string;
  why_it_matters?: string;
  image_url?: string | null;
  article_id?: number;
  remote_id?: number;
};

export type NarrativeAudioVariant = {
  id: string;
  label: string;
  status: string;
  url: string | null;
  duration_seconds: number | null;
  generated_at: string | null;
};

export type VoiceAlignment = {
  latest_daily_report_date?: string | null;
  latest_ready_narrative_date?: string | null;
  latest_ready_audio_date?: string | null;
  anchor_report_date?: string | null;
  audio_generation_enabled?: boolean;
  voice_status?:
    | "ready_for_current_report"
    | "narrative_missing"
    | "audio_missing"
    | "audio_generation_disabled"
    | "stale_audio"
    | "failed"
    | string;
  message?: string;
};

export type NarrativeAudio = {
  default_profile: string;
  variants: NarrativeAudioVariant[];
  status: string;
  url: string | null;
  duration_seconds: number | null;
  generated_at: string | null;
};

export type Narrative = {
  id?: number | null;
  report_date: string;
  scope: string;
  status: string;
  version: number;
  word_count?: number | null;
  estimated_duration_seconds?: number | null;
  script_text?: string;
  generated_at?: string | null;
  audio: NarrativeAudio;
  voice_alignment?: VoiceAlignment;
};

export type Perspective = {
  id: number;
  report_date: string;
  status: string;
  headline: string;
  perspective: string;
  confidence?: string;
  themes?: string[];
};

export type WatchNextItem = {
  text: string;
  reason: string;
  topics?: string[];
  confidence?: string;
};

export type WatchNext = {
  id: number;
  report_date: string;
  status: string;
  items: WatchNextItem[];
  item_count: number;
};
