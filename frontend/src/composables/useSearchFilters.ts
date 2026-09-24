import { ref } from "vue";
import type { SortOrder } from "../types";
import type { SearchCriteria } from "./useSongSearch";

/** Editable draft; callers decide when to submit it to the search resource. */
export function useSearchFilters() {
  const titleLength = ref("");
  const composerQuery = ref("");
  const publishedYear = ref("");
  const sort = ref<SortOrder>("popularity");
  const popularityLabels = ref<string[]>([]);
  const selectedPopularityLabels = ref<Set<string>>(new Set());

  const formError = ref("");
  function parseTitleLength(value: string): number | null | undefined {
    const trimmed = value.trim();
    if (!trimmed) return null;
    if (!/^\d+$/.test(trimmed)) return undefined;
    const parsed = Number(trimmed);
    return Number.isSafeInteger(parsed) ? parsed : undefined;
  }

  function parsePublishedYear(value: string): number | null | undefined {
    const trimmed = value.trim();
    if (!trimmed) return null;
    if (!/^\d{4}$/.test(trimmed)) return undefined;
    const parsed = Number(trimmed);
    return Number.isSafeInteger(parsed) ? parsed : undefined;
  }

  function clearSearchCriteria(): void {
    titleLength.value = "";
    composerQuery.value = "";
    publishedYear.value = "";
    sort.value = "popularity";
    selectedPopularityLabels.value = defaultPopularityLabelSet();
    formError.value = "";
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


  function readCriteria(page: number, pageSize: number, source: "stats" | null): SearchCriteria | null {
    const length = parseTitleLength(titleLength.value);
    const year = parsePublishedYear(publishedYear.value);
    formError.value = length === undefined ? "文字数には0以上の整数を入力してください。"
      : year === undefined ? "公開年には西暦4桁の年を入力してください。" : "";
    if (length === undefined || year === undefined) return null;
    return { titleLength: length, composer: composerQuery.value.trim(), publishedYear: year,
      sort: sort.value, popularityLabels: [...selectedPopularityLabels.value], page, pageSize, source };
  }

  return { titleLength, composerQuery, publishedYear, sort, popularityLabels, selectedPopularityLabels,
    formError, readCriteria, clearSearchCriteria, resetCriteriaForStatsSearch, defaultPopularityLabelSet,
    allPopularityLabelSet, isDefaultPopularityLabels, popularityLabelSummary, sortLabel };
}
