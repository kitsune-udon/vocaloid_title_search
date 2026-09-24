import { expect, type Page, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("searches songs, opens detail, paginates, and applies stats filters", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("navigation", { name: "表示切替" })).toBeVisible();
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

test("search conditions stay at the top and remain usable from statistics", async ({ page }) => {
  await page.route("**/api/search?**", route => route.fulfill({ json: {
    total: 50, page: 1, page_size: 50,
    results: Array.from({ length: 50 }, (_, i) => song(`検証${i}`, 3, `https://w.atwiki.jp/hmiku/pages/${i + 1}.html`, 2020)),
  } }));
  await page.goto("/");
  const dock = page.getByRole("region", { name: "検索", exact: true });
  const bounds = await dock.boundingBox();
  const navigation = await page.getByRole("navigation", { name: "表示切替" }).boundingBox();
  expect(bounds!.y).toBe(0);
  const summary = await dock.locator("summary").boundingBox();
  expect(navigation!.y).toBeGreaterThanOrEqual(summary!.y);
  expect(navigation!.y + navigation!.height).toBeLessThanOrEqual(summary!.y + summary!.height);
  await page.getByRole("button", { name: "統計", exact: true }).click();
  await expect(dock.locator("details")).toHaveAttribute("open", "");
  await page.getByRole("navigation", { name: "表示切替" }).getByRole("button", { name: "検索", exact: true }).click();
  await page.getByLabel("文字数").fill("3");
  await dock.getByRole("button", { name: "検索", exact: true }).click();
  await expect(page.locator(".status")).toHaveText("1-50 / 50件");
  await page.evaluate(() => window.scrollTo({ top: 1200, behavior: "instant" }));
  await expect.poll(async () => (await dock.boundingBox())!.y).toBe(0);
  await dock.locator("summary").click();
  await expect(dock.getByRole("textbox", { name: /^文字数/ })).toBeVisible();
  expect((await dock.boundingBox())!.height).toBeLessThan(page.viewportSize()!.height * 0.8);
  await page.getByRole("button", { name: "統計", exact: true }).click();
  await expect(page.getByText("タイトル文字数", { exact: true })).toBeVisible();
  await dock.getByRole("button", { name: "検索", exact: true }).click();
  await expect(page.getByRole("region", { name: "検索結果", exact: true })).toBeVisible();
});

test("a newer stats search supersedes an in-flight search", async ({ page }) => {
  let releaseOld!: () => void;
  const oldResponse = new Promise<void>(resolve => { releaseOld = resolve; });
  await page.route("**/api/search?**", async route => {
    const length = new URL(route.request().url()).searchParams.get("length");
    if (length === "3") {
      await oldResponse;
      await route.fulfill({ json: { total: 1, page: 1, page_size: 50,
        results: [song("古い検索結果", 3, "https://w.atwiki.jp/hmiku/pages/82.html", 2007)] } });
    } else {
      await route.fallback();
    }
  });
  await page.goto("/");
  await page.getByLabel("文字数").fill("3");
  const started = page.waitForRequest(request => request.url().includes("/api/search?"));
  await page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索" }).click();
  await started;
  await page.getByRole("button", { name: "統計" }).click();
  await page.getByRole("button", { name: /7文字/ }).click();
  try {
    await expect(page.getByText("きゅうくらりん", { exact: true })).toBeVisible();
  } finally {
    releaseOld();
  }
  await expect(page.getByText("古い検索結果", { exact: true })).toHaveCount(0);
  await expect(page.getByText("統計から適用")).toBeVisible();
});

test("pagination keeps the applied filters while form edits remain a draft", async ({ page }) => {
  await page.goto("/");
  const controls = page.getByLabel("検索", { exact: true });
  await page.getByLabel("文字数").fill("3");
  await controls.getByRole("button", { name: "検索", exact: true }).click();
  await expect(page.getByText("1-50 / 51件")).toBeVisible();
  await controls.locator("summary").click();
  await controls.getByRole("textbox", { name: /^文字数/ }).fill("7");
  const request = page.waitForRequest(request => request.url().includes("page=2"));
  await page.getByRole("button", { name: "次のページへ" }).click();
  expect(new URL((await request).url()).searchParams.get("length")).toBe("3");
  await expect(page.getByText("51-51 / 51件")).toBeVisible();
});

test("closing detail aborts its request and reopening loads a fresh detail", async ({ page }) => {
  let releaseOld!: () => void;
  const oldResponse = new Promise<void>(resolve => { releaseOld = resolve; });
  let calls = 0;
  await page.route("**/api/song-detail?**", async route => {
    calls++;
    if (calls === 1) {
      await oldResponse;
      await route.fulfill({ json: { ...songDetail, introduction: ["古い詳細"] } });
    } else {
      await route.fulfill({ json: { ...songDetail, introduction: ["新しい詳細"] } });
    }
  });
  await page.goto("/");
  await page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索", exact: true }).click();
  const failed = page.waitForEvent("requestfailed", request => request.url().includes("/api/song-detail?"));
  await page.getByRole("button", { name: /メルトの詳細を開く/ }).click();
  await expect.poll(() => calls).toBe(1);
  try {
    await page.getByRole("button", { name: /メルトの詳細を閉じる/ }).click();
    await failed;
    await page.getByRole("button", { name: /メルトの詳細を開く/ }).click();
    await expect(page.getByText("新しい詳細", { exact: true })).toBeVisible();
  } finally {
    releaseOld();
  }
  await expect(page.getByText("古い詳細", { exact: true })).toHaveCount(0);
});

test("a stalled search times out and can be retried", async ({ page }) => {
  await page.clock.install();
  let release!: () => void;
  const stalled = new Promise<void>(resolve => { release = resolve; });
  let requests = 0;
  await page.route("**/api/search?**", async route => {
    if (++requests === 1) {
      await stalled;
      await route.abort();
    } else {
      await route.fallback();
    }
  });
  await page.goto("/");
  const search = page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索", exact: true });
  await search.click();
  await expect.poll(() => requests).toBe(1);
  try {
    await page.clock.fastForward(21_000);
    await expect(page.getByText("通信に失敗しました。ネットワーク状態を確認して再実行してください。")).toBeVisible();
    await expect(search).toBeEnabled();
  } finally {
    release();
  }
  await search.click();
  await expect(page.getByText("メルト", { exact: true })).toBeVisible();
});

test("search waits for initial tag defaults and can recover from an initial fetch failure", async ({ page }) => {
  let calls = 0;
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/popularity-labels", async route => {
    calls++;
    if (calls === 1) {
      await pending;
      await route.abort();
    } else {
      await route.fallback();
    }
  });
  await page.goto("/");
  const search = page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索", exact: true });
  try {
    await expect(search).toBeDisabled();
  } finally {
    release();
  }
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(search).toBeDisabled();
  await page.getByRole("button", { name: "再読み込み", exact: true }).click();
  await expect(search).toBeEnabled();
  const requested = page.waitForRequest(request => request.url().includes("/api/search?"));
  await search.click();
  const labels = new URL((await requested).url()).searchParams.getAll("popularity_label");
  expect(labels.length).toBeGreaterThan(0);
  expect(labels).not.toContain("殿堂入り");
});

