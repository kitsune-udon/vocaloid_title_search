# CLI Reference

CLI は役割ごとに module を分けています。この文書はオプションと既定値の参照用です。ローカル開発の流れは [usage.md](usage.md)、staging / production へのD1投入は [operations.md](operations.md) を参照してください。

オプションを変更した場合は、実装の `--help` とこの文書を同時に更新します。`--db-path` の既定値は `--help` では解決済みの絶対パスとして表示される場合がありますが、この文書ではプロジェクト直下の論理パス `vocaloid_titles.sqlite3` として表記します。

| Command | 役割 |
| --- | --- |
| `python -m vocaloid_title_search.cli.build_db` | Wiki から曲一覧と曲詳細を取得し、検索DBを作成 |
| `python -m vocaloid_title_search.cli.refresh_video_metadata` | 既存DB内の動画IDから動画タイトルとサムネイルURLを更新 |
| `python -m vocaloid_title_search.cli.validate_db` | 作成済みDBの品質と整合性を検査 |
| `python -m vocaloid_title_search.cli.report_detail_quality` | 保存済み曲詳細JSONの欠損候補を一覧化 |
| `python -m vocaloid_title_search.cli.search_titles` | 作成済みDBを検索 |

| Command | 外部ネットワーク | 書き込み |
| --- | --- | --- |
| `build_db` | 初音ミク Wiki | ローカルSQLiteを差し替える |
| `refresh_video_metadata` | YouTube / ニコニコ | ローカルSQLite内の詳細JSONを更新 |
| `validate_db` | なし | なし |
| `report_detail_quality` | なし | なし |
| `search_titles` | なし | なし |

影響範囲:

- `build_db` は外部Wikiへアクセスし、ローカルSQLiteを差し替えます。D1は変更しません。
- `refresh_video_metadata` は外部動画サービスへアクセスし、ローカルSQLite内の詳細JSONを更新します。曲詳細ページは再取得せず、D1も変更しません。
- `validate_db` はローカルSQLiteを読み取るだけです。D1投入前やデプロイ前の品質確認に使います。
- `report_detail_quality` はローカルSQLiteを読み取り、詳細抽出の欠損候補を一覧化します。DBは変更しません。
- `search_titles` はローカルSQLiteを読み取るだけです。

## build_db

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db
```

| Option | Default | 内容 |
| --- | ---: | --- |
| `--db-path` | `vocaloid_titles.sqlite3` | SQLite DB の保存先 |
| `--source-url` | 殿堂入りタグURL | 曲一覧の代表取得元 |
| `--workers` | `8` | 曲詳細ページ取得の最大並列数 |
| `--timeout` | `20.0` | 1 HTTP リクエストのタイムアウト秒数 |
| `--request-interval` | `0.2` | 同一ホストへの最小リクエスト間隔秒数 |
| `--max-retries` | `2` | 429/502/503/504 の最大リトライ回数 |
| `--backoff-base` | `2.0` | Retry-After がない場合の初回待機秒数 |
| `--backoff-max` | `30.0` | バックオフ待機の最大秒数 |

DB構築CLIは一時DBを構築してから `os.replace()` で差し替えます。曲詳細が全件揃わない場合は完成DBとして置き換えません。

負荷調整の目安:

| 目的 | 例 |
| --- | --- |
| 相手サイトへの負荷を下げる | `--workers 4 --request-interval 0.5` |
| 一時的な503に粘る | `--max-retries 4 --backoff-max 60` |
| ローカル検証で既定値を使う | optionなし |

`--workers` を増やしても、同一ホストへの `--request-interval` は守ります。高速化より安定性と相手サイトへの負荷を優先します。

## refresh_video_metadata

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.refresh_video_metadata
```

このコマンドは曲詳細ページを再取得せず、DB内の動画IDから動画サービスのメタデータだけを取得します。Wikiへのアクセスではないため、`--request-interval` の既定値は `build_db` より短くしています。

