import type {
  MetadataResponse,
  PopularityLabelsResponse,
  SearchResponse,
  SongDetail,
  SortOrder,
  StatisticsResponse,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url);
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "network error";
    throw new ApiError(null, message);
  }
  const text = await response.text();
  let data: (T & { error?: string; detail?: string }) | undefined;
  if (text) {
    try {
      data = JSON.parse(text) as T & { error?: string; detail?: string };
    } catch {
      if (!response.ok) {
        throw new ApiError(response.status, `${response.status} ${response.statusText || "request failed"}`.trim());
      }
      throw new ApiError(response.status, "invalid JSON response");
    }
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.error || data?.detail || `${response.status} ${response.statusText || "request failed"}`.trim(),
    );
  }
  if (!data) {
    throw new ApiError(response.status, "empty response");
  }
  return data;
}

export function fetchMetadata(): Promise<MetadataResponse> {
  return fetchJson<MetadataResponse>("/api/metadata");
}

export function fetchPopularityLabels(): Promise<PopularityLabelsResponse> {
  return fetchJson<PopularityLabelsResponse>("/api/popularity-labels");
}

export function fetchStatistics(): Promise<StatisticsResponse> {
  return fetchJson<StatisticsResponse>("/api/stats");
}

export function searchSongs(
  titleLength: number | null,
  sort: SortOrder,
  popularityLabels: string[],
  composer: string,
  publishedYear: number | null,
  page: number,
  pageSize: number,
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    sort,
    page: String(page),
    page_size: String(pageSize),
  });
  if (titleLength !== null) {
    params.set("length", String(titleLength));
  }
  if (publishedYear !== null) {
    params.set("year", String(publishedYear));
  }
  for (const label of popularityLabels) {
    params.append("popularity_label", label);
  }
  if (composer) {
    params.set("composer", composer);
  }
  return fetchJson<SearchResponse>(`/api/search?${params.toString()}`);
}

export function fetchSongDetail(url: string): Promise<SongDetail> {
  const params = new URLSearchParams({ url });
  return fetchJson<SongDetail>(`/api/song-detail?${params.toString()}`);
}