test("video thumbnails recover from a failed first candidate", async ({ page }) => {
  await page.route("**/api/song-detail?**", route => route.fulfill({ json: {
    ...songDetail,
    videos: { niconico: [{ id: "sm1", title: "検証動画", url: "https://example.test/video",
      thumbnail_url: "https://example.test/thumb-broken.png",
      thumbnail_urls: ["https://example.test/thumb-broken.png", "https://example.test/thumb-good.png"] }],
      youtube: [{ id: "abcdefghijk", title: "YouTube検証動画", url: "https://example.test/youtube",
        thumbnail_url: "https://example.test/thumb-broken.png",
        thumbnail_urls: ["https://example.test/thumb-broken.png", "https://example.test/thumb-good.png"] }] },
  } }));
  await page.route("https://example.test/thumb-broken.png", route => route.fulfill({ status: 404 }));
  await page.route("https://example.test/thumb-good.png", route => route.fulfill({ contentType: "image/png",
    body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=", "base64") }));
  await page.goto("/");
  await page.getByLabel("文字数").fill("3");
  await page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索" }).click();
  await page.getByRole("button", { name: /メルトの詳細を開く/ }).click();
  for (const name of ["検証動画", "YouTube検証動画"]) {
    const image = page.getByRole("img", { name, exact: true });
    await image.scrollIntoViewIfNeeded();
    await expect(image).toHaveAttribute("data-thumbnail-index", "1");
    await expect.poll(() => image.evaluate(node => (node as HTMLImageElement).naturalWidth)).toBe(1);
  }
});

test("keyboard detail toggle and retry recover from a server error", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/song-detail?**", route => ++calls === 1
    ? route.fulfill({ status: 503, json: { detail: "database is being updated" } })
    : route.fulfill({ json: songDetail }));
  await page.goto("/");
  await page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索", exact: true }).click();
  const row = page.getByRole("button", { name: /メルトの詳細を開く/ });
  await row.focus();
  await row.press("Enter");
  await page.getByRole("button", { name: "再試行", exact: true }).click();
  await expect(page.getByText("作曲: ryo")).toBeVisible();
  const expanded = page.getByRole("button", { name: /メルトの詳細を閉じる/ });
  await expanded.press("Space");
  await expect(page.getByText("作曲: ryo")).toHaveCount(0);
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
        page_size: Number(url.searchParams.get("page_size") ?? "50"),
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
