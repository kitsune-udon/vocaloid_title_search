import type { SortOrder, StatisticsResponse } from "../../../shared/api-types";
import { normalizeCreditName } from "../../../shared/credit-normalization";
import { HttpError } from "./http";
const SORT_ORDERS = new Set<SortOrder>([
  "popularity",
  "title_length_asc",
  "title_length_desc",
  "published_year_asc",
  "published_year_desc",
]);
const PAGE_SIZES = new Set([50, 100, 200]);

export interface SearchParams {
  length: number | null;
  sort: string;
  popularityLabels: string[];
  composer: string;
  year: number | null;
  page: number;
  pageSize: number;
}

export function parseSearchParams(params: URLSearchParams): SearchParams | { error: string } {
  const length = optionalInteger(params.get("length"), "length", 0);
  if ("error" in length) return length;
  const year = optionalInteger(params.get("year"), "year", 0);
  if ("error" in year) return year;
  const page = requiredInteger(params.get("page") ?? "1", "page", 1);
  if ("error" in page) return page;
  const pageSize = requiredInteger(params.get("page_size") ?? "50", "page_size", 1);
  if ("error" in pageSize) return pageSize;
  if (!PAGE_SIZES.has(pageSize.value)) return { error: "page_size must be one of 50, 100, 200" };
  if (!Number.isSafeInteger((page.value - 1) * pageSize.value)) return { error: "page offset is too large" };
  const sort = params.get("sort") ?? "popularity";
  if (!isSortOrder(sort)) return { error: "sort is not supported" };
  return {
    length: length.value,
    sort,
    popularityLabels: [...new Set(params.getAll("popularity_label").filter(Boolean))].sort(),
    composer: normalizeCreditName(params.get("composer") ?? ""),
    year: year.value,
    page: page.value,
    pageSize: pageSize.value,
  };
}

function isSortOrder(value: string): value is SortOrder {
  return SORT_ORDERS.has(value as SortOrder);
}

function optionalInteger(value: string | null, name: string, min: number): { value: number | null } | { error: string } {
  if (value === null || value === "") return { value: null };
  return requiredInteger(value, name, min);
}

function requiredInteger(value: string, name: string, min: number): { value: number } | { error: string } {
  if (!/^\d+$/.test(value)) return { error: `${name} must be an integer` };
  const parsed = Number.parseInt(value, 10);
  if (!Number.isSafeInteger(parsed)) return { error: `${name} must be a safe integer` };
  if (parsed < min) return { error: `${name} must be ${min} or greater` };
  return { value: parsed };
}

export function precomputedTotal(params: SearchParams, stats: StatisticsResponse): number | null {
  const dimensions = Number(params.length !== null) + Number(params.year !== null) + Number(params.popularityLabels.length > 0);
  if (params.composer || dimensions > 1) return null;
  if (params.length !== null) return stats.by_title_length.find(row => row.length === params.length)?.count ?? 0;
  if (params.year !== null) return stats.by_published_year.find(row => row.year === params.year)?.count ?? 0;
  if (params.popularityLabels.length) return stats.by_popularity_label
    .filter(row => params.popularityLabels.includes(row.label)).reduce((total, row) => total + row.count, 0);
  return stats.total_songs;
}

export function buildSearchFilters(params: SearchParams): { whereSql: string; values: unknown[] } {
  const clauses: string[] = [];
  const values: unknown[] = [];
  if (params.length !== null) {
    clauses.push("songs.title_length = ?");
    values.push(params.length);
  }
  if (params.popularityLabels.length) {
    clauses.push(`songs.popularity_label IN (${params.popularityLabels.map(() => "?").join(", ")})`);
    values.push(...params.popularityLabels);
  }
  if (params.year !== null) {
    clauses.push("song_details.published_year = ?");
    values.push(params.year);
  }
  const normalizedComposer = normalizeCreditName(params.composer);
  if (normalizedComposer) {
    clauses.push(`
      songs.song_url IN (
        SELECT person.song_url
        FROM song_credit_people person
        WHERE person.role = 'composer'
          AND person.normalized_name LIKE ? ESCAPE '\\'
      )
    `);
    values.push(`%${escapeLikePattern(normalizedComposer)}%`);
  }
  return {
    whereSql: clauses.length ? `WHERE ${clauses.join(" AND ")}` : "",
    values,
  };
}

export function sqlOrderBy(sort: string): string {
  if (sort === "popularity") return "popularity_score DESC, popularity_order, sort_order";
  if (sort === "title_length_asc") return "title_length ASC, popularity_score DESC, popularity_order, sort_order";
  if (sort === "title_length_desc") return "title_length DESC, popularity_score DESC, popularity_order, sort_order";
  if (sort === "published_year_asc") return "song_details.published_year IS NULL, song_details.published_year ASC, popularity_score DESC, popularity_order, sort_order";
  if (sort === "published_year_desc") return "song_details.published_year IS NULL, song_details.published_year DESC, popularity_score DESC, popularity_order, sort_order";
  throw new HttpError(400, "sort is not supported");
}

function escapeLikePattern(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/%/g, "\\%").replace(/_/g, "\\_");
}
