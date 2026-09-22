<script setup lang="ts">
import type { SongDetail, VideoEntry, VideoMap } from "../types";
defineProps<{ detail: SongDetail }>();

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
                    <div
                      v-for="[sectionTitle, videos] in [
                        ['動画', detail.videos],
                        ['関連動画', detail.related_videos],
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
