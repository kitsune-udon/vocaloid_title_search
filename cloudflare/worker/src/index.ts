import type {
  ComposerBucket,
  HealthResponse,
  MetadataResponse,
  PopularityLabelBucket,
  PopularityLabelsResponse,
  PublishedYearBucket,
  SearchResponse,
  SearchResult,
  SortOrder,
  StatisticsResponse,
  TitleLengthBucket,
} from "../../../shared/api-types";

const REQUIRED_METADATA_KEYS = [
  "schema_version",
  "fetched_at",
  "song_count",
  "title_length_rule",
  "detail_count",
  "detail_schema_version",
];
const DATABASE_SCHEMA_VERSION = "7";
const DETAIL_SCHEMA_VERSION = "1";
const SORT_ORDERS = new Set<SortOrder>([
  "popularity",
  "title_length_asc",
  "title_length_desc",
  "published_year_asc",
  "published_year_desc",
]);
const PAGE_SIZES = new Set([50, 100, 200]);

export interface Env {
  DB: D1Database;
  CORS_ORIGINS?: string;
  API_TIMING_LOGS?: string;
}

interface D1Database {
  prepare(query: string): D1PreparedStatement;
  batch<T = unknown>(statements: D1PreparedStatement[]): Promise<Array<D1Result<T>>>;
}

interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement;
  first<T = unknown>(): Promise<T | null>;
  all<T = unknown>(): Promise<D1Result<T>>;
}

interface D1Result<T = unknown> {
  results?: T[];
}

interface SearchRow extends SearchResult {}

interface CountRow {
  count: number;
}

interface MetadataRow {
  key: string;
  value: string;
}

interface LabelRow {
  popularity_label: string;
}

interface PayloadRow {
  payload_json: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const startedAt = performance.now();
    const url = new URL(request.url);
    const requestId = crypto.randomUUID();
    let response: Response;
    try {
      if (request.method === "OPTIONS") {
        response = new Response(null, { status: 204, headers: responseHeaders(env, request) });
      } else if (request.method !== "GET") {
        response = jsonResponse({ detail: "method not allowed" }, 405, env, request);
      } else if (url.pathname === "/health") {
        response = await health(env, request);
      } else if (url.pathname === "/api/metadata") {
        response = await metadata(env, request);
      } else if (url.pathname === "/api/popularity-labels") {
        response = await popularityLabels(env, request);
      } else if (url.pathname === "/api/stats") {
        response = await statistics(env, request);
      } else if (url.pathname === "/api/search") {
        response = await search(url, env, request);
      } else if (url.pathname === "/api/song-detail") {
        response = await songDetail(url, env, request);
      } else {
        response = jsonResponse({ detail: "not found" }, 404, env, request);
      }
    } catch (error) {
      if (error instanceof HttpError) {
        response = jsonResponse({ detail: error.message }, error.status, env, request);
      } else {
        console.error(JSON.stringify({ event: "worker_error", requestId, path: url.pathname, error: serializeError(error) }));
        response = jsonResponse({ detail: "internal server error" }, 500, env, request);
      }
    }
    logApiTiming(env, requestId, url.pathname, request.method, response.status, startedAt);
    return response;
  },
};

function logApiTiming(
  env: Env,
  requestId: string,
  path: string,
  method: string,
  status: number,
  startedAt: number,
): void {
  if (env.API_TIMING_LOGS === "0") {
    return;
  }
  console.log(JSON.stringify({
    event: "api_timing",
    requestId,
    method,
    path,
    status,
    duration_ms: Math.round((performance.now() - startedAt) * 100) / 100,
  }));
}

async function health(env: Env, request: Request): Promise<Response> {
  return jsonResponse<HealthResponse>({ ok: true, database_ready: await databaseIsReady(env.DB) }, 200, env, request);
}

async function metadata(env: Env, request: Request): Promise<Response> {
  return jsonResponse<MetadataResponse>(await requireDatabaseReady(env.DB), 200, env, request);
}

async function popularityLabels(env: Env, request: Request): Promise<Response> {
  await requireDatabaseReady(env.DB);
  return jsonResponse<PopularityLabelsResponse>({ labels: await loadPopularityLabels(env.DB) }, 200, env, request);
}

async function loadPopularityLabels(db: D1Database): Promise<string[]> {
  const rows = await db.prepare(`
    SELECT popularity_label
    FROM songs
    WHERE popularity_label <> ''
    GROUP BY popularity_label
    ORDER BY MAX(popularity_score) DESC, popularity_label
  `).all<LabelRow>();
  return (rows.results ?? []).map((row) => row.popularity_label);
}

