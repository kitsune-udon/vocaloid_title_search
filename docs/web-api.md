# Web API

Cloudflare Worker API は検索、統計、metadata、曲詳細参照の API を提供します。公開運用では D1 を読み取り用に参照し、リクエスト時に外部 Wiki や外部動画メタデータ取得へアクセスしません。

この文書はHTTP APIの契約だけを扱います。ローカル開発サーバーの起動、ローカルD1へのデータ投入、ポート競合時の確認方法は [usage.md](usage.md#local-dev-server) を参照してください。

本番では `cloudflare/worker/wrangler.toml` の D1 binding を使います。このファイルは ignore 対象で、実ドメインや D1 ID を追跡ファイルへ入れません。Worker routes は Terraform 管理なので `wrangler.toml` には書きません。

CORS を許可する origin はWorkerの `CORS_ORIGINS` にカンマ区切りで指定します。

```bash
CORS_ORIGINS=https://staging.vocaloid-title-search.example.com,https://vocaloid-title-search.example.com
```

## Contract Files

API契約を変える場合は、次を同時に確認します。

| 対象 | 役割 |
| --- | --- |
| `cloudflare/worker/src/index.ts` | 実際のWorker API実装 |
| `shared/api-types.ts` | frontend と Worker が共有するレスポンス型 |
| `frontend/src/api.ts` | frontend 側のfetchとエラー処理 |
| `cloudflare/worker/test/worker-api.test.js` | Worker API contract test |
| `docs/web-api.md` | 人間向けAPI仕様 |

レスポンスのfield追加、validation変更、エラー本文変更、pagination変更はAPI契約の変更として扱います。

## Common Responses

| Status | 意味 | 主な確認先 |
| --- | --- | --- |
| `200` | 正常応答 | レスポンス本文 |
| `400` | query parameter が不正 | API仕様、フロントの送信値 |
| `404` | 指定した曲詳細がDBにない | `song_details` と投入先D1 |
| `503` | D1が未準備、空、metadata不足、schema不一致 | `/health`, [operations.md](operations.md#troubleshooting) |

Worker は通常リクエスト時に外部Wikiや動画サイトへ再取得しません。`404` や `503` は、基本的にD1へ投入済みのデータ状態を確認します。

エラーレスポンスの本文は原則として `detail` を返します。

```json
{
  "detail": "page_size must be one of 50, 100, 200"
}
```

## UI Mapping

Web UI は、画面ごとに次のAPIを使います。API契約を変える場合は、対応する画面表示とエラー表示も確認します。

| UI | 主なAPI | 使う目的 | 失敗時の見え方 |
| --- | --- | --- | --- |
| 初期データ表示 | `/api/metadata`, `/api/popularity-labels` | DB状態、取得日時、根拠タグ候補 | DB未準備または初期化失敗 |
| 検索結果 | `/api/search` | 条件検索、ページング、並び替え | 条件エラー、空結果、DB未準備 |
| 詳細アコーディオン | `/api/song-detail` | 基本情報、曲紹介、動画、関連動画 | 詳細未投入、URL不正、DB未準備 |
| 統計ビュー | `/api/stats` | 文字数、公開年、根拠タグ、作曲者分布 | 統計取得失敗、DB未準備 |
| smoke test | `/health` と主要API | 公開経路とD1 bindingの確認 | deploy、route、D1投入の切り分け |

フロントエンドは、`400` を入力条件の問題、`404` を詳細データ未投入または未登録、`503` をDB準備不足として扱います。詳しい画面方針は [frontend-ui.md](frontend-ui.md) を参照してください。

## Timing Logs

Worker は `API_TIMING_LOGS` が `0` でない場合、各リクエスト後に構造化ログを出します。

```json
{
  "event": "api_timing",
  "method": "GET",
  "path": "/api/search",
  "status": 200,
  "duration_ms": 12.34
}
```

ローカルテストではノイズを避けるため `API_TIMING_LOGS=0` を使えます。遅いAPIを調べる場合は [testing.md](testing.md#api-profiling) の `tools/profile_worker_api.py` を使います。

## GET /health

DB readiness を返します。

```json
{
  "ok": true,
  "database_ready": true
}
```

`database_ready:false` は、Worker自体は応答しているものの、検索に必要なD1データが揃っていない状態です。主な原因は、D1投入失敗、`metadata` 不足、schema version 不一致、曲数と詳細件数の不一致、またはWorkerが想定外のD1 bindingを見ていることです。

`database_ready:false` の場合は、[operations.md](operations.md#troubleshooting) の手順でD1投入とWorker bindingを確認します。

readiness判定の主な確認項目:

| 項目 | 意味 |
| --- | --- |
| D1 binding `DB` | Workerが想定するD1を見ている |
| `songs` が空でない | 曲一覧が投入済み |
| `metadata.schema_version` | Workerが期待するschemaと一致 |
| `metadata.detail_schema_version` | Workerが期待する曲詳細schemaと一致 |
| `metadata.song_count` | 実際の曲数と一致 |
| `metadata.detail_count` | 実際の詳細件数と一致 |
| `song_details` 件数 | 曲数と一致している |

## GET /api/search

タイトル文字数、作曲者、公開年、根拠タグで検索します。すべて未指定の場合は、DB全体を指定した並び順でページングして返します。

Query parameters:

| Parameter | 必須 | 内容 |
| --- | --- | --- |
| `length` | 任意 | 検索するタイトル文字数。未指定時は文字数で絞り込まない |
| `sort` | 任意 | `popularity`, `title_length_asc`, `title_length_desc`, `published_year_asc`, `published_year_desc`。未指定時は `popularity` |
| `popularity_label` | 任意 | 根拠タグフィルター。複数指定可 |
| `composer` | 任意 | 曲詳細由来の作曲者部分一致フィルター |
| `year` | 任意 | 初音ミク Wiki の詳細ページ内の年タグなどから推定した公開年 |
| `page` | 任意 | 1始まりのページ番号。未指定時は `1` |
| `page_size` | 任意 | 1ページの件数。`50`, `100`, `200`。未指定時は `50` |

Examples:

```text
/api/search?length=7
/api/search?composer=ryo
/api/search?year=2021
/api/search?popularity_label=ミリオン達成曲&popularity_label=テンミリオン達成曲
/api/search?sort=published_year_desc&page=2&page_size=100
```

Response:

```json
{
  "total": 123,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "title": "サンプル曲",
      "title_length": 7,
      "artist": "作者名",
      "artist_note": "",
      "url": "https://w.atwiki.jp/hmiku/pages/123.html",
      "popularity_score": 1000,
      "popularity_label": "テンミリオン達成曲",
      "published_year": 2021
    }
  ]
}
```

Empty result response:

```json
{
  "total": 0,
  "page": 1,
  "page_size": 50,
  "results": []
}
```

Validation:

| Parameter | 正常例 | エラー例 | Status | `detail` |
| --- | --- | --- | ---: | --- |
| `length` | `7`, 空欄 | `abc`, `-1` | `400` | `length must be an integer` |
| `year` | `2021`, 空欄 | `abcd`, `-1` | `400` | `year must be an integer` |
| `page` | `1` 以上 | `0` | `400` | `page must be 1 or greater` |
| `page_size` | `50`, `100`, `200` | `25` | `400` | `page_size must be one of 50, 100, 200` |
| `sort` | 下記sort値 | `wiki` | `400` | `sort is not supported` |
| `popularity_label` | DBに存在するタグ | 未知のタグ | `400` | `invalid popularity_label` |

`composer` は空文字なら未指定扱いです。DB が未作成、空、または metadata 不足の場合は `503` を返します。

Pagination:

- `page` は1始まり
- `page_size` は `50`, `100`, `200`
- `total` は全一致件数
- `results` は指定ページの件数だけ返す
- 最終ページを超えた場合、`total` は維持し、`results` は空配列になることがある

Validation error response:

```json
{
  "detail": "page_size must be one of 50, 100, 200"
}
```

DB not ready response:

```json
{
  "detail": "database is not ready"
}
```

`composer` は `song_details` の `credits.composer` から作った検索用テーブルを参照します。作曲者クレジットを抽出できていない曲は対象外です。
レスポンスの `artist` も、タグページ由来の `songs.artist` ではなく曲詳細由来の `credits.composer` を返します。曲詳細に作曲者がない場合は空文字です。

代表的なエラー:

| Status | 例 | 主な原因 |
| --- | --- | --- |
| `400` | `{"detail":"page_size must be one of 50, 100, 200"}` | query parameter不正 |
| `503` | `{"detail":"database is not ready"}` | D1未投入、metadata不足、schema不一致 |

## GET /api/stats

DB全体の統計情報を返します。統計ビューはこのAPIを使います。DB が未作成、空、または metadata 不足の場合は `503` を返します。

Response:

```json
{
  "total_songs": 1234,
  "detail_count": 1234,
  "with_composer": 980,
  "with_published_year": 760,
  "by_title_length": [
    {"length": 7, "count": 120}
  ],
  "by_published_year": [
    {"year": 2021, "count": 45}
  ],
  "by_popularity_label": [
    {"label": "ミリオン達成曲", "count": 300}
  ],
  "top_composers": [
    {"name": "DECO*27", "count": 42}
  ]
}
```

DB not ready response:

```json
{
  "detail": "database is not ready"
}
```

`top_composers` は曲詳細由来の `credits.composer` を集計し、上位30件を返します。

統計ビューはこのAPIの各bucketを検索条件へ変換します。文字数bucketは `length`、公開年bucketは `year`、根拠タグbucketは `popularity_label`、作曲者bucketは `composer` として検索ビューへ渡します。統計から検索へ移動する時は、前回の検索条件を引き継がず、選択したbucketを中心に検索します。

## GET /api/metadata

DB の `metadata` テーブルを返します。DB が未作成、空、または metadata 不足の場合は `503` を返します。

metadataは、Web UI のデータ状態表示、運用時のD1投入確認、smoke testで使います。通常ユーザーが直接見るための詳細データではありません。

主なフィールド:

| Field | 内容 |
| --- | --- |
| `schema_version` | DB schema version |
| `source_url` | 代表取得元 URL |
| `fetched_at` | DB 作成時刻 |
| `song_count` | 登録曲数 |
| `title_length_rule` | 文字数計算ルール |
| `popularity_source_tags` | 人気度計算に使った根拠タグ一覧 |
| `publication_year_source` | 公開年推定に使った情報源 |
| `detail_schema_version` | 曲詳細スキーマバージョン |
| `detail_count` | 保存済み曲詳細件数 |

DB not ready response:

```json
{
  "detail": "database is not ready"
}
```

## GET /api/popularity-labels

DB 内に存在する根拠タグ一覧を、スコアの高い順に返します。DB が未作成、空、または metadata 不足の場合は `503` を返します。

## GET /api/song-detail

曲ページ URL を指定し、DBに保存済みの構造化詳細情報を返します。

Query parameters:

| Parameter | 必須 | 内容 |
| --- | --- | --- |
| `url` | 必須 | `https://w.atwiki.jp/hmiku/pages/<数字>.html` 形式の Wiki ページ URL |

Example:

```text
/api/song-detail?url=https%3A%2F%2Fw.atwiki.jp%2Fhmiku%2Fpages%2F123.html
```

Validation:

- 許可されていない URL は `400`
- DB が未作成、空、または metadata 不足の場合は `503`
- 曲詳細が存在しない場合は `404`

代表的なエラー:

| Status | 例 | 主な原因 |
| --- | --- | --- |
| `400` | `{"detail":"invalid wiki url"}` | 許可外URL |
| `404` | `{"detail":"song detail is not available"}` | `song_details` に該当URLがない |
| `503` | `{"detail":"database is not ready"}` | D1未準備 |

レスポンス形式と抽出ルールは [detail-extraction.md](detail-extraction.md) を参照してください。

## CORS Troubleshooting

CORSを変更した場合は、staging / production の両方で確認します。

| 症状 | 主な原因 | 確認 |
| --- | --- | --- |
| ブラウザだけ失敗し `curl` は成功 | `CORS_ORIGINS` に画面のoriginがない | `wrangler.toml` 生成元 |
| stagingだけ失敗 | staging custom domainのorigin漏れ | staging Worker env |
| productionだけ失敗 | production custom domainのorigin漏れ | production Worker env |
| preflightが失敗 | allowed headers / methods不足 | Worker CORS処理 |
