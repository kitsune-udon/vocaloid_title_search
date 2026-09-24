<script setup lang="ts">
import SearchResults from "./components/SearchResults.vue";
import SearchControls from "./components/SearchControls.vue";
import { userFacingError } from "./errors";
import StatisticsView from "./components/StatisticsView.vue";
import { useSearchFilters } from "./composables/useSearchFilters";
import { useSongSearch } from "./composables/useSongSearch";
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Search as SearchIcon,
  SlidersHorizontal,
} from "@lucide/vue";
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import {
  fetchMetadata,
  fetchPopularityLabels,
  fetchStatistics,
} from "./api";
import type {
  ComposerBucket,
  MetadataResponse,
  PopularityLabelBucket,
  PublishedYearBucket,
  StatisticsResponse,
  TitleLengthBucket,
} from "./types";

const { searchResults, totalResults, currentPage, isSearching, lastSearchCriteria, search, cancelSearch } = useSongSearch();
const { titleLength, composerQuery, publishedYear, sort, popularityLabels, selectedPopularityLabels,
  formError, readCriteria, clearSearchCriteria, resetCriteriaForStatsSearch, defaultPopularityLabelSet,
  allPopularityLabelSet, isDefaultPopularityLabels, popularityLabelSummary, sortLabel } = useSearchFilters();
const metadata = ref<MetadataResponse>({});
const initialLoading = ref(true);
const initialError = ref("");
const catalogReady = computed(() => !initialLoading.value && !initialError.value);
const pageSize = ref<50 | 100 | 200>(50);
const hasSearched = ref(false);

const status = ref("");
const error = ref("");

const pendingSearchSource = ref<"stats" | null>(null);
const resultAnchor = ref<HTMLElement | null>(null);
const filterOpen = ref(true);
const searchDock = ref<HTMLElement | null>(null);
const searchDockHeight = ref(0);
let searchDockObserver: ResizeObserver | undefined;
onMounted(() => {
  searchDockObserver = new ResizeObserver(() => {
    searchDockHeight.value = searchDock.value?.offsetHeight ?? 0;
  });
  if (searchDock.value) searchDockObserver.observe(searchDock.value);
});
onUnmounted(() => searchDockObserver?.disconnect());
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

const resultPageSize = computed(() => lastSearchCriteria.value?.pageSize ?? pageSize.value);
const totalPages = computed(() => Math.max(1, Math.ceil(totalResults.value / resultPageSize.value)));
const resultStart = computed(() => (
  totalResults.value === 0 ? 0 : ((currentPage.value - 1) * resultPageSize.value) + 1
));
const resultEnd = computed(() => Math.min(currentPage.value * resultPageSize.value, totalResults.value));

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

const lifetime = new AbortController();
onUnmounted(() => lifetime.abort());

onMounted(loadInitialData);

async function loadInitialData(): Promise<void> {
  initialLoading.value = true;
  initialError.value = "";
  try {
    const [meta, response] = await Promise.all([fetchMetadata(lifetime.signal), fetchPopularityLabels(lifetime.signal)]);
    if (lifetime.signal.aborted) return;
    metadata.value = meta;
    popularityLabels.value = response.labels;
    selectedPopularityLabels.value = defaultPopularityLabelSet(response.labels);
  } catch (caught) {
    if (lifetime.signal.aborted) return;
    initialError.value = userFacingError(caught, "initial");
    metadata.value = {};
    popularityLabels.value = [];
    status.value = "";
  } finally {
    initialLoading.value = false;
  }
}

async function runSearch(): Promise<void> {
  activeView.value = "search";
  pendingSearchSource.value = null;
  await executeSearch(1);
}

async function runStatsSearch(): Promise<void> {
  pendingSearchSource.value = "stats";
  await executeSearch(1);
}