| Option | Default | 内容 |
| --- | ---: | --- |
| `--db-path` | `vocaloid_titles.sqlite3` | 更新対象の SQLite DB |
| `--workers` | `32` | 動画メタデータ取得の最大並列数 |
| `--timeout` | `20.0` | 1 HTTP リクエストのタイムアウト秒数 |
| `--request-interval` | `0.0` | 同一ホストへの最小リクエスト間隔秒数 |
| `--max-retries` | `2` | 429/502/503/504 の最大リトライ回数 |
| `--backoff-base` | `2.0` | Retry-After がない場合の初回待機秒数 |
| `--backoff-max` | `30.0` | バックオフ待機の最大秒数 |

このコマンドは曲詳細ページを再取得しません。`song_details.payload_json` 内の `videos` / `related_videos` からユニークな動画IDを集め、動画メタデータだけを書き戻します。

再実行しても、同じ動画IDは同じ詳細JSON内で更新されるだけです。途中失敗後に再実行できます。外部動画サービスに到達できないIDは、既存値またはフォールバック値が残ることがあります。

## validate_db

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.validate_db
```

| Option | Default | 内容 |
| --- | ---: | --- |
| `--db-path` | `vocaloid_titles.sqlite3` | 検査対象の SQLite DB |
| `--json` | `false` | 検査結果をJSONで出力 |

このコマンドはDBへ書き込まず、外部ネットワークにもアクセスしません。次の項目を確認します。

- 必須テーブルが存在するか
- `metadata` の schema version、曲数、詳細件数が実テーブルと一致するか
- `songs` と `song_details` の件数が一致するか
- `song_details.payload_json` がJSONとして壊れていないか
- `song_credit_people` や `song_details` に孤立行がないか
- 作曲者、公開年、動画、サムネイル、動画タイトルの件数

検査に失敗した場合は終了コード `1` を返します。D1へ投入する前、または `tools/check_all.sh` で失敗原因を切り分けるときに使います。

`tools/update_d1.sh` はD1 SQLを生成する前にこの検査を実行します。検査に失敗したDBはstaging / production D1へ投入されません。

`validate_db` と `report_detail_quality` の使い分け:

| コマンド | 目的 | 失敗扱い | 主な利用タイミング |
| --- | --- | --- | --- |
| `validate_db` | DB全体が検索・D1投入に使えるか確認する | schema、metadata、件数、JSON破損の不整合は失敗 | D1投入前、DB更新後 |
| `report_detail_quality` | 詳細抽出の改善候補を探す | 欠損候補があっても失敗ではない | 抽出ロジック改善、データ品質レビュー |

## report_detail_quality

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.report_detail_quality
```

| Option | Default | 内容 |
| --- | ---: | --- |
| `--db-path` | `vocaloid_titles.sqlite3` | 検査対象の SQLite DB |
| `--limit` | `100` | 表示する曲数。`0` なら件数だけ表示 |
| `--json` | `false` | レポートをJSONで出力 |

このコマンドは保存済みの `song_details.payload_json` を読み、次の欠損候補を曲名・URL付きで表示します。

- `missing_credits`
- `missing_composer`
- `suspicious_composer`
- `missing_introduction`
- `missing_primary_videos`
- `missing_published_year`
- `suspicious_published_year`
- `published_year_mismatch`
- `invalid_json`

DB構築の成否を判定する `validate_db` とは目的が異なります。`report_detail_quality` は、欠損が許容される項目や不自然に見える作曲者・公開年もレビュー対象として拾い、抽出ロジック改善の優先順位を決めるために使います。

## search_titles

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.search_titles 3
```

| Option | Default | 内容 |
| --- | ---: | --- |
| `n` | 必須 | 検索するタイトル文字数 |
| `--db-path` | `vocaloid_titles.sqlite3` | SQLite DB の参照先 |
| `--sort` | `popularity` | `popularity`, `title_length_asc`, `title_length_desc`, `published_year_asc`, `published_year_desc` |
| `--show-count` | `false` | 文字数を出力 |
| `--show-artist` | `false` | 作曲者を出力 |
| `--show-artist-note` | `false` | 作曲者補足を出力 |
| `--show-url` | `false` | Wiki URL を出力 |
| `--show-popularity` | `false` | 人気度スコアと根拠タグを出力 |
| `--show-year` | `false` | 公開年を出力 |
