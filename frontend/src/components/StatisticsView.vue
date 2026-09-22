<script setup lang="ts">
import { ref } from "vue";
import type { StatisticsResponse, TitleLengthBucket, PublishedYearBucket, PopularityLabelBucket, ComposerBucket } from "../types";
defineProps<{ statistics: StatisticsResponse | null; isStatsLoading: boolean; statsError: string }>();
const activeStatsPanel = defineModel<string>({ required: true });
const emit = defineEmits<{ length: [TitleLengthBucket]; year: [PublishedYearBucket]; popularity: [PopularityLabelBucket]; composer: [ComposerBucket] }>();
const statsTouchStartX = ref<number | null>(null);
const statsPanels = [
  { key: "title_length", label: "文字数" },
  { key: "published_year", label: "公開年" },
  { key: "popularity_label", label: "根拠タグ" },
  { key: "composer", label: "作曲者" },
] as const;

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

</script>
<template>
    <section class="stats-view" aria-label="統計">
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
                @click="emit('length', bucket)"
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
                @click="emit('year', bucket)"
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
                @click="emit('popularity', bucket)"
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
                @click="emit('composer', bucket)"
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
</template>
