import { expect, test } from "@playwright/test";

test("browser searches real Worker and local D1, opens details and paginates", async ({ page, request }) => {
  const health = await request.get("http://127.0.0.1:8789/health");
  expect(await health.json()).toMatchObject({ database_ready: true });
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
