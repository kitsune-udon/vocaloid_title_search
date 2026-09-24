import type {
  HealthResponse,
  MetadataResponse,
  PopularityLabelsResponse,
  SearchResponse,
  SearchResult,
  StatisticsResponse,
} from "../../../shared/api-types";

import type { Env, D1Result } from "./database";
import { jsonResponse, responseHeaders } from "./http";
import { databaseIsReady, requireDatabaseReady, requireSamePublication } from "./publication";
import { parseSearchParams, precomputedTotal, buildSearchFilters, sqlOrderBy } from "./search-query";
import { cachedSearch, saveSearch } from "./search-cache";
interface SearchRow extends SearchResult {}

interface CountRow {
  count: number;
}

interface PayloadRow {
  payload_json: string;
}

export async function health(env: Env, request: Request): Promise<Response> {
  return jsonResponse<HealthResponse>({ ok: true, database_ready: await databaseIsReady(env.DB) }, 200, env, request);
}

export async function metadata(env: Env, request: Request): Promise<Response> {
  return jsonResponse<MetadataResponse>((await requireDatabaseReady(env.DB)).metadata, 200, env, request);
}

export async function popularityLabels(env: Env, request: Request): Promise<Response> {
  const publication = await requireDatabaseReady(env.DB);
  return jsonResponse<PopularityLabelsResponse>({ labels: publication.statistics.by_popularity_label.map(row => row.label) }, 200, env, request);
}

export async function statistics(env: Env, request: Request): Promise<Response> {
  return jsonResponse<StatisticsResponse>((await requireDatabaseReady(env.DB)).statistics, 200, env, request);
}

export async function search(url: URL, env: Env, request: Request): Promise<Response> {
  const params = parseSearchParams(url.searchParams);
  if ("error" in params) return jsonResponse({ detail: params.error }, 400, env, request);
  const publication = await requireDatabaseReady(env.DB);
  if (params.popularityLabels.length) {
    const validLabels = new Set(publication.statistics.by_popularity_label.map(row => row.label));
    if (params.popularityLabels.some((label) => !validLabels.has(label))) {
      return jsonResponse({ detail: "invalid popularity_label" }, 400, env, request);
    }
  }

  const cacheKey = JSON.stringify([publication.revision, params]);
  const cached = cachedSearch(cacheKey);
  if (cached !== undefined) {
    const headers = responseHeaders(env, request);
    headers.set("x-search-cache", "hit");
    return new Response(cached, { headers });
  }
  const filters = buildSearchFilters(params);
  const savedTotal = precomputedTotal(params, publication.statistics);
  const countStatement = savedTotal === null ? env.DB.prepare(`
    SELECT COUNT(*) AS count
    FROM songs
    JOIN song_details ON song_details.url = songs.song_url
    ${filters.whereSql}
  `).bind(...filters.values) : null;
  const rowsStatement = env.DB.prepare(`
    WITH page AS (
      SELECT songs.*, song_details.published_year
      FROM songs
      JOIN song_details ON song_details.url = songs.song_url
      ${filters.whereSql}
      ORDER BY ${sqlOrderBy(params.sort)}
      LIMIT ? OFFSET ?
    )
    SELECT
      songs.title,
      songs.title_length,
      COALESCE((
        SELECT GROUP_CONCAT(name, ' / ')
        FROM (
          SELECT name FROM song_credit_people
          WHERE song_url = songs.song_url AND role = 'composer'
          ORDER BY name
        )
      ), '') AS artist,
      songs.artist_note,
      songs.song_url AS url,
      songs.popularity_score,
      songs.popularity_label,
      songs.published_year
    FROM page AS songs
    ORDER BY ${sqlOrderBy(params.sort).replaceAll("song_details.", "songs.")}
  `).bind(...filters.values, params.pageSize, (params.page - 1) * params.pageSize);
  const results = await env.DB.batch(countStatement ? [countStatement, rowsStatement] : [rowsStatement]);
  const rows = results[results.length - 1];
  const total = savedTotal ?? firstCount(results[0] as D1Result<CountRow>);

  // Reject results spanning an import; errors and partial DB results never enter the cache.
  await requireSamePublication(env.DB, publication.revision);
  const data: SearchResponse = {
    total,
    page: params.page,
    page_size: params.pageSize,
    results: (rows as D1Result<SearchRow>).results ?? [],
  };
  const body = JSON.stringify(data);
  saveSearch(cacheKey, body);
  const headers = responseHeaders(env, request);
  headers.set("x-search-cache", "miss");
  return new Response(body, { headers });
}

export async function songDetail(url: URL, env: Env, request: Request): Promise<Response> {
  const sourceUrl = url.searchParams.get("url") ?? "";
  if (!isAllowedWikiUrl(sourceUrl)) return jsonResponse({ detail: "invalid wiki url" }, 400, env, request);
  const publication = await requireDatabaseReady(env.DB);
  const row = await env.DB.prepare("SELECT payload_json FROM song_details WHERE url = ?").bind(sourceUrl).first<PayloadRow>();
  await requireSamePublication(env.DB, publication.revision);
  if (!row) return jsonResponse({ detail: "song detail is not available" }, 404, env, request);
  const body = row.payload_json satisfies string;
  return new Response(body, {
    status: 200,
    headers: responseHeaders(env, request),
  });
}

function isAllowedWikiUrl(value: string): boolean {
  return /^https:\/\/w\.atwiki\.jp\/hmiku\/pages\/\d+\.html$/.test(value);
}

function firstCount(result: D1Result<CountRow>): number {
  return result.results?.[0]?.count ?? 0;
}
