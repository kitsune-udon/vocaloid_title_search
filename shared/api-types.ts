export type SortOrder =
  | "popularity"
  | "title_length_asc"
  | "title_length_desc"
  | "published_year_asc"
  | "published_year_desc";

export interface HealthResponse {
  ok: boolean;
  database_ready: boolean;
}

export interface ErrorResponse {
  detail: string;
}

export interface SearchResult {
  title: string;
  title_length: number;
  artist: string;
  artist_note: string;
  url: string;
  popularity_score: number;
  popularity_label: string;
  published_year: number | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  page: number;
  page_size: number;
}

export interface MetadataResponse {
  schema_version?: string;
  source_url?: string;
  fetched_at?: string;
  song_count?: string;
  title_length_rule?: string;
  popularity_source_tags?: string;
  publication_year_source?: string;
  detail_schema_version?: string;
  detail_count?: string;
}

export interface PopularityLabelsResponse {
  labels: string[];
}

export interface TitleLengthBucket {
  length: number;
  count: number;
}

export interface PublishedYearBucket {
  year: number;
  count: number;
}

export interface PopularityLabelBucket {
  label: string;
  count: number;
}

export interface ComposerBucket {
  name: string;
  count: number;
}

export interface StatisticsResponse {
  total_songs: number;
  detail_count: number;
  with_composer: number;
  with_published_year: number;
  by_title_length: TitleLengthBucket[];
  by_published_year: PublishedYearBucket[];
  by_popularity_label: PopularityLabelBucket[];
  top_composers: ComposerBucket[];
}

export interface VideoEntry {
  id: string;
  url: string;
  title: string;
  thumbnail_url: string;
  thumbnail_urls?: string[];
}

export interface VideoMap {
  niconico: VideoEntry[];
  youtube: VideoEntry[];
}

export interface SongDetail {
  page_title: string;
  reading: string;
  published_year: number | null;
  credits: Partial<Record<CreditKey, string[]>>;
  introduction: string[];
  videos: VideoMap;
  related_videos: VideoMap;
  source_url: string;
}

export type CreditKey =
  | "lyricist"
  | "composer"
  | "arranger"
  | "vocalist"
  | "illustrator"
  | "video"
  | "tuning";
