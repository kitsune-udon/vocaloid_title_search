import { expect, test } from "@playwright/test";

test("browser searches real Worker and local D1, opens details and paginates", async ({ page, request }) => {
  const health = await request.get("http://127.0.0.1:8789/health");
  expect(await health.json()).toMatchObject({ database_ready: true });
  expect(health.headers()["x-d1-rows-read"]).toBe("1");
  const stats = await request.get("http://127.0.0.1:8789/api/stats");
  expect(stats.headers()["x-d1-rows-read"]).toBe("1");
  expect((await stats.json()).total_songs).toBe(56);
  await page.goto("/");
  await page.getByLabel("文字数").fill("3");
  await page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索" }).click();
  await expect(page.getByText("1-50 / 51件")).toBeVisible();
  await page.getByRole("button", { name: /検証.*の詳細を開く/ }).first().click();
  await expect(page.getByText("結合テスト用のデータ")).toBeVisible();
  await expect(page.getByText("作曲: 検証作者")).toBeVisible();
  await page.getByRole("button", { name: "次のページへ" }).click();
  await expect(page.getByText("51-51 / 51件")).toBeVisible();
  await page.getByRole("button", { name: "統計" }).click();
  await page.getByRole("button", { name: /3文字/ }).click();
  await expect(page.getByText("統計から適用")).toBeVisible();
  const invalid = await request.get("http://127.0.0.1:8789/api/search?length=-1");
  expect(invalid.status()).toBe(400);
});


test("real D1 preserves totals for single and combined filters and caches normalized requests", async ({ request }) => {
  for (const [query, total] of [
    ["length=3", 51], ["length=999", 0], ["year=2020", 51], ["year=1999", 0],
    ["composer=検証&length=3&year=2020", 51], ["composer=該当なし", 0],
    ["popularity_label=テンミリオン達成曲", 51], ["length=3&year=1999", 0],
  ] as const) {
    const response = await request.get(`http://127.0.0.1:8789/api/search?${query}`);
    expect(response.status()).toBe(200);
    expect((await response.json()).total).toBe(total);
  }
  await request.get("http://127.0.0.1:8789/api/search?composer=検証&page=2");
  const cached = await request.get("http://127.0.0.1:8789/api/search?page=2&composer=検証&page_size=50&sort=popularity");
  expect(cached.headers()["x-search-cache"]).toBe("hit");
  expect(cached.headers()["x-d1-rows-read"]).toBe("1");
  expect((await cached.json()).results).toHaveLength(1);
});


test("Worker composer normalization matches the Python-built index", async ({ request }) => {
  for (const composer of ["Straße", "STRASSE", "ＳＴＲＡＳＳＥ", "ΟΣ", "ος", "οσ"]) {
    const response = await request.get(`http://127.0.0.1:8789/api/search?${new URLSearchParams({ composer })}`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.total).toBe(1);
    expect(data.results[0].url).toBe("https://w.atwiki.jp/hmiku/pages/51.html");
  }
});


test("page sizes and optional result columns work with real results", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("作曲者", { exact: true }).fill("検証");
  await page.getByLabel("検索", { exact: true }).getByRole("button", { name: "検索", exact: true }).click();
  await expect(page.locator(".song-row")).toHaveCount(50);
  for (const size of ["100", "200", "50"]) {
    await page.getByRole("combobox", { name: "表示数", exact: true }).selectOption(size);
    await expect(page.locator(".song-row")).toHaveCount(size === "50" ? 50 : 51);
  }
  await page.getByLabel("結果カードに表示する項目を選ぶ", { exact: true }).click();
  const options = page.locator(".view-options-content");
  for (const label of ["文字数", "作曲者", "公開年", "人気度", "根拠タグ"]) {
    await options.getByRole("checkbox", { name: label, exact: true }).check();
  }
  const first = page.locator(".song-row").first();
  await expect(first.locator('[data-key="artist"]')).toHaveText("検証作者");
  await expect(first.locator('[data-key="published_year"]')).toHaveText("2020");
  await expect(first.locator('[data-key="title_length"]')).toHaveText("3");
  await expect(first.locator('[data-key="popularity_label"]')).toHaveText("テンミリオン達成曲");
});


test("all sorts follow independent expected orders with ties and missing years", async ({ request }) => {
  const orders = {
    popularity: [105, 102, 103, 101, 104],
    title_length_asc: [101, 105, 102, 103, 104],
    title_length_desc: [103, 104, 105, 102, 101],
    published_year_asc: [105, 102, 104, 101, 103],
    published_year_desc: [101, 105, 102, 104, 103],
  };
  for (const [sort, ids] of Object.entries(orders)) {
    const query = new URLSearchParams({ composer: "順序確認", sort });
    const response = await request.get(`http://127.0.0.1:8789/api/search?${query}`);
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.total).toBe(5);
    expect(data.results.map((row: { url: string }) => row.url)).toEqual(
      ids.map(id => `https://w.atwiki.jp/hmiku/pages/${id}.html`),
    );
  }
});
