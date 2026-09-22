import { onUnmounted, ref } from "vue";
import { searchSongs } from "../api";
import type { SearchResult, SortOrder } from "../types";

export interface SearchCriteria {
  source: "stats" | null;
  titleLength: number | null;
  composer: string;
  publishedYear: number | null;
  sort: SortOrder;
  popularityLabels: string[];
  page: number;
  pageSize: number;
}

export function useSongSearch() {
  const searchResults = ref<SearchResult[]>([]);
  const totalResults = ref(0);
  const currentPage = ref(1);
  const isSearching = ref(false);
  const lastSearchCriteria = ref<SearchCriteria | null>(null);
  let active: AbortController | null = null;

  function cancelSearch() {
    active?.abort();
    active = null;
    isSearching.value = false;
  }
  onUnmounted(cancelSearch);

  async function search(criteria: SearchCriteria) {
    cancelSearch();
    const controller = new AbortController();
    active = controller;
    isSearching.value = true;
    try {
      const result = await searchSongs(criteria.titleLength, criteria.sort, criteria.popularityLabels,
        criteria.composer, criteria.publishedYear, criteria.page, criteria.pageSize, controller.signal);
      if (controller.signal.aborted) return null;
      searchResults.value = result.results;
      totalResults.value = result.total;
      currentPage.value = result.page;
      lastSearchCriteria.value = { ...criteria, page: result.page, pageSize: result.page_size };
      return result;
    } catch (error) {
      if (controller.signal.aborted) return null;
      throw error;
    } finally {
      if (active === controller) {
        active = null;
        isSearching.value = false;
      }
    }
  }
  return { searchResults, totalResults, currentPage, isSearching, lastSearchCriteria, search, cancelSearch };
}
