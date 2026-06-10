<script setup lang="ts">
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ExternalLink,
  RotateCcw,
  Search as SearchIcon,
  SlidersHorizontal,
  X,
} from "@lucide/vue";
import { computed, nextTick, onMounted, ref } from "vue";
import {
  ApiError,
  fetchMetadata,
  fetchPopularityLabels,
  fetchStatistics,
  fetchSongDetail,
  searchSongs,
} from "./api";
import type {
  ComposerBucket,
  CreditKey,
  MetadataResponse,
  PopularityLabelBucket,
  PublishedYearBucket,
  SearchResult,
  SongDetail,
  SortOrder,
  StatisticsResponse,
  TitleLengthBucket,
  VideoEntry,
  VideoMap,
} from "./types";

interface SearchCriteria {
  source: "stats" | null;
  titleLength: number | null;
  composer: string;
  publishedYear: number | null;
  sort: SortOrder;
  popularityLabels: string[];
  page: number;
  pageSize: number;
}

const titleLength = ref("");
const composerQuery = ref("");
const publishedYear = ref("");
const sort = ref<SortOrder>("popularity");
const metadata = ref<MetadataResponse>({});
const popularityLabels = ref<string[]>([]);
const selectedPopularityLabels = ref<Set<string>>(new Set());
const searchResults = ref<SearchResult[]>([]);
const totalResults = ref(0);
const currentPage = ref(1);
const pageSize = ref<50 | 100 | 200>(50);
const hasSearched = ref(false);
const isSearching = ref(false);
const status = ref("");
const error = ref("");
const formError = ref("");
const lastSearchCriteria = ref<SearchCriteria | null>(null);
const pendingSearchSource = ref<"stats" | null>(null);
const expandedUrls = ref<Set<string>>(new Set());
const detailCache = ref<Map<string, SongDetail>>(new Map());
const detailErrors = ref<Map<string, string>>(new Map());
const loadingDetails = ref<Set<string>>(new Set());
const slowDetails = ref<Set<string>>(new Set());
const resultAnchor = ref<HTMLElement | null>(null);
const filterOpen = ref(true);
const showColumns = ref({
  count: false,
  artist: false,
  publishedYear: false,
  popularity: false,
  popularityLabel: false,
});
const activeView = ref<"search" | "stats">("search");
const statistics = ref<StatisticsResponse | null>(null);
const isStatsLoading = ref(false);
const statsError = ref("");
const activeStatsPanel = ref("title_length");
const statsTouchStartX = ref<number | null>(null);
const detailSlowTimers = new Map<string, number>();

type ErrorContext = "initial" | "search" | "detail" | "stats";

const statsPanels = [
  { key: "title_length", label: "文字数" },
  { key: "published_year", label: "公開年" },
  { key: "popularity_label", label: "根拠タグ" },
  { key: "composer", label: "作曲者" },
] as const;

const hasVisibleMetaColumns = computed(() => (
  showColumns.value.count
  || showColumns.value.artist
  || showColumns.value.publishedYear
  || showColumns.value.popularity
  || showColumns.value.popularityLabel
));

const visibleColumnCount = computed(() => {
  const baseColumns = 2;
  return baseColumns
    + Number(showColumns.value.count)
    + Number(showColumns.value.artist)
    + Number(showColumns.value.publishedYear)
    + Number(showColumns.value.popularity)
    + Number(showColumns.value.popularityLabel);
});

const visibleMetaColumnCount = computed(() => (
  Number(showColumns.value.count)
  + Number(showColumns.value.artist)
  + Number(showColumns.value.publishedYear)
  + Number(showColumns.value.popularity)
  + Number(showColumns.value.popularityLabel)
));

const viewOptionsSummary = computed(() => (
  visibleMetaColumnCount.value === 0
    ? "表示項目"
    : `表示項目 ${visibleMetaColumnCount.value}`
));

const metadataPills = computed(() => {
  if (!metadata.value.song_count || !metadata.value.fetched_at) {
    return [];
  }
  return [
    `${metadata.value.song_count}曲`,
    `取得: ${formatDate(metadata.value.fetched_at)}`,
  ];
});

const selectedPopularityLabelList = computed(() => Array.from(selectedPopularityLabels.value));
const totalPages = computed(() => Math.max(1, Math.ceil(totalResults.value / pageSize.value)));
const resultStart = computed(() => (
  totalResults.value === 0 ? 0 : ((currentPage.value - 1) * pageSize.value) + 1
));
const resultEnd = computed(() => Math.min(currentPage.value * pageSize.value, totalResults.value));

