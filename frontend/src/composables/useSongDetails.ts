import { onUnmounted, ref } from "vue";
import { fetchSongDetail } from "../api";
import { userFacingError } from "../errors";
import type { SearchResult, SongDetail } from "../types";

/** Details live only as long as the visible result set; completed entries are bounded. */
export function useSongDetails() {
  const expandedUrls = ref(new Set<string>());
  const detailCache = ref(new Map<string, SongDetail>());
  const detailErrors = ref(new Map<string, string>());
  const loadingDetails = ref(new Set<string>());
  const slowDetails = ref(new Set<string>());
  const pending = new Map<string, AbortController>();
  const timers = new Map<string, ReturnType<typeof setTimeout>>();

  function cancel(url: string) {
    pending.get(url)?.abort();
    pending.delete(url);
    clearTimeout(timers.get(url));
    timers.delete(url);
    loadingDetails.value.delete(url);
    slowDetails.value.delete(url);
  }

  function reset() {
    for (const url of pending.keys()) cancel(url);
    expandedUrls.value.clear();
    detailErrors.value.clear();
    detailCache.value.clear();
  }
  onUnmounted(reset);

  async function loadDetail(row: SearchResult, force = false) {
    const url = row.url;
    if (!url || (!force && (detailCache.value.has(url) || pending.has(url)))) return;
    cancel(url);
    const controller = new AbortController();
    pending.set(url, controller);
    loadingDetails.value.add(url);
    detailErrors.value.delete(url);
    timers.set(url, setTimeout(() => slowDetails.value.add(url), 1200));
    try {
      const detail = await fetchSongDetail(url, controller.signal);
      if (controller.signal.aborted) return;
      // A result page contains at most 200 songs; clearing on page change bounds memory.
      detailCache.value.set(url, detail);
    } catch (error) {
      if (!controller.signal.aborted) detailErrors.value.set(url, userFacingError(error, "detail"));
    } finally {
      if (pending.get(url) === controller) cancel(url);
    }
  }

  async function toggleDetail(row: SearchResult) {
    if (!row.url) return;
    if (expandedUrls.value.has(row.url)) {
      expandedUrls.value.delete(row.url);
      cancel(row.url);
    } else {
      expandedUrls.value.add(row.url);
      await loadDetail(row);
    }
  }

  return {
    expandedUrls, detailCache, detailErrors, loadingDetails, reset, toggleDetail,
    retryDetail: (row: SearchResult) => loadDetail(row, true),
    detailLoadingText: (url: string) => slowDetails.value.has(url)
      ? "詳細情報を取得しています。通信状況によって少し時間がかかります。"
      : "詳細情報を取得しています",
  };
}
