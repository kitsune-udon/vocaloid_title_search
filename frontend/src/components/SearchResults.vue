<script setup lang="ts">
import { computed, watch } from "vue";
import { ChevronRight, ExternalLink } from "@lucide/vue";
import VideoSections from "./VideoSections.vue";
import { useSongDetails } from "../composables/useSongDetails";
import type { SearchResult, SongDetail, CreditKey } from "../types";
import type { ResultColumns } from "../result-columns";
const props = defineProps<{ searchResults: SearchResult[]; showColumns: ResultColumns }>();
const { expandedUrls, detailCache, detailErrors, loadingDetails, toggleDetail, retryDetail, detailLoadingText, reset } = useSongDetails();
watch(() => props.searchResults, reset);
const hasVisibleMetaColumns = computed(() => (
  props.showColumns.count
  || props.showColumns.artist
  || props.showColumns.publishedYear
  || props.showColumns.popularity
  || props.showColumns.popularityLabel
));

const visibleColumnCount = computed(() => {
  const baseColumns = 2;
  return baseColumns
    + Number(props.showColumns.count)
    + Number(props.showColumns.artist)
    + Number(props.showColumns.publishedYear)
    + Number(props.showColumns.popularity)
    + Number(props.showColumns.popularityLabel);
});

const visibleMetaColumnCount = computed(() => (
  Number(props.showColumns.count)
  + Number(props.showColumns.artist)
  + Number(props.showColumns.publishedYear)
  + Number(props.showColumns.popularity)
  + Number(props.showColumns.popularityLabel)
));

function firstVisibleMetaKey(): string | null {
  if (props.showColumns.count) return "title_length";
  if (props.showColumns.artist) return "artist";
  if (props.showColumns.publishedYear) return "published_year";
  if (props.showColumns.popularity) return "popularity_score";
  if (props.showColumns.popularityLabel) return "popularity_label";
  return null;
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

</script>
<template>
      <div class="table-wrap card-results" :class="{ 'compact-results': !hasVisibleMetaColumns }">
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
                    <VideoSections :detail="detailCache.get(row.url)!" />
                  </template>
                  <div v-else class="detail-loading">表示できる詳細情報が見つかりませんでした。</div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      </div>
</template>
