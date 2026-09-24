import type { Env } from "./database";
export function jsonResponse<T>(body: T, status: number, env: Env, request: Request): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(env, request),
  });
}

export function responseHeaders(env: Env, request: Request): Headers {
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

export class HttpError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

export function serializeError(error: unknown): Record<string, string> {
  if (error instanceof HttpError) return { name: "HttpError", message: error.message, status: String(error.status) };
  if (error instanceof Error) return { name: error.name, message: error.message, stack: error.stack ?? "" };
  return { name: "UnknownError", message: String(error) };
}
