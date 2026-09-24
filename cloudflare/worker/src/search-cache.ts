// Isolate-local, bounded cache: no extra service or billable storage required.
const searchCache = new Map<string, { body: string; expires: number }>();
const CACHE_TTL_MS = 60_000;
const CACHE_MAX_ENTRIES = 128;
const CACHE_MAX_BYTES = 2 * 1024 * 1024;
let cacheBytes = 0;

export function cachedSearch(key: string): string | undefined {
  const entry = searchCache.get(key);
  if (!entry) return;
  if (entry.expires <= Date.now()) {
    cacheBytes -= entry.body.length * 2;
    searchCache.delete(key);
    return;
  }
  return entry.body;
}

export function saveSearch(key: string, body: string): void {
  const bytes = body.length * 2;
  if (bytes > 128 * 1024 || key.length > 2048) return;
  const previous = searchCache.get(key);
  if (previous) {
    cacheBytes -= previous.body.length * 2;
    searchCache.delete(key);
  }
  while (searchCache.size >= CACHE_MAX_ENTRIES || cacheBytes + bytes > CACHE_MAX_BYTES) {
    const oldest = searchCache.keys().next().value!;
    cacheBytes -= searchCache.get(oldest)!.body.length * 2;
    searchCache.delete(oldest);
  }
  searchCache.set(key, { body, expires: Date.now() + CACHE_TTL_MS });
  cacheBytes += bytes;
}