const searchCriteriaChips = computed(() => {
  const criteria = lastSearchCriteria.value;
  if (!criteria) return [];
  const chips = [];
  if (criteria.source === "stats") chips.push("統計から適用");
  if (criteria.titleLength !== null) chips.push(`${criteria.titleLength}文字`);
  if (criteria.composer) chips.push(`作曲者: ${criteria.composer}`);
  if (criteria.publishedYear !== null) chips.push(`公開年: ${criteria.publishedYear}`);
  if (!isDefaultPopularityLabels(criteria.popularityLabels)) {
    chips.push(popularityLabelSummary(criteria.popularityLabels));
  }
  chips.push(sortLabel(criteria.sort));
  return chips;
});

const emptyState = computed(() => {
  if (error.value) {
    return {
      title: "表示できません",
      body: error.value,
    };
  }
  if (!hasSearched.value) {
    return {
      title: "条件を指定して検索",
      body: "文字数、作曲者、公開年、根拠タグを必要に応じて指定し、検索ボタンで結果を表示します。",
    };
  }
  if (searchResults.value.length === 0) {
    return {
      title: "該当する曲がありません",
      body: "条件を減らすか、根拠タグの選択を広げて再検索してください。",
    };
  }
  return null;
});

onMounted(async () => {
  try {
    metadata.value = await fetchMetadata();
    const response = await fetchPopularityLabels();
    popularityLabels.value = response.labels;
    selectedPopularityLabels.value = defaultPopularityLabelSet(response.labels);
  } catch (caught) {
    error.value = userFacingError(caught, "initial");
    metadata.value = {};
    popularityLabels.value = [];
    status.value = "";
  }
});

async function runSearch(): Promise<void> {
  pendingSearchSource.value = null;
  await executeSearch(1);
}

async function runStatsSearch(): Promise<void> {
  pendingSearchSource.value = "stats";
  await executeSearch(1);
}

async function executeSearch(page: number): Promise<void> {
  if (isSearching.value) return;
  const parsedTitleLength = parseTitleLength(titleLength.value);
  if (parsedTitleLength === undefined) {
    formError.value = "文字数には0以上の整数を入力してください。";
    clearResultsForFormError();
    return;
  }
  const parsedPublishedYear = parsePublishedYear(publishedYear.value);
  if (parsedPublishedYear === undefined) {
    formError.value = "公開年には西暦4桁の年を入力してください。";
    clearResultsForFormError();
    return;
  }
  const trimmedComposer = composerQuery.value.trim();
  const selectedLabels = selectedPopularityLabelList.value;
  formError.value = "";
  error.value = "";
  status.value = "検索中";
  hasSearched.value = true;
  isSearching.value = true;
  try {
    const response = await searchSongs(
      parsedTitleLength,
      sort.value,
      selectedLabels,
      trimmedComposer,
      parsedPublishedYear,
      page,
      pageSize.value,
    );
    searchResults.value = response.results;
    totalResults.value = response.total;
    currentPage.value = response.page;
    expandedUrls.value = new Set();
    lastSearchCriteria.value = {
      source: page === 1 ? pendingSearchSource.value : lastSearchCriteria.value?.source ?? null,
      titleLength: parsedTitleLength,
      composer: trimmedComposer,
      publishedYear: parsedPublishedYear,
      sort: sort.value,
      popularityLabels: selectedLabels,
      page: response.page,
      pageSize: response.page_size,
    };
    status.value = response.total
      ? `${resultStart.value}-${resultEnd.value} / ${response.total}件`
      : "0件";
    filterOpen.value = false;
    await scrollToResults(page === 1 ? "smooth" : "auto");
  } catch (caught) {
    renderError(userFacingError(caught, "search"));
  } finally {
    pendingSearchSource.value = null;
    isSearching.value = false;
  }
}

async function scrollToResults(behavior: ScrollBehavior): Promise<void> {
  await nextTick();
  resultAnchor.value?.scrollIntoView({ block: "start", behavior });
}

async function scrollToPageTop(): Promise<void> {
  await nextTick();
  window.scrollTo({ top: 0, behavior: "auto" });
}

function renderError(message: string): void {
  error.value = message;
  status.value = "";
  searchResults.value = [];
  totalResults.value = 0;
  currentPage.value = 1;
}

function clearResultsForFormError(): void {
  error.value = "";
  status.value = "";
  searchResults.value = [];
  totalResults.value = 0;
  currentPage.value = 1;
}

function parseTitleLength(value: string): number | null | undefined {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^\d+$/.test(trimmed)) return undefined;
  return Number.parseInt(trimmed, 10);
}

function parsePublishedYear(value: string): number | null | undefined {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^\d{4}$/.test(trimmed)) return undefined;
  return Number.parseInt(trimmed, 10);
}

function clearTitleLength(): void {
  titleLength.value = "";
  formError.value = "";
}

function clearPublishedYear(): void {
  publishedYear.value = "";
  formError.value = "";
}

function clearComposer(): void {
  composerQuery.value = "";
  formError.value = "";
}

