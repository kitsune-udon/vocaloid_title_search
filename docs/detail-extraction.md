# Detail Extraction

Web UI の詳細アコーディオンは `/api/song-detail?url=...` から取得します。公開運用時の Worker API は外部 Wiki を取得せず、D1 の `song_details.payload_json` に保存済みの構造化 JSON を返します。

曲ページ HTML の取得と BeautifulSoup 解析は、DB構築ジョブの `python -m vocaloid_title_search.cli.build_db` で曲一覧取得後に全曲分実行します。DB構築ジョブは同一ホストへのリクエスト間隔、最大並列数、HTTP 429/502/503/504 のバックオフをCLIオプションで制御します。

構築時間短縮のため、YouTube oEmbed とニコニコ getthumbinfo はDB構築中には呼びません。動画メタデータが必要な場合は、DB構築後に `python -m vocaloid_title_search.cli.refresh_video_metadata` を実行します。この処理はDB内の `videos` / `related_videos` からユニークな動画IDを集め、曲詳細ページを再取得せずに動画タイトルとサムネイルURLだけを書き戻します。

実装は `vocaloid_title_search/detail.py` に集約しています。曲ページ HTML を BeautifulSoup で解析し、作詞・作曲・編曲・唄・動画などの情報を構造化します。

安全のため、詳細 API は `https://w.atwiki.jp/hmiku/pages/<数字>.html` のみ受け付けます。DB内に詳細がない場合は `404` を返します。

## Responsibility Boundaries

詳細情報に関する処理は、意図的に3段階へ分けています。

| 段階 | コマンドまたはAPI | 外部アクセス | 書き込み先 | 責務 |
| --- | --- | --- | --- | --- |
| DB構築 | `build_db` | 初音ミク Wiki | ローカル SQLite | 曲一覧、曲詳細HTML、基本情報、紹介文、動画ID、公開年を取得 |
| 動画メタデータ更新 | `refresh_video_metadata` | YouTube / ニコニコ | ローカル SQLite | 既存DB内の動画IDにタイトルとサムネイルURLを補完 |
| 表示API | `/api/song-detail` | なし | なし | D1 に投入済みの詳細JSONを返す |

D1投入ツールは、既存SQLiteをD1用SQLへ変換して投入するだけです。Wikiや動画サービスへアクセスしません。

## Response Shape

```json
{
  "page_title": "メルト",
  "reading": "",
  "published_year": 2007,
  "credits": {
    "lyricist": ["ryo"],
    "composer": ["ryo"],
    "arranger": ["ryo"],
    "vocalist": ["初音ミク"]
  },
  "introduction": ["誰もがご存知有名なミク曲。"],
  "videos": {
    "niconico": [
      {
        "id": "sm1715919",
        "url": "https://www.nicovideo.jp/watch/sm1715919",
        "title": "初音ミク　が　オリジナル曲を歌ってくれたよ「メルト」",
        "thumbnail_url": "https://nicovideo.cdn.nimg.jp/thumbnails/1715919/1715919.L",
        "thumbnail_urls": [
          "https://nicovideo.cdn.nimg.jp/thumbnails/1715919/1715919.L",
          "https://nicovideo.cdn.nimg.jp/thumbnails/1715919/1715919.M",
          "https://nicovideo.cdn.nimg.jp/thumbnails/1715919/1715919"
        ]
      }
    ],
    "youtube": [
      {
        "id": "XRymkHlMB-k",
        "url": "https://www.youtube.com/watch?v=XRymkHlMB-k",
        "title": "ryo(supercell) feat.初音ミク メルト",
        "thumbnail_url": "https://img.youtube.com/vi/XRymkHlMB-k/mqdefault.jpg"
      }
    ]
  },
  "related_videos": {
    "niconico": [
      {
        "id": "sm2183246",
        "url": "https://www.nicovideo.jp/watch/sm2183246",
        "title": "メルト 3M MIX",
        "thumbnail_url": "https://nicovideo.cdn.nimg.jp/thumbnails/2183246/2183246"
      }
    ],
    "youtube": []
  },
  "source_url": "https://w.atwiki.jp/hmiku/pages/82.html"
}
```

## Extracted Fields

- `page_title`: HTML の `<title>` から Wiki 名を除いたページ名
- `reading`: `曲紹介` 内の `曲名：『...』（...）` から抽出した読み
- `published_year`: 曲詳細ページ内の `YYYY年` タグから推定した公開年
- `credits`: `作詞`, `作曲`, `編曲`, `唄`, `絵`, `動画`, `調声`
- `introduction`: `曲紹介` セクション内の本文
- `videos`: `関連動画` 見出しより前にある埋め込み動画
- `related_videos`: 本文中の動画リンクと `関連動画` セクション内の動画