async function statistics(env: Env, request: Request): Promise<Response> {
  const metadata = await requireDatabaseReady(env.DB);
  const [
    withComposerResult,
    withPublishedYearResult,
    byTitleLengthResult,
    byPublishedYearResult,
    byPopularityLabelResult,
    topComposersResult,
  ] = await env.DB.batch([
    env.DB.prepare("SELECT COUNT(DISTINCT song_url) AS count FROM song_credit_people WHERE role = 'composer'"),
    env.DB.prepare("SELECT COUNT(*) AS count FROM song_details WHERE published_year IS NOT NULL"),
    env.DB.prepare("SELECT title_length AS length, COUNT(*) AS count FROM songs GROUP BY title_length ORDER BY title_length"),
    env.DB.prepare("SELECT published_year AS year, COUNT(*) AS count FROM song_details WHERE published_year IS NOT NULL GROUP BY published_year ORDER BY published_year"),
    env.DB.prepare("SELECT popularity_label AS label, COUNT(*) AS count FROM songs WHERE popularity_label <> '' GROUP BY popularity_label ORDER BY MAX(popularity_score) DESC, popularity_label"),
    env.DB.prepare(`
      SELECT MIN(name) AS name, COUNT(DISTINCT song_url) AS count
      FROM song_credit_people
      WHERE role = 'composer'
      GROUP BY normalized_name
      ORDER BY count DESC, MIN(name)
      LIMIT 30
    `),
  ]);
  return jsonResponse<StatisticsResponse>({
    total_songs: metadataCount(metadata.song_count),
    detail_count: metadataCount(metadata.detail_count),
    with_composer: firstCount(withComposerResult as D1Result<CountRow>),
    with_published_year: firstCount(withPublishedYearResult as D1Result<CountRow>),
    by_title_length: (byTitleLengthResult as D1Result<TitleLengthBucket>).results ?? [],
    by_published_year: (byPublishedYearResult as D1Result<PublishedYearBucket>).results ?? [],
    by_popularity_label: (byPopularityLabelResult as D1Result<PopularityLabelBucket>).results ?? [],
    top_composers: (topComposersResult as D1Result<ComposerBucket>).results ?? [],
  }, 200, env, request);
}

async function search(url: URL, env: Env, request: Request): Promise<Response> {
  await requireDatabaseReady(env.DB);
  const params = parseSearchParams(url.searchParams);
  if ("error" in params) return jsonResponse({ detail: params.error }, 400, env, request);
  const validLabels = new Set(await loadPopularityLabels(env.DB));
  if (params.popularityLabels.some((label) => !validLabels.has(label))) {
    return jsonResponse({ detail: "invalid popularity_label" }, 400, env, request);
  }

  const filters = buildSearchFilters(params);
  const countRow = await env.DB.prepare(`
    SELECT COUNT(*) AS count
    FROM songs
    JOIN song_details ON song_details.url = songs.song_url
    ${filters.whereSql}
  `).bind(...filters.values).first<CountRow>();
  const total = countRow?.count ?? 0;
  const rows = await env.DB.prepare(`
    SELECT
      songs.title,
      songs.title_length,
      COALESCE(composers.composer_names, '') AS artist,
      songs.artist_note,
      songs.song_url AS url,
      songs.popularity_score,
      songs.popularity_label,
      song_details.published_year
    FROM songs
    JOIN song_details ON song_details.url = songs.song_url
    LEFT JOIN (
      SELECT song_url, GROUP_CONCAT(name, ' / ') AS composer_names
      FROM (
        SELECT song_url, name
        FROM song_credit_people
        WHERE role = 'composer'
        ORDER BY name
      )
      GROUP BY song_url
    ) composers ON composers.song_url = songs.song_url
    ${filters.whereSql}
    ORDER BY ${sqlOrderBy(params.sort)}
    LIMIT ? OFFSET ?
  `).bind(...filters.values, params.pageSize, (params.page - 1) * params.pageSize).all<SearchRow>();

  return jsonResponse<SearchResponse>({
    total,
    page: params.page,
    page_size: params.pageSize,
    results: rows.results ?? [],
  }, 200, env, request);
}

async function songDetail(url: URL, env: Env, request: Request): Promise<Response> {
  await requireDatabaseReady(env.DB);
  const sourceUrl = url.searchParams.get("url") ?? "";
  if (!isAllowedWikiUrl(sourceUrl)) return jsonResponse({ detail: "invalid wiki url" }, 400, env, request);
  const row = await env.DB.prepare("SELECT payload_json FROM song_details WHERE url = ?").bind(sourceUrl).first<PayloadRow>();
  if (!row) return jsonResponse({ detail: "song detail is not available" }, 404, env, request);
  const body = row.payload_json satisfies string;
  return new Response(body, {
    status: 200,
    headers: responseHeaders(env, request),
  });
}

async function databaseIsReady(db: D1Database): Promise<boolean> {
  return (await databaseReadiness(db)).ready;
}

