import type { Env, ReadMetrics } from "./database";
import { observeDatabase } from "./database";
import { HttpError, jsonResponse, responseHeaders, serializeError } from "./http";
import { health, metadata, popularityLabels, statistics, search, songDetail } from "./handlers";
export type { Env } from "./database";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const startedAt = performance.now();
    const metrics: ReadMetrics = { queries: 0, rowsRead: 0, complete: true };
    env = { ...env, DB: observeDatabase(env.DB, metrics) };
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
    if (metrics.complete) response.headers.set("x-d1-rows-read", String(metrics.rowsRead));
    response.headers.set("x-d1-queries", String(metrics.queries));
    logApiTiming(env, requestId, url.pathname, request.method, response.status, startedAt, metrics);
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
  metrics: ReadMetrics,
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
    d1_queries: metrics.queries,
    rows_read: metrics.complete ? metrics.rowsRead : null,
    duration_ms: Math.round((performance.now() - startedAt) * 100) / 100,
  }));
}
