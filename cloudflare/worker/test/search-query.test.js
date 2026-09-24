import assert from "node:assert/strict";
import { before, it } from "node:test";
import { build } from "esbuild";
let parseSearchParams;
before(async () => {
  const result = await build({ entryPoints: ["src/search-query.ts"], bundle: true, write: false, format: "esm", platform: "browser" });
  ({ parseSearchParams } = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString("base64")}`));
});
it("normalizes composer names using Python-compatible casefold, including final sigma", () => {
  for (const [value, expected] of [["Straße", "strasse"], ["ΟΣ", "οσ"], ["ος", "οσ"], [" ＲＹＯ ", "ryo"], ["\u0085Straße\u001c", "strasse"], ["İ", "i\u0307"], ["Ꭰꭰ", "ᎠᎠ"]]) {
    assert.equal(parseSearchParams(new URLSearchParams({ composer: value })).composer, expected);
  }
});
