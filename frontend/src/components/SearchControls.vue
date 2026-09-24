<script setup lang="ts">
import { RotateCcw, Search as SearchIcon, X } from "@lucide/vue";
import type { SortOrder } from "../types";
defineProps<{ isSearching: boolean; disabled: boolean; formError: string; popularityLabels: string[]; selectedPopularityLabels: Set<string> }>();
const titleLength = defineModel<string>("titleLength", { required: true });
const composerQuery = defineModel<string>("composerQuery", { required: true });
const publishedYear = defineModel<string>("publishedYear", { required: true });
const sort = defineModel<SortOrder>("sort", { required: true });
const emit = defineEmits<{
  search: []; reset: []; clearError: []; sort: [];
  preset: [value: "default" | "all" | "none"]; toggleLabel: [label: string];
}>();
</script>
<template>
      <div class="filter-content">
        <form class="controls" @submit.prevent="emit('search')">
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
                @click="titleLength = ''; emit('clearError')"
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
                @click="composerQuery = ''; emit('clearError')"
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
                @click="publishedYear = ''; emit('clearError')"
              >
                <X aria-hidden="true" />
              </button>
            </span>
          </label>
          <div class="controls-actions">
            <button type="submit" :disabled="isSearching || disabled">
              <SearchIcon class="button-icon" aria-hidden="true" />
              {{ isSearching ? "検索中" : "検索" }}
            </button>
            <button class="secondary-button" type="button" @click="emit('reset')">
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
              <button type="button" :disabled="disabled" @click="emit('preset', 'default')">既定</button>
              <button type="button" :disabled="disabled" @click="emit('preset', 'all')">全て</button>
              <button type="button" :disabled="disabled" @click="emit('preset', 'none')">指定なし</button>
            </div>
          </div>
          <div class="tag-filters">
            <label v-for="label in popularityLabels" :key="label" class="toggle">
              <input
                type="checkbox"
                :checked="selectedPopularityLabels.has(label)"
                @change="emit('toggleLabel', label)"
              />
              {{ label }}
            </label>
          </div>
        </div>

        <div class="sort-row">
          <div class="sort-title">並び順</div>
          <select v-model="sort" class="sort-control" @change="emit('sort')">
            <option value="popularity">人気度順</option>
            <option value="title_length_asc">文字数昇順</option>
            <option value="title_length_desc">文字数降順</option>
            <option value="published_year_asc">公開年昇順</option>
            <option value="published_year_desc">公開年降順</option>
          </select>
        </div>
      </div>
</template>
