import { expect, type Page, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("searches songs, opens detail, paginates, and applies stats filters", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Vocaloid Title Search" })).toBeVisible();
  await expect(page.getByText("条件を指定して検索")).toBeVisible();

  await page.getByLabel("文字数").fill("3");
  await page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索" }).click();

  await expect(page.getByText("1-50 / 51件")).toBeVisible();
  await expect(page.getByText("メルト")).toBeVisible();
  await expect(page.getByText("短曲")).toBeVisible();

  await page.getByRole("button", { name: /メルトの詳細を開く/ }).click();
  await expect(page.getByText("基本情報")).toBeVisible();
  await expect(page.getByText("作曲: ryo")).toBeVisible();
  await expect(page.getByText("曲紹介")).toBeVisible();

  await page.getByRole("button", { name: "次のページへ" }).click();
  await expect(page.getByText("51-51 / 51件")).toBeVisible();
  await expect(page.getByText("長い曲名")).toBeVisible();

  await page.getByRole("button", { name: "統計" }).click();
  await expect(page.getByText("タイトル文字数")).toBeVisible();
  await page.getByRole("button", { name: /7文字/ }).click();

  await expect(page.getByText("統計から適用")).toBeVisible();
  await expect(page.getByText("7文字")).toBeVisible();
});

async function mockApi(page: Page): Promise<void> {
  await page.route("**/api/metadata", async (route) => {
    await route.fulfill({ json: metadata });
  });
  await page.route("**/api/popularity-labels", async (route) => {
    await route.fulfill({ json: { labels: ["テンミリオン達成曲", "ミリオン達成曲", "殿堂入り"] } });
  });
  await page.route("**/api/search?**", async (route) => {
    const url = new URL(route.request().url());
    const pageNumber = Number.parseInt(url.searchParams.get("page") ?? "1", 10);
    const byStats = url.searchParams.get("length") === "7";
    const results = byStats
      ? [song("きゅうくらりん", 7, "https://w.atwiki.jp/hmiku/pages/1.html", 2021)]
      : pageNumber === 1
        ? [
            song("メルト", 3, "https://w.atwiki.jp/hmiku/pages/82.html", 2007),
            song("短曲", 2, "https://w.atwiki.jp/hmiku/pages/83.html", 2020),
          ]
        : [song("長い曲名", 4, "https://w.atwiki.jp/hmiku/pages/84.html", 2024)];
    await route.fulfill({
      json: {
        total: byStats ? 1 : 51,
        page: pageNumber,
        page_size: 2,
        results,
      },
    });
  });
  await page.route("**/api/song-detail?**", async (route) => {
    await route.fulfill({ json: songDetail });
  });
  await page.route("**/api/stats", async (route) => {
    await route.fulfill({ json: statistics });
  });
}

const metadata = {
  schema_version: "7",
  fetched_at: "2026-06-09T00:00:00+00:00",
  song_count: "3",
  title_length_rule: "unicode_nfc_grapheme_cluster_whitespace_excluded",
  detail_schema_version: "1",
  detail_count: "3",
};

const songDetail = {
  page_title: "メルト",
  reading: "めると",
  credits: {
    composer: ["ryo"],
  },
  introduction: ["代表的なVOCALOID曲。"],
  videos: {
    niconico: [],
    youtube: [],
  },
  related_videos: {
    niconico: [],
    youtube: [],
  },
  published_year: 2007,
};

const statistics = {
  total_songs: 3,
  detail_count: 3,
  with_composer: 2,
  with_published_year: 3,
  by_title_length: [
    { length: 3, count: 2 },
    { length: 7, count: 1 },
  ],
  by_published_year: [
    { year: 2007, count: 1 },
    { year: 2021, count: 1 },
  ],
  by_popularity_label: [
    { label: "テンミリオン達成曲", count: 1 },
    { label: "ミリオン達成曲", count: 1 },
  ],
  top_composers: [
    { name: "ryo", count: 1 },
    { name: "いよわ", count: 1 },
  ],
};

function song(title: string, titleLength: number, url: string, publishedYear: number) {
  return {
    title,
    title_length: titleLength,
    artist: title === "メルト" ? "ryo" : "",
    artist_note: "",
    url,
    popularity_score: 1000,
    popularity_label: "テンミリオン達成曲",
    published_year: publishedYear,
  };
}
