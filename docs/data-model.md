# Data Model

永続データは SQLite の `vocaloid_titles.sqlite3` に集約します。Wiki 取得や詳細 HTML 解析は `python -m vocaloid_title_search.cli.build_db` の更新ジョブだけが行います。

モジュールやディレクトリの責務は [project-structure.md](project-structure.md) に集約しています。

## Source Of Truth

`vocaloid_titles.sqlite3` は検索データの source of truth です。検索CLIはこのDBを読み、Cloudflare D1 は公開API用の配布先として使います。D1 schema はSQLiteと同じ前提で、`tools/export_d1_sql.py` が既存SQLiteからD1投入用SQLを生成します。

```text
vocaloid_titles.sqlite3
  -> tools/export_d1_sql.py
  -> D1 SQL
  -> local D1 / staging D1 / production D1
```

DB内容を編集する場合は、D1を直接手作業で直すのではなく、SQLite DBを作り直してからD1へ投入します。

この方針により、ローカルで検証済みのSQLiteをstaging / productionへ同じ形で配布できます。D1だけを手作業で直すと、次回投入時に差分が消え、ローカル検証結果ともずれます。

責務境界:

| 対象 | 書くもの | 読むもの | 役割 |
| --- | --- | --- | --- |
| SQLite `vocaloid_titles.sqlite3` | `build_db`, `refresh_video_metadata` | CLI検索、検査CLI、D1 export | 手元で検証するsource of truth |
| local D1 | `tools/export_d1_sql.py` の出力をWranglerで投入 | local Worker dev | ブラウザ確認用のローカル配布先 |
| staging D1 | `tools/update_d1.sh --env staging` | staging Worker | production前の確認先 |
| production D1 | `tools/update_d1.sh --env production` | production Worker | 公開APIの読み取り元 |

`tools/update_d1.sh` は既存SQLiteを読むだけで、Wiki取得やSQLite再構築は行いません。SQLiteを更新するか、D1へ投入するかは別の操作として扱います。

データフロー:

```text
songs
  -> song_details
  -> song_credit_people
  -> search / stats / song-detail API
```

`song_credit_people` は `song_details.payload_json` から作る検索用の派生テーブルです。リクエスト時にJSONを走査しないため、作曲者検索の性能と実装を安定させます。

## Schema Version

現在の DB schema version は `7` です。`metadata.schema_version` に保存し、`database_is_ready()` は次の metadata が揃い、`songs` が空でないこと、アプリ側の schema version と一致すること、曲詳細件数が曲数と一致することを確認します。

- `schema_version`
- `fetched_at`
- `song_count`
- `title_length_rule`

schema versionを上げる条件:

- table、column、index、metadataの意味を変える
- Worker APIが期待するDB構造を変える
- D1投入済みの古いDBを新しいWorkerが読めなくなる

schema versionを上げない条件:

- ドキュメントだけの変更
- UI表示だけの変更
- 抽出ヒューリスティックの改善で、保存JSON schemaが変わらない
- 既存columnの値をより正確に埋め直すだけの変更

schema versionを上げる場合に更新するもの:

| 対象 | 更新内容 |
| --- | --- |
| `vocaloid_title_search/database.py` | `DATABASE_SCHEMA_VERSION`、schema作成SQL、metadata保存 |
| `cloudflare/worker/src/index.ts` | Workerが期待する schema version と readiness判定 |
| `tools/export_d1_sql.py` | D1へ出すtable / index が変わる場合のexport対象 |
| Python tests | schema、検索、DB品質検査の期待値 |
| Worker tests | `/health`, `/api/search`, `/api/stats` などのfixture metadata |
| [web-api.md](web-api.md) | API responseやreadiness条件が変わる場合 |
| [cli-reference.md](cli-reference.md) | DB構築・検査CLIの挙動が変わる場合 |
| [operations.md](operations.md) | D1投入前後の確認手順が変わる場合 |

schema変更後は、`tools/check_all.sh` と `python -m vocaloid_title_search.cli.validate_db` を実行します。

## songs

曲一覧検索の主テーブルです。1行は Wiki タグページ上の1エントリに対応します。

Writer / reader:

| 種類 | 内容 |
| --- | --- |
| Writer | `build_db` |
| Reader | CLI検索、Worker `/api/search`, `/api/stats`, `/api/song-detail` の親参照 |

| Column | 内容 |
| --- | --- |
| `raw_title` | Wiki タグページ上の元タイトル。主キー |
| `song_url` | 各曲の Wiki ページ URL。曲詳細参照キー |
| `title` | `/` より前の曲名 |
| `artist` | 最初の `/` の後ろの作曲者名 |
| `artist_note` | 2個目以降の `/` の後ろの補足 |
| `title_length` | 文字数計算済みの曲名長 |
| `sort_order` | 代表取得元上の取得順 |
| `popularity_score` | 根拠タグから計算した人気度スコア |
| `popularity_label` | 採用された根拠タグ |
| `popularity_order` | 採用された根拠タグページ内の取得順 |
| `source_url` | DB作成時の代表取得元 URL |
| `fetched_at` | DB作成時刻。UTC の ISO 8601 文字列 |