async function executeSearch(page: number, reuseApplied = false): Promise<void> {
  if (!catalogReady.value) return;
  cancelSearch();
  const criteria = reuseApplied && lastSearchCriteria.value
    ? { ...lastSearchCriteria.value, page, pageSize: pageSize.value }
    : readCriteria(page, pageSize.value, pendingSearchSource.value);
  if (!criteria) {
    clearResultsForFormError();
    return;
  }
  formError.value = "";
  error.value = "";
  status.value = "検索中";
  hasSearched.value = true;
  try {
    const response = await search(criteria);
    if (!response) return;
    pendingSearchSource.value = null;
    status.value = response.total
      ? `${resultStart.value}-${resultEnd.value} / ${response.total}件`
      : "0件";
    filterOpen.value = false;
    await scrollToResults(page === 1 ? "smooth" : "auto");
  } catch (caught) {
    pendingSearchSource.value = null;
    renderError(userFacingError(caught, "search"));
  }
}

async function scrollToResults(behavior: ScrollBehavior): Promise<void> {
  await nextTick();
  searchDockHeight.value = searchDock.value?.offsetHeight ?? 0;
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

function applyLabelSet(labels: Set<string>): void {
  selectedPopularityLabels.value = labels;
  if (hasSearched.value) {
    void runSearch();
  }
}

function applyPreset(preset: "all" | "default" | "none"): void {
  applyLabelSet(preset === "all" ? allPopularityLabelSet() : preset === "default" ? defaultPopularityLabelSet() : new Set());
}

function goToPage(page: number): void {
  if (page < 1 || page > totalPages.value || page === currentPage.value || isSearching.value) return;
  void executeSearch(page, true);
}

function changePageSize(): void {
  if (hasSearched.value) {
    void executeSearch(1, true);
  }
}

async function showStats(): Promise<void> {
  activeView.value = "stats";
  await scrollToPageTop();
  if (statistics.value || isStatsLoading.value) return;
  isStatsLoading.value = true;
  statsError.value = "";
  try {
    statistics.value = await fetchStatistics(lifetime.signal);
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

function onFilterToggle(event: Event): void {
  filterOpen.value = (event.target as HTMLDetailsElement).open;
}

function formatDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

</script>

<template>
  <div class="app-layout" :style="{ '--search-dock-height': `${searchDockHeight}px` }">
  <div ref="searchDock" class="search-dock">
    <div class="shell search-dock-inner">
      <section aria-label="検索">
      <details class="filter-panel" :open="filterOpen" @toggle="onFilterToggle">
      <summary>
        <span>検索条件</span>
        <span class="filter-summary-action">{{ filterOpen ? "閉じる" : "開く" }}</span>
      </summary>
      <SearchControls v-model:title-length="titleLength" v-model:composer-query="composerQuery"
        v-model:published-year="publishedYear" v-model:sort="sort" :is-searching="isSearching"
        :disabled="!catalogReady" :form-error="formError" :popularity-labels="popularityLabels" :selected-popularity-labels="selectedPopularityLabels"
        @search="runSearch" @reset="clearSearchCriteria" @clear-error="formError = ''"
        @preset="applyPreset" @toggle-label="toggleLabel" @sort="rerunSearchIfNeeded" />
      </details>
      </section>
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
  </div>
  <main class="shell">
    <div v-if="initialError" class="empty" role="alert">
      <span>{{ initialError }}</span>
      <button type="button" @click="loadInitialData">再読み込み</button>
    </div>
    <template v-if="activeView === 'search'">
    <section class="search-view" aria-label="検索結果">


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
      <SearchResults v-else :search-results="searchResults" :show-columns="showColumns" />
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
    <StatisticsView v-else v-model="activeStatsPanel" :statistics="statistics"
      :is-stats-loading="isStatsLoading || initialLoading" :stats-error="statsError || initialError"
      @length="applyLengthFromStats" @year="applyYearFromStats"
      @popularity="applyPopularityFromStats" @composer="applyComposerFromStats" />
  </main>
  </div>
</template>