function clearSearchCriteria(): void {
  titleLength.value = "";
  composerQuery.value = "";
  publishedYear.value = "";
  sort.value = "popularity";
  selectedPopularityLabels.value = defaultPopularityLabelSet();
  formError.value = "";
}

function applyLabelSet(labels: Set<string>): void {
  selectedPopularityLabels.value = labels;
  if (hasSearched.value) {
    void runSearch();
  }
}

function selectAllPopularityLabels(): void {
  applyLabelSet(allPopularityLabelSet());
}

function selectDefaultPopularityLabels(): void {
  applyLabelSet(defaultPopularityLabelSet());
}

function clearPopularityLabels(): void {
  applyLabelSet(new Set());
}

function goToPage(page: number): void {
  if (page < 1 || page > totalPages.value || page === currentPage.value || isSearching.value) return;
  void executeSearch(page);
}

function changePageSize(): void {
  if (hasSearched.value) {
    void executeSearch(1);
  }
}

async function showStats(): Promise<void> {
  activeView.value = "stats";
  await scrollToPageTop();
  if (statistics.value || isStatsLoading.value) return;
  isStatsLoading.value = true;
  statsError.value = "";
  try {
    statistics.value = await fetchStatistics();
  } catch (caught) {
    statsError.value = userFacingError(caught, "stats");
  } finally {
    isStatsLoading.value = false;
  }
}

async function showSearch(): Promise<void> {
  activeView.value = "search";
  await scrollToPageTop();
}

function selectStatsPanel(key: string): void {
  activeStatsPanel.value = key;
}

function onStatsTouchStart(event: TouchEvent): void {
  statsTouchStartX.value = event.changedTouches[0]?.clientX ?? null;
}

function onStatsTouchEnd(event: TouchEvent): void {
  if (statsTouchStartX.value === null) return;
  const endX = event.changedTouches[0]?.clientX ?? statsTouchStartX.value;
  const delta = endX - statsTouchStartX.value;
  statsTouchStartX.value = null;
  if (Math.abs(delta) < 48) return;
  moveStatsPanel(delta < 0 ? 1 : -1);
}

function moveStatsPanel(delta: number): void {
  const currentIndex = statsPanels.findIndex((panel) => panel.key === activeStatsPanel.value);
  const nextIndex = Math.min(statsPanels.length - 1, Math.max(0, currentIndex + delta));
  activeStatsPanel.value = statsPanels[nextIndex].key;
}

function maxCount<T extends { count: number }>(items: T[]): number {
  return Math.max(1, ...items.map((item) => item.count));
}

function barWidth(count: number, max: number): string {
  return `${Math.max(4, Math.round((count / max) * 100))}%`;
}

function defaultPopularityLabelSet(labels: string[] = popularityLabels.value): Set<string> {
  return new Set(labels.filter((label) => label !== "殿堂入り"));
}

function isDefaultPopularityLabels(labels: string[]): boolean {
  const defaultLabels = defaultPopularityLabelSet();
  return labels.length === defaultLabels.size && labels.every((label) => defaultLabels.has(label));
}

function allPopularityLabelSet(labels: string[] = popularityLabels.value): Set<string> {
  return new Set(labels);
}

function resetCriteriaForStatsSearch(): void {
  titleLength.value = "";
  composerQuery.value = "";
  publishedYear.value = "";
  sort.value = "popularity";
  selectedPopularityLabels.value = allPopularityLabelSet();
  formError.value = "";
}

function applyLengthFromStats(bucket: TitleLengthBucket): void {
  resetCriteriaForStatsSearch();
  titleLength.value = String(bucket.length);
  activeView.value = "search";
  void runStatsSearch();
}

function applyYearFromStats(bucket: PublishedYearBucket): void {
  resetCriteriaForStatsSearch();
  publishedYear.value = String(bucket.year);
  activeView.value = "search";
  void runStatsSearch();
}

function applyPopularityFromStats(bucket: PopularityLabelBucket): void {
  resetCriteriaForStatsSearch();
  selectedPopularityLabels.value = new Set([bucket.label]);
  activeView.value = "search";
  void runStatsSearch();
}

function applyComposerFromStats(bucket: ComposerBucket): void {
  resetCriteriaForStatsSearch();
  composerQuery.value = bucket.name;
  activeView.value = "search";
  void runStatsSearch();
}

function firstVisibleMetaKey(): string | null {
  if (showColumns.value.count) return "title_length";
  if (showColumns.value.artist) return "artist";
  if (showColumns.value.publishedYear) return "published_year";
  if (showColumns.value.popularity) return "popularity_score";
  if (showColumns.value.popularityLabel) return "popularity_label";
  return null;
}