Indexes:

- `idx_songs_title_length`: 文字数フィルターと文字数昇順/降順ソートを安定させる
- `idx_songs_popularity`: 人気度順ソートと、人気度順のページングを安定させる
- `idx_songs_url_unique`: `song_url` の一意制約。`song_details.url` の親キーとして使う
- `idx_songs_popularity_label`: 根拠タグフィルターで対象曲を絞り込む
- `idx_song_details_published_year`: 公開年フィルター、公開年ソート、`songs` JOIN で使う
- `idx_song_credit_people_role_name`: 作曲者フィルターで正規化済み作曲者名を検索する

## song_details

曲ページ詳細の JSON 保存テーブルです。`url` は `songs.song_url` を参照する外部キーです。

Writer / reader:

| 種類 | 内容 |
| --- | --- |
| Writer | `build_db`, `refresh_video_metadata` |
| Reader | Worker `/api/song-detail`, `/api/search` の公開年・作曲者表示補助, `/api/stats` |

| Column | 内容 |
| --- | --- |
| `url` | 曲ページ URL。主キー、`songs.song_url` への外部キー |
| `payload_json` | `/api/song-detail` が返す構造化詳細 JSON |
| `published_year` | 曲詳細ページに付いた年タグから推定した公開年。未取得または未分類の場合は `NULL` |
| `fetched_at` | 曲詳細取得時刻 |
| `source_fetched_at` | 元データ側の取得時刻補助。未使用時は空文字 |
| `schema_version` | 曲詳細のスキーマバージョン |

## song_credit_people

曲詳細の `credits` から作る検索用の派生テーブルです。公開APIは作曲者フィルター時にこのテーブルを参照し、リクエスト時に `song_details.payload_json` をJSON検索しません。

Writer / reader:

| 種類 | 内容 |
| --- | --- |
| Writer | `build_db`, `refresh_video_metadata` 実行後の派生テーブル再構築 |
| Reader | Worker `/api/search` の作曲者フィルターと `artist` 表示 |

| Column | 内容 |
| --- | --- |
| `song_url` | 曲ページ URL。`songs.song_url` への外部キー |
| `role` | クレジット種別。現在の検索対象は `composer` |
| `name` | 表示用の元表記 |
| `normalized_name` | NFKC + casefold した検索用表記 |

作曲者フィルターは、`credits.composer` が抽出済みの曲だけを対象にします。
検索APIの `artist` 表示もこのテーブルの `role = 'composer'` を使います。`songs.artist` はタグページの `/作曲者` 表記を保持しますが、検索APIの表示用作曲者としては使いません。

例:

| 元データ | 用途 |
| --- | --- |
| `songs.artist` | Wikiタグページ上の `/作曲者` 表記を保持する |
| `song_details.payload_json.credits.composer` | 曲ページ詳細から抽出した作曲者 |
| `song_credit_people` | 作曲者検索とAPIの `artist` 表示に使う |

## metadata

DB全体の補助情報です。

Writer / reader:

| 種類 | 内容 |
| --- | --- |
| Writer | `build_db`, `refresh_video_metadata` |
| Reader | `validate_db`, Worker `/health`, `/api/metadata` |

| Key | 内容 |
| --- | --- |
| `schema_version` | DB schema version |
| `fetched_at` | DB作成時刻 |
| `source_url` | 代表取得元 URL |
| `popularity_source_tags` | 人気度計算に使った根拠タグ一覧 |
| `publication_year_source` | 公開年推定に使った情報源 |
| `title_length_rule` | タイトル文字数計算ルール |
| `song_count` | DB に登録した曲数 |
| `detail_schema_version` | 曲詳細のスキーマバージョン |
| `detail_count` | `song_details` の現在行数 |

## Counting Rule

タイトル文字数は `vocaloid_title_search.models.count_title_chars()` で計算します。

- カウント前に Unicode NFC 正規化を行う
- `regex` の `\X` で grapheme cluster に分割し、見た目の1文字に近い単位で数える
- 記号は1文字として数える
- 半角スペース、全角スペース、タブなど `str.isspace()` が真になる文字は数えない
- ゼロ幅スペース、ゼロ幅非接合子、単語結合子、ゼロ幅ノーブレークスペース、点字空白 U+2800 だけでできた cluster は数えない
- 作曲者名と補足は文字数計算に含めない

例:

| 入力 | 結果 | 理由 |
| --- | ---: | --- |
| `メルト` | 3 | 3つのgrapheme cluster |
| `このツンデレ！` | 7 | 記号 `！` も数える |
| `A B` | 2 | 空白は数えない |
| `ネ⠀土` | 2 | U+2800 は空白風文字として数えない |

## Title / Artist Split Rule

`/` がない場合:

```text
メルト
```

```text
title: メルト
artist:
artist_note:
```

`/` が1つある場合:

```text
Q/椎名もた
```

```text
title: Q
artist: 椎名もた
artist_note:
```

`/` が2つ以上ある場合は、最初の `/` でタイトル、次の `/` で補足を分けます。

```text
ドラマツルギー/Eve/2016～
```

```text
title: ドラマツルギー
artist: Eve
artist_note: 2016～
```

## Popularity Sort

人気度は初音ミク Wiki のタグをもとに近似しています。高い順は次の通りです。

1. `YouTube1億再生達成曲`
2. `テンミリオン達成曲`
3. `YouTubeテンミリオン達成曲`
4. `ミリオン達成曲`
5. `YouTubeミリオン達成曲`
6. `殿堂入り`

同じ人気度内ではタグページ上の取得順で並びます。同じ曲が複数の根拠タグを持つ場合、DBには最も高いスコアのタグを `popularity_label` として保存します。

例:

| 曲が持つ根拠タグ | 保存する `popularity_label` |
| --- | --- |
| `殿堂入り`, `ミリオン達成曲` | `ミリオン達成曲` |
| `YouTubeミリオン達成曲`, `テンミリオン達成曲` | `テンミリオン達成曲` |
| `YouTube1億再生達成曲`, `殿堂入り` | `YouTube1億再生達成曲` |

## Publication Year

公開年は初音ミク Wiki の曲詳細ページに付いている `YYYY年` タグから取得します。DB構築時に曲ページHTMLを解析し、タグリンクの表示文字列が `YYYY年` で、リンク先が `/hmiku/tag/` を指すものを公開年候補にします。

同じ曲に複数の年タグがある場合は、最も古い年を `published_year` に保存します。

`YYYY年` タグページ全体の巡回機能はありません。殿堂入り・人気タグ対象外の曲まで大量に取得してしまうためです。

公開年が未取得の曲は `NULL` とし、公開年フィルターでは一致しません。公開年昇順・降順ソートでは `NULL` の曲を末尾に置き、同一年内では人気度順とタグページ取得順で安定化します。

例:

| 条件 | `published_year = NULL` の曲 |
| --- | --- |
| `year=2021` | 一致しない |
| `published_year_asc` | 年がある曲の後ろ |
| `published_year_desc` | 年がある曲の後ろ |

## Update Strategy

DB構築CLIは既存DBを直接 `DROP TABLE` せず、同じディレクトリに一時DBを構築します。曲一覧と曲詳細の全件取得が成功した後に `os.replace()` で差し替えるため、公開APIは更新中でも古い完全なDBか新しい完全なDBのどちらかを読みます。

曲詳細はDB構築時に全曲分取得します。詳細が揃っていないDBは `database_is_ready()` で未完成として扱います。

## Runtime Read-Only Access

検索、metadata、詳細のロード関数は `file:<path>?mode=ro` で SQLite を開きます。公開APIはリクエスト時にDBへ書き込まず、外部ネットワーク取得も行いません。

D1側も通常リクエストでは読み取り専用です。D1を変更する経路は、既存SQLiteから生成したSQLを `tools/update_d1.sh` で投入する手順に限定します。

## D1 Update Verification

D1投入前後で比較する代表値:

| 値 | 確認先 |
| --- | --- |
| `metadata.schema_version` | `/api/metadata`, D1 `metadata` |
| `metadata.song_count` | `/api/metadata`, `/api/stats.total_songs` |
| `metadata.detail_count` | `/api/metadata`, `/api/stats.detail_count` |
| `song_details` 件数 | `/api/stats.detail_count` |
| 作曲者あり件数 | `/api/stats.with_composer` |
| 公開年あり件数 | `/api/stats.with_published_year` |

件数が極端に少ない、`detail_count` と `song_count` が一致しない、または `/health` が `database_ready:false` の場合は、D1投入先、SQL生成、metadataを確認します。

ローカルSQLiteの投入前検査には次を使います。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.validate_db
```

この検査はDBを読み取るだけで、必須テーブル、metadata、曲数と詳細件数、詳細JSON、作曲者派生テーブル、公開年、動画メタデータ件数を確認します。

`validate_db` はDBの成立条件を確認する品質ゲートです。`report_detail_quality` は成立済みDBの中から、紹介文や動画などの抽出改善候補を探すレビュー用レポートです。`report_detail_quality` で欠損候補が出ても、検索DBとして不成立とは限りません。