async function databaseReadiness(db: D1Database): Promise<{ ready: boolean; metadata: Record<string, string> }> {
  try {
    const metadata = await loadMetadata(db);
    const songCount = await db.prepare("SELECT COUNT(*) AS count FROM songs").first<CountRow>();
    const detailCount = await db.prepare("SELECT COUNT(*) AS count FROM song_details").first<CountRow>();
    return {
      ready: REQUIRED_METADATA_KEYS.every((key) => key in metadata)
      && metadata.schema_version === DATABASE_SCHEMA_VERSION
      && metadata.detail_schema_version === DETAIL_SCHEMA_VERSION
      && Number.parseInt(metadata.song_count, 10) === (songCount?.count ?? -1)
      && Number.parseInt(metadata.detail_count, 10) === (detailCount?.count ?? -1)
      && (songCount?.count ?? 0) > 0
      && (detailCount?.count ?? -1) === (songCount?.count ?? 0),
      metadata,
    };
  } catch {
    return { ready: false, metadata: {} };
  }
}

async function requireDatabaseReady(db: D1Database): Promise<Record<string, string>> {
  const readiness = await databaseReadiness(db);
  if (!readiness.ready) {
    throw new HttpError(503, "database is not ready");
  }
  return readiness.metadata;
}

async function loadMetadata(db: D1Database): Promise<Record<string, string>> {
  const rows = await db.prepare("SELECT key, value FROM metadata").all<MetadataRow>();
  return Object.fromEntries((rows.results ?? []).map((row) => [row.key, row.value]));
}

interface SearchParams {
  length: number | null;
  sort: string;
  popularityLabels: string[];
  composer: string;
  year: number | null;
  page: number;
  pageSize: number;
}

function parseSearchParams(params: URLSearchParams): SearchParams | { error: string } {
  const length = optionalInteger(params.get("length"), "length", 0);
  if ("error" in length) return length;
  const year = optionalInteger(params.get("year"), "year", 0);
  if ("error" in year) return year;
  const page = requiredInteger(params.get("page") ?? "1", "page", 1);
  if ("error" in page) return page;
  const pageSize = requiredInteger(params.get("page_size") ?? "50", "page_size", 1);
  if ("error" in pageSize) return pageSize;
  if (!PAGE_SIZES.has(pageSize.value)) return { error: "page_size must be one of 50, 100, 200" };
  const sort = params.get("sort") ?? "popularity";
  if (!isSortOrder(sort)) return { error: "sort is not supported" };
  return {
    length: length.value,
    sort,
    popularityLabels: params.getAll("popularity_label").filter(Boolean),
    composer: params.get("composer")?.trim() ?? "",
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
  if (parsed < min) return { error: `${name} must be ${min} or greater` };
  return { value: parsed };
}

function buildSearchFilters(params: SearchParams): { whereSql: string; values: unknown[] } {
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
      EXISTS (
        SELECT 1
        FROM song_credit_people person
        WHERE person.song_url = songs.song_url
          AND person.role = 'composer'
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

function sqlOrderBy(sort: string): string {
  if (sort === "popularity") return "popularity_score DESC, popularity_order, sort_order";
  if (sort === "title_length_asc") return "title_length ASC, popularity_score DESC, popularity_order, sort_order";
  if (sort === "title_length_desc") return "title_length DESC, popularity_score DESC, popularity_order, sort_order";
  if (sort === "published_year_asc") return "song_details.published_year IS NULL, song_details.published_year ASC, popularity_score DESC, popularity_order, sort_order";
  if (sort === "published_year_desc") return "song_details.published_year IS NULL, song_details.published_year DESC, popularity_score DESC, popularity_order, sort_order";
  throw new HttpError(400, "sort is not supported");
}

function normalizeCreditName(value: string): string {
  return value.normalize("NFKC").toLocaleLowerCase().trim();
}

function escapeLikePattern(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/%/g, "\\%").replace(/_/g, "\\_");
}

function isAllowedWikiUrl(value: string): boolean {
  return /^https:\/\/w\.atwiki\.jp\/hmiku\/pages\/\d+\.html$/.test(value);
}

function jsonResponse<T>(body: T, status: number, env: Env, request: Request): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(env, request),
  });
}

function responseHeaders(env: Env, request: Request): Headers {
  const headers = new Headers({
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
  });
  const origin = request.headers.get("origin");
  if (origin && allowedOrigins(env).has(origin)) {
    headers.set("access-control-allow-origin", origin);
    headers.set("access-control-allow-methods", "GET, OPTIONS");
    headers.set("access-control-allow-headers", "content-type");
    headers.set("vary", "Origin");
  }
  return headers;
}

function allowedOrigins(env: Env): Set<string> {
  return new Set((env.CORS_ORIGINS ?? "").split(",").map((origin) => origin.trim()).filter(Boolean));
}

function firstCount(result: D1Result<CountRow>): number {
  return result.results?.[0]?.count ?? 0;
}

function metadataCount(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

class HttpError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

function serializeError(error: unknown): Record<string, string> {
  if (error instanceof HttpError) return { name: "HttpError", message: error.message, status: String(error.status) };
  if (error instanceof Error) return { name: error.name, message: error.message, stack: error.stack ?? "" };
  return { name: "UnknownError", message: String(error) };
}