必須・任意の扱い:

| Field | 必須 | 欠損時の扱い |
| --- | --- | --- |
| `page_title` | はい | 空文字なら表示上は曲名側を使う |
| `source_url` | はい | 詳細APIのキーなので欠損させない |
| `credits` | はい | 空objectを許容 |
| `introduction` | はい | 空配列を許容 |
| `videos` | はい | `niconico`, `youtube` の空配列を許容 |
| `related_videos` | はい | `niconico`, `youtube` の空配列を許容 |
| `reading` | 任意 | 表示しない |
| `published_year` | 任意 | `null` として扱う |

動画メタデータ未取得時:

- YouTubeのタイトルは `YouTube <id>` のようなフォールバック値になる
- ニコニコのタイトルは `ニコニコ動画 <id>` のようなフォールバック値になる
- サムネイルURLはIDから作れる候補を入れる
- `refresh_video_metadata` 実行後に、取得できたタイトルとサムネイルURLへ置き換わる

詳細取得に失敗した曲がある場合、完成DBとして扱いません。`song_details` の件数が `songs` の件数と一致しないDBは `/health` で `database_ready:false` になります。

抽出品質をレビューしたい場合は、保存済みDBに対して次を実行します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.report_detail_quality
```

このコマンドは曲ページを再取得せず、`song_details.payload_json` だけを読みます。基本情報、作曲者、曲紹介、通常動画、公開年、JSON破損の欠損候補を曲URL付きで一覧化します。作曲者にSNSや公式サイト由来の文字列が混ざった候補、公開年が範囲外に見える候補、保存カラムと詳細JSONの公開年不一致もレビュー対象に含めます。

## Investigation Flow

Web UIの詳細表示がおかしい場合は、表示、API、保存済みJSON、抽出ロジックを分けて確認します。

1. Web UIで該当カードの詳細を開き、どの項目が不自然か確認する
2. `/api/song-detail?url=...` のJSONを見て、API時点で不自然か確認する
3. SQLiteの `song_details.payload_json` に同じ値が入っているか確認する
4. `report_detail_quality` で同種の候補が複数あるか確認する
5. [detail-extraction-algorithm.md](detail-extraction-algorithm.md) の Common Failure Patterns から近い症状を探す
6. 最小HTMLで `tests/test_detail_extraction.py` に回帰テストを追加する

症状別の入口:

| 症状 | 最初に見る場所 |
| --- | --- |
| 作曲者にSNS名や公式サイト名が混ざる | リンク注記除去、`song_credit_people` |
| 唄・作詞・動画などに別項目が混ざる | Credits State Machine |
| 通常動画と関連動画が逆に見える | Videos, Video State Machine |
| 読みがRemix名や括弧内補足になる | Reading |
| 公開年が空または不自然 | Published Year |
| サムネイルや動画タイトルだけ古い | `refresh_video_metadata` とlocal D1再投入 |

表示だけがおかしい場合は `frontend-ui.md` とフロント実装を見ます。API JSONの時点でおかしい場合は、詳細抽出か保存済みDBの問題として扱います。

## Extraction Flow

詳細情報は以下の順で抽出します。

1. DB構築CLIが DB 内の曲 URL を列挙し、全曲のページを `fetch_song_detail()` で取得します。
2. `fetch_song_detail(url)` が曲ページ HTML を取得します。
3. `parse_song_detail(page_html, source_url)` が HTML 文字列を受け取り、各抽出関数に分配します。
4. `clean_soup(page_html)` が `script`, `style`, `noscript`, `iframe` を除去した BeautifulSoup オブジェクトを作ります。
5. `split_video_sections(page_html)` が `関連動画` 見出しより前と、関連動画セクションを分離します。この処理では動画 URL を残すため `iframe` は除去しません。
6. `remove_excluded_video_sections()` が `英語版` など、本家曲の通常動画に混ぜないセクションを通常動画対象から外します。
7. `extract_page_title`, `extract_reading`, `extract_published_year`, `extract_credits`, `extract_introduction`, `extract_videos` の結果を `SongDetail` にまとめます。
8. `save_song_detail_entry()` が表示用の完成済み JSON と `published_year` を `song_details` に保存します。
9. 動画タイトルやサムネイルを補完する場合は、動画メタデータ更新CLIが `song_details.payload_json` 内の動画IDを走査し、動画タイトルとサムネイルURLを更新します。

## Algorithm Details

抽出アルゴリズムの細部は [detail-extraction-algorithm.md](detail-extraction-algorithm.md) に分離しています。

この概要文書では、Web UI と API が扱うデータ構造、DB保存、レスポンス形状だけを説明します。実装上のヒューリスティック、基本情報の状態機械、リンク注記除去、動画分類の詳細はアルゴリズム文書を参照してください。