function popularityLabelSummary(labels: string[]): string {
  if (!labels.length) return "根拠タグ: 指定なし";
  if (popularityLabels.value.length && labels.length === popularityLabels.value.length) return "全タグ";
  if (popularityLabels.value.includes("殿堂入り") && !labels.includes("殿堂入り")) {
    return labels.length === popularityLabels.value.length - 1 ? "殿堂入り除外" : `根拠タグ: ${labels.length}件`;
  }
  return labels.length <= 2 ? `根拠タグ: ${labels.join(" / ")}` : `根拠タグ: ${labels.length}件`;
}

function sortLabel(value: SortOrder): string {
  const labels: Record<SortOrder, string> = {
    popularity: "人気度順",
    title_length_asc: "文字数昇順",
    title_length_desc: "文字数降順",
    published_year_asc: "公開年昇順",
    published_year_desc: "公開年降順",
  };
  return labels[value];
}

function toggleLabel(label: string): void {
  const next = new Set(selectedPopularityLabels.value);
  if (next.has(label)) {
    next.delete(label);
  } else {
    next.add(label);
  }
  selectedPopularityLabels.value = next;
  if (hasSearched.value) {
    void runSearch();
  }
}

function rerunSearchIfNeeded(): void {
  if (hasSearched.value) {
    void runSearch();
  }
}

async function toggleDetail(row: SearchResult): Promise<void> {
  if (!row.url) return;
  const next = new Set(expandedUrls.value);
  if (next.has(row.url)) {
    next.delete(row.url);
    expandedUrls.value = next;
    return;
  }
  next.add(row.url);
  expandedUrls.value = next;
  await loadDetail(row);
}

async function retryDetail(row: SearchResult): Promise<void> {
  await loadDetail(row, true);
}

async function loadDetail(row: SearchResult, force = false): Promise<void> {
  if (!row.url) return;
  if (!force && (detailCache.value.has(row.url) || loadingDetails.value.has(row.url))) return;

  const loading = new Set(loadingDetails.value).add(row.url);
  loadingDetails.value = loading;
  const errors = new Map(detailErrors.value);
  errors.delete(row.url);
  detailErrors.value = errors;
  startDetailSlowTimer(row.url);
  try {
    const detail = await fetchSongDetail(row.url);
    detailCache.value = new Map(detailCache.value).set(row.url, detail);
  } catch (caught) {
    detailErrors.value = new Map(detailErrors.value).set(row.url, userFacingError(caught, "detail"));
  } finally {
    stopDetailSlowTimer(row.url);
    const done = new Set(loadingDetails.value);
    done.delete(row.url);
    loadingDetails.value = done;
  }
}

function startDetailSlowTimer(url: string): void {
  stopDetailSlowTimer(url);
  const timerId = window.setTimeout(() => {
    slowDetails.value = new Set(slowDetails.value).add(url);
  }, 1200);
  detailSlowTimers.set(url, timerId);
}

function stopDetailSlowTimer(url: string): void {
  const timerId = detailSlowTimers.get(url);
  if (timerId !== undefined) {
    window.clearTimeout(timerId);
    detailSlowTimers.delete(url);
  }
  if (slowDetails.value.has(url)) {
    const next = new Set(slowDetails.value);
    next.delete(url);
    slowDetails.value = next;
  }
}

function detailLoadingText(url: string): string {
  return slowDetails.value.has(url)
    ? "詳細情報を取得しています。通信状況によって少し時間がかかります。"
    : "詳細情報を取得しています";
}

function userFacingError(caught: unknown, context: ErrorContext): string {
  if (caught instanceof ApiError) {
    if (caught.status === null) {
      return "通信に失敗しました。ネットワーク状態を確認して再実行してください。";
    }
    if (caught.status === 400) {
      return context === "detail"
        ? "詳細ページのURLが不正です。"
        : "検索条件に不正な値があります。入力内容を確認してください。";
    }
    if (caught.status === 404) {
      return context === "detail"
        ? "詳細情報がDBにありません。DBを再構築してください。"
        : "対象のデータが見つかりませんでした。";
    }
    if (caught.status === 503 || caught.message === "database is not ready") {
      return "DBが未作成、未配置、または更新が必要です。先にDBを作成してください。";
    }
    if (caught.status >= 500) {
      return "サーバー側でエラーが発生しました。時間を置いて再実行してください。";
    }
  }
  const fallback = caught instanceof Error ? caught.message : "";
  if (context === "initial") return `初期データを取得できませんでした。${fallback}`.trim();
  if (context === "stats") return `統計情報を取得できませんでした。${fallback}`.trim();
  if (context === "detail") return "詳細取得に失敗しました。";
  return `検索に失敗しました。${fallback}`.trim();
}

function onFilterToggle(event: Event): void {
  filterOpen.value = (event.target as HTMLDetailsElement).open;
}

function formatDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function creditRows(detail: SongDetail): Array<[string, string[]]> {
  const creditLabels: Array<[CreditKey, string]> = [
    ["lyricist", "作詞"],
    ["composer", "作曲"],
    ["arranger", "編曲"],
    ["vocalist", "唄"],
    ["illustrator", "絵"],
    ["video", "動画"],
    ["tuning", "調声"],
  ];
  const displayRows: Array<[string, string[]]> = [];
  if (detail.reading) {
    displayRows.push(["読み", [detail.reading]]);
  }
  for (const [key, label] of creditLabels) {
    const values = detail.credits[key];
    if (values?.length) {
      displayRows.push([label, values]);
    }
  }
  return displayRows;
}

function allVideos(videos: VideoMap | undefined): Array<[string, VideoEntry]> {
  if (!videos) return [];
  return [
    ...(videos.niconico ?? []).map((video): [string, VideoEntry] => ["ニコニコ", video]),
    ...(videos.youtube ?? []).map((video): [string, VideoEntry] => ["YouTube", video]),
  ];
}

function thumbnailUrl(video: VideoEntry): string {
  return video.thumbnail_urls?.[0] || video.thumbnail_url;
}

function useNextThumbnail(event: Event, video: VideoEntry): void {
  const image = event.target as HTMLImageElement;
  const candidates = video.thumbnail_urls?.length ? video.thumbnail_urls : [video.thumbnail_url];
  const currentIndex = Number.parseInt(image.dataset.thumbnailIndex || "0", 10);
  const nextUrl = candidates[currentIndex + 1];
  if (nextUrl) {
    image.dataset.thumbnailIndex = String(currentIndex + 1);
    image.src = nextUrl;
  }
}
</script>

<template>
  <header>
    <div class="shell topbar">
      <div class="brand-block">
        <h1>Vocaloid Title Search</h1>
        <p class="app-description">初音ミク Wiki の有名曲を探す</p>
      </div>
      <nav class="view-switch" aria-label="表示切替">
        <button type="button" :class="{ active: activeView === 'search' }" :aria-pressed="activeView === 'search'" @click="showSearch">
          <SearchIcon class="button-icon" aria-hidden="true" />
          検索
        </button>
        <button type="button" :class="{ active: activeView === 'stats' }" :aria-pressed="activeView === 'stats'" @click="showStats">
          <BarChart3 class="button-icon" aria-hidden="true" />
          統計
        </button>
      </nav>
    </div>
  </header>

  <main class="shell">
    <template v-if="activeView === 'search'">
    <section class="search-view" aria-label="検索">
      <details class="filter-panel" :open="filterOpen" @toggle="onFilterToggle">
      <summary>
        <span>検索条件</span>
        <span class="filter-summary-action">{{ filterOpen ? "閉じる" : "開く" }}</span>
      </summary>
      <div class="filter-content">
        <form class="controls" @submit.prevent="runSearch">
          <label class="length-field">
            文字数
            <span class="clearable-input">
              <input
                v-model.trim="titleLength"
                name="length"
                type="text"
                inputmode="numeric"
                pattern="[0-9]*"
                placeholder="例: 7"
                title="タイトルの文字数。空欄なら指定しません。"
              />
              <button
                v-if="titleLength"
                class="clear-input-button"
                type="button"
                title="文字数をクリア"
                aria-label="文字数をクリア"
                @click="clearTitleLength"
              >
                <X aria-hidden="true" />
              </button>
            </span>
          </label>
          <label class="composer-field">
            作曲者
            <span class="clearable-input">
              <input
                v-model.trim="composerQuery"
                name="composer"
                type="search"
                placeholder="例: DECO*27"
                title="曲詳細から抽出した作曲者名で部分一致検索します。"
              />
              <button
                v-if="composerQuery"
                class="clear-input-button"
                type="button"
                title="作曲者をクリア"
                aria-label="作曲者をクリア"
                @click="clearComposer"
              >
                <X aria-hidden="true" />
              </button>
            </span>
          </label>
          <label class="year-field">
            公開年
            <span class="clearable-input">
              <input
                v-model.trim="publishedYear"
                name="year"
                type="text"
                inputmode="numeric"
                pattern="[0-9]{4}"
                placeholder="例: 2021"
                title="公開年。空欄なら指定しません。"
              />
              <button
                v-if="publishedYear"
                class="clear-input-button"
                type="button"
                title="公開年をクリア"
                aria-label="公開年をクリア"
                @click="clearPublishedYear"
              >
                <X aria-hidden="true" />
              </button>
            </span>
          </label>
          <div class="controls-actions">
            <button type="submit" :disabled="isSearching">
              <SearchIcon class="button-icon" aria-hidden="true" />
              {{ isSearching ? "検索中" : "検索" }}
            </button>
            <button class="secondary-button" type="button" @click="clearSearchCriteria">
              <RotateCcw class="button-icon" aria-hidden="true" />
              条件クリア
            </button>
          </div>
        </form>
        <div v-if="formError" class="form-error">{{ formError }}</div>

        <div class="filter-row">
          <div class="filter-row-heading">
            <div class="filter-title">根拠タグ</div>
            <div class="filter-presets" aria-label="根拠タグの一括操作">
              <button type="button" @click="selectDefaultPopularityLabels">既定</button>
              <button type="button" @click="selectAllPopularityLabels">全て</button>
              <button type="button" @click="clearPopularityLabels">指定なし</button>
            </div>
          </div>
          <div class="tag-filters">
            <label v-for="label in popularityLabels" :key="label" class="toggle">
              <input
                type="checkbox"
                :checked="selectedPopularityLabels.has(label)"
                @change="toggleLabel(label)"
              />
              {{ label }}
            </label>
          </div>
        </div>

        <div class="sort-row">
          <div class="sort-title">並び順</div>
          <select v-model="sort" class="sort-control" @change="rerunSearchIfNeeded">
            <option value="popularity">人気度順</option>
            <option value="title_length_asc">文字数昇順</option>
            <option value="title_length_desc">文字数降順</option>
            <option value="published_year_asc">公開年昇順</option>
            <option value="published_year_desc">公開年降順</option>
          </select>
        </div>
      </div>
      </details>

      <div v-if="metadataPills.length" class="data-strip" aria-label="DB情報">
        <span v-for="pill in metadataPills" :key="pill">{{ pill }}</span>
      </div>

      <div ref="resultAnchor" class="result-anchor" aria-hidden="true"></div>

      <div v-if="hasSearched || status || error" class="result-bar">
      <div class="result-status-block">
        <div class="status" :class="{ error }">{{ status }}</div>
        <div v-if="searchCriteriaChips.length" class="criteria-chips" aria-label="検索条件">
          <span v-for="chip in searchCriteriaChips" :key="chip">{{ chip }}</span>
        </div>
      </div>
      </div>
      <div v-if="emptyState" class="empty">
        <strong>{{ emptyState.title }}</strong>
        <span>{{ emptyState.body }}</span>
      </div>
      <div v-else class="table-wrap card-results" :class="{ 'compact-results': !hasVisibleMetaColumns }">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>曲</th>
            <th v-if="showColumns.count">文字数</th>
            <th v-if="showColumns.artist">作曲者</th>
            <th v-if="showColumns.publishedYear">公開年</th>
            <th v-if="showColumns.popularity">人気度</th>
            <th v-if="showColumns.popularityLabel">根拠タグ</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="row in searchResults" :key="`${row.url}-${row.title}`">
            <tr
              class="song-row"
              tabindex="0"
              role="button"
              :aria-expanded="expandedUrls.has(row.url)"
              :aria-label="`${row.title}の詳細を${expandedUrls.has(row.url) ? '閉じる' : '開く'}`"
              :title="`${row.title}の詳細を${expandedUrls.has(row.url) ? '閉じる' : '開く'}`"
              @click="toggleDetail(row)"
              @keydown.enter.prevent="toggleDetail(row)"
              @keydown.space.prevent="toggleDetail(row)"
            >
              <td class="expand-cell" data-key="expand" data-label="">
                <span class="chevron" aria-hidden="true">
                  <ChevronRight />
                </span>
              </td>
              <td class="primary-cell" data-key="title" data-label="曲">
                <div class="result-primary">
                  <span class="result-title">{{ row.title }}</span>
                  <a
                    v-if="row.url"
                    class="link-icon"
                    :href="row.url"
                    target="_blank"
                    rel="noreferrer"
                    title="Wikiを開く"
                    aria-label="Wikiを開く"
                    @click.stop
                  >
                    <ExternalLink aria-hidden="true" />
                  </a>
                </div>
              </td>
              <td
                v-if="showColumns.count"
                class="num meta-cell"
                :class="{ 'first-meta-cell': firstVisibleMetaKey() === 'title_length' }"
                data-key="title_length"
                data-label="文字数"
              >
                {{ row.title_length }}
              </td>
              <td
                v-if="showColumns.artist"
                class="meta-cell"
                :class="{ 'first-meta-cell': firstVisibleMetaKey() === 'artist' }"
                data-key="artist"
                data-label="作曲者"
              >{{ row.artist }}</td>
              <td
                v-if="showColumns.publishedYear"
                class="num meta-cell"
                :class="{ 'first-meta-cell': firstVisibleMetaKey() === 'published_year' }"
                data-key="published_year"
                data-label="公開年"
              >
                {{ row.published_year ?? "-" }}
              </td>
              <td
                v-if="showColumns.popularity"
                class="num meta-cell"
                :class="{ 'first-meta-cell': firstVisibleMetaKey() === 'popularity_score' }"
                data-key="popularity_score"
                data-label="人気度"
              >
                {{ row.popularity_score }}
              </td>
              <td
                v-if="showColumns.popularityLabel"
                class="meta-cell"
                :class="{ 'first-meta-cell': firstVisibleMetaKey() === 'popularity_label' }"
                data-key="popularity_label"
                data-label="根拠タグ"
              >
                {{ row.popularity_label }}
              </td>
            </tr>

            <tr v-if="expandedUrls.has(row.url)" class="detail-row">
              <td :colspan="visibleColumnCount">
                <div class="detail-panel">
                  <div v-if="loadingDetails.has(row.url)" class="detail-loading">
                    {{ detailLoadingText(row.url) }}
                  </div>
                  <div v-else-if="detailErrors.has(row.url)" class="detail-error">
                    <span>{{ detailErrors.get(row.url) }}</span>
                    <button type="button" class="inline-action" @click.stop="retryDetail(row)">再試行</button>
                  </div>
                  <template v-else-if="detailCache.has(row.url)">
                    <div class="detail-title">{{ detailCache.get(row.url)?.page_title }}</div>
                    <div v-if="creditRows(detailCache.get(row.url)!).length" class="detail-section">
                      <div class="detail-title">基本情報</div>
                      <ul class="detail-list">
                        <li v-for="[label, values] in creditRows(detailCache.get(row.url)!)" :key="label">
                          <strong>{{ label }}:</strong> {{ values.join(" / ") }}
                        </li>
                      </ul>
                    </div>
                    <div v-if="detailCache.get(row.url)?.introduction.length" class="detail-section">
                      <div class="detail-title">曲紹介</div>
                      <ul class="detail-list">
                        <li v-for="item in detailCache.get(row.url)?.introduction" :key="item">{{ item }}</li>
                      </ul>
                    </div>
                    <div
                      v-for="[sectionTitle, videos] in [
                        ['動画', detailCache.get(row.url)?.videos],
                        ['関連動画', detailCache.get(row.url)?.related_videos],
                      ] as const"
                      :key="sectionTitle"
                      class="detail-section"
                    >
                      <template v-if="allVideos(videos).length">
                        <div class="detail-title">{{ sectionTitle }}</div>
                        <div class="video-grid">
                          <a
                            v-for="[service, video] in allVideos(videos)"
                            :key="`${service}-${video.id}`"
                            class="video-card"
                            :href="video.url"
                            target="_blank"
                            rel="noreferrer"
                            :title="video.title || service"
                          >
                            <img
                              class="video-thumb"
                              :src="thumbnailUrl(video)"
                              :alt="video.title || service"
                              data-thumbnail-index="0"
                              loading="lazy"
                              @error="useNextThumbnail($event, video)"
                            />
                            <span class="video-meta">
                              <span class="video-name">{{ video.title || service }}</span>
                              <span class="video-service">{{ service }}</span>
                            </span>
                          </a>
                        </div>
                      </template>
                    </div>
                  </template>
                  <div v-else class="detail-loading">表示できる詳細情報が見つかりませんでした。</div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      </div>
      <div v-if="!error && searchResults.length" class="result-action-bar">
      <div class="result-action-inner">
        <div class="result-action-summary" aria-live="polite">
          <strong>{{ resultStart }}-{{ resultEnd }}</strong>
          <span>/ {{ totalResults }}件</span>
        </div>
        <label class="page-size-control">
          表示数
          <select v-model.number="pageSize" @change="changePageSize">
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </select>
        </label>
        <div v-if="totalPages > 1" class="pager" aria-label="ページ移動">
          <button class="pager-edge" type="button" :disabled="currentPage <= 1 || isSearching" title="先頭" aria-label="先頭ページへ" @click="goToPage(1)"><ChevronsLeft aria-hidden="true" /></button>
          <button type="button" :disabled="currentPage <= 1 || isSearching" title="前へ" aria-label="前のページへ" @click="goToPage(currentPage - 1)"><ChevronLeft aria-hidden="true" /></button>
          <span class="page-indicator">{{ currentPage }} / {{ totalPages }}</span>
          <button type="button" :disabled="currentPage >= totalPages || isSearching" title="次へ" aria-label="次のページへ" @click="goToPage(currentPage + 1)"><ChevronRight aria-hidden="true" /></button>
          <button class="pager-edge" type="button" :disabled="currentPage >= totalPages || isSearching" title="最後" aria-label="最後のページへ" @click="goToPage(totalPages)"><ChevronsRight aria-hidden="true" /></button>
        </div>
        <details class="view-options-menu">
          <summary title="結果カードに表示する項目を選ぶ" aria-label="結果カードに表示する項目を選ぶ">
            <SlidersHorizontal class="button-icon" aria-hidden="true" />
            {{ viewOptionsSummary }}
          </summary>
          <div class="view-options-content">
            <label class="toggle"><input v-model="showColumns.count" type="checkbox" />文字数</label>
            <label class="toggle"><input v-model="showColumns.artist" type="checkbox" />作曲者</label>
            <label class="toggle"><input v-model="showColumns.publishedYear" type="checkbox" />公開年</label>
            <label class="toggle"><input v-model="showColumns.popularity" type="checkbox" />人気度</label>
            <label class="toggle"><input v-model="showColumns.popularityLabel" type="checkbox" />根拠タグ</label>
          </div>
        </details>
      </div>
      </div>
    </section>
    </template>
    <section v-else class="stats-view" aria-label="統計">
      <div v-if="statsError" class="empty">{{ statsError }}</div>
      <div v-else-if="isStatsLoading || !statistics" class="empty">統計情報を読み込み中</div>
      <template v-else>
        <div class="stats-summary">
          <div class="stat-card">
            <span class="stat-label">総曲数</span>
            <strong>{{ statistics.total_songs }}</strong>
          </div>
          <div class="stat-card">
            <span class="stat-label">詳細取得済み</span>
            <strong>{{ statistics.detail_count }}</strong>
          </div>
          <div class="stat-card">
            <span class="stat-label">作曲者情報あり</span>
            <strong>{{ statistics.with_composer }}</strong>
          </div>
          <div class="stat-card">
            <span class="stat-label">公開年あり</span>
            <strong>{{ statistics.with_published_year }}</strong>
          </div>
        </div>

        <div class="stats-tabs" aria-label="統計カテゴリ">
          <button
            v-for="panel in statsPanels"
            :key="panel.key"
            type="button"
            :class="{ active: activeStatsPanel === panel.key }"
            :aria-pressed="activeStatsPanel === panel.key"
            @click="selectStatsPanel(panel.key)"
          >
            {{ panel.label }}
          </button>
        </div>

        <div class="stats-grid" @touchstart.passive="onStatsTouchStart" @touchend.passive="onStatsTouchEnd">
          <section class="stats-panel" data-stats-panel="title_length" :class="{ active: activeStatsPanel === 'title_length' }">
            <div class="stats-panel-title">タイトル文字数</div>
            <div class="bar-list">
              <button
                v-for="bucket in statistics.by_title_length"
                :key="bucket.length"
                type="button"
                class="bar-row"
                @click="applyLengthFromStats(bucket)"
              >
                <span class="bar-label">{{ bucket.length }}文字</span>
                <span class="bar-track">
                  <span class="bar-fill" :style="{ width: barWidth(bucket.count, maxCount(statistics.by_title_length)) }"></span>
                </span>
                <span class="bar-count">{{ bucket.count }}</span>
              </button>
            </div>
          </section>

          <section class="stats-panel" data-stats-panel="published_year" :class="{ active: activeStatsPanel === 'published_year' }">
            <div class="stats-panel-title">公開年</div>
            <div class="bar-list">
              <button
                v-for="bucket in statistics.by_published_year"
                :key="bucket.year"
                type="button"
                class="bar-row"
                @click="applyYearFromStats(bucket)"
              >
                <span class="bar-label">{{ bucket.year }}</span>
                <span class="bar-track">
                  <span class="bar-fill" :style="{ width: barWidth(bucket.count, maxCount(statistics.by_published_year)) }"></span>
                </span>
                <span class="bar-count">{{ bucket.count }}</span>
              </button>
            </div>
          </section>

          <section class="stats-panel" data-stats-panel="popularity_label" :class="{ active: activeStatsPanel === 'popularity_label' }">
            <div class="stats-panel-title">根拠タグ</div>
            <div class="bar-list">
              <button
                v-for="bucket in statistics.by_popularity_label"
                :key="bucket.label"
                type="button"
                class="bar-row"
                @click="applyPopularityFromStats(bucket)"
              >
                <span class="bar-label">{{ bucket.label }}</span>
                <span class="bar-track">
                  <span class="bar-fill" :style="{ width: barWidth(bucket.count, maxCount(statistics.by_popularity_label)) }"></span>
                </span>
                <span class="bar-count">{{ bucket.count }}</span>
              </button>
            </div>
          </section>

          <section class="stats-panel" data-stats-panel="composer" :class="{ active: activeStatsPanel === 'composer' }">
            <div class="stats-panel-title">作曲者</div>
            <div class="bar-list">
              <button
                v-for="bucket in statistics.top_composers"
                :key="bucket.name"
                type="button"
                class="bar-row"
                @click="applyComposerFromStats(bucket)"
              >
                <span class="bar-label">{{ bucket.name }}</span>
                <span class="bar-track">
                  <span class="bar-fill" :style="{ width: barWidth(bucket.count, maxCount(statistics.top_composers)) }"></span>
                </span>
                <span class="bar-count">{{ bucket.count }}</span>
              </button>
            </div>
          </section>
        </div>
      </template>
    </section>
  </main>
</template>
