# Usage

ローカルでDBを作り、CLI検索、Worker API、Web UIを確認するための手順です。CLI の全オプションと既定値は [cli-reference.md](cli-reference.md) を参照してください。

この文書は手元の開発環境だけを扱います。staging / production へのdeployやD1投入は [operations.md](operations.md)、Cloudflare リソースの作成や変更は [infrastructure.md](infrastructure.md) を参照してください。

SQLite、local D1、staging D1、production D1 の関係は [concepts.md](concepts.md) にまとめています。

## Choose A Path

| 目的 | 必要なもの | local D1 |
| --- | --- | --- |
| CLI検索だけ試す | Python依存、SQLite DB | 不要 |
| DB品質を確認する | Python依存、SQLite DB | 不要 |
| Web UIをブラウザで確認する | Python依存、Node依存、SQLite DB、Worker dev、Vite dev server | 必要 |
| Worker APIを本番に近い形で確認する | Node依存、local D1、Worker dev | 必要 |
| staging / productionへdeployまたはD1投入する | 公開環境向け手順 | この文書では扱わない |

local D1は、ブラウザやWorker APIが本番と同じD1経路でデータを読むために使います。CLI検索だけなら、`vocaloid_titles.sqlite3` を直接読むためlocal D1は不要です。

## Setup

Python は `uv` で管理し、リポジトリ直下の `.python-version` を使用します。Node.js は `nodenv` で管理し、リポジトリ直下の `.node-version` を使用します。

```bash
uv python install
nodenv install -s "$(cat .node-version)"
nodenv rehash
corepack enable
```

```bash
uv sync --cache-dir .uv-cache
(cd frontend && yarn install)
(cd cloudflare/worker && yarn install)
```

確認:

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.search_titles --help
(cd frontend && yarn build)
(cd cloudflare/worker && yarn typecheck)
```

主な依存関係:

- `beautifulsoup4`, `lxml`: 曲ページ詳細の HTML 解析
- `regex`: タイトル文字数の grapheme cluster 分割
- `vue`, `vite`, `typescript`: Web UI
- `@lucide/vue`: Web UI のアイコン
- `wrangler`: Cloudflare Worker / Pages / D1 のローカル開発とデプロイ

Python 依存関係はDB構築、詳細抽出、CLI検索のために使います。本番の公開APIランタイムは Cloudflare Worker で、Pythonプロセスは起動しません。

## Build Local Data

曲一覧、人気度、曲詳細、公開年を含むDBを作成します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db
```

動画タイトルやニコニコの実サムネイルURLまで事前取得したい場合は、DB作成後に動画メタデータだけを更新します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.refresh_video_metadata
```

DB構築CLIは一時DBを構築してから原子的に差し替えます。曲詳細はDB構築中に全曲分取得し、詳細が揃っていないDBはAPIから未完成として扱われます。

Web API / Web UI の作曲者フィルターは、曲詳細の `credits.composer` を対象にします。Web UI では文字数と作曲者を独立した条件として扱い、文字数を空欄にすると作曲者だけで検索できます。

## Search CLI

検索CLIは作成済みDBだけを読みます。DBがない場合は `build_db` を先に実行します。

3文字タイトルを人気度順で出力します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.search_titles 3
```

詳細列を表示します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.search_titles 3 --show-count --show-artist --show-url --show-popularity
```

## Local Dev Server

開発時は Cloudflare Worker と Vite dev server を別々に起動します。Worker は D1 を読むため、初回起動前またはDB更新後に、既存SQLiteからローカルD1へデータを投入します。

最短判断:

| 状況 | 先にやること |
| --- | --- |
| 画面だけ見たいがDBもlocal D1も未準備 | `Build Local Data` → `First Run Or After DB Update` |
| 以前にlocal D1投入済みで、コードだけ触る | `Daily Startup` |
| SQLiteを作り直した | `First Run Or After DB Update` |
| 動画メタデータだけ更新した | `First Run Or After DB Update` |
| CSSやVueだけ変更した | D1再投入なしで `Daily Startup` |

なぜローカルD1を使うか:

- 本番と同じ Worker + D1 の実行経路で API を確認するため
- staging / production D1 を誤って書き換えないため
- フロントエンドから `/api/*` を呼んだとき、実データ入りのAPIとして動かすため

データの流れ:

```text
vocaloid_titles.sqlite3
  -> tools/export_d1_sql.py
  -> release/d1/local/vocaloid_titles.sql
  -> wrangler d1 execute --local
  -> Wrangler のローカルD1
```

この手順はローカルD1だけを書き換えます。通常DB `vocaloid_titles.sqlite3` と staging / production D1 は変更しません。

よく使うURL:

| 用途 | URL |
| --- | --- |
| Web UI | `http://127.0.0.1:5173/` |
| Worker API | `http://127.0.0.1:8000/` |
| Health | `http://127.0.0.1:8000/health` |
| 代表検索 | `http://127.0.0.1:8000/api/search?length=7&sort=popularity` |

手順は3パターンに分けます。

| 状況 | 必要な操作 |
| --- | --- |
| 初回セットアップ | 依存同期、DB構築、local D1投入、サーバー起動 |
| 日常起動 | サーバー起動だけ |
| DB更新後 | D1 SQL再生成、local D1再投入、サーバー再起動または再確認 |

### First Run Or After DB Update

初回起動時、または `build_db` / `refresh_video_metadata` で `vocaloid_titles.sqlite3` を更新した後は、local D1へデータを投入します。

1. D1投入用SQLを生成します。

```bash
uv run --cache-dir .uv-cache python tools/export_d1_sql.py \
  --db-path vocaloid_titles.sqlite3 \
  --output release/d1/local/vocaloid_titles.sql
```

2. 生成したSQLをWranglerのローカルD1へ投入します。

```bash
(cd cloudflare/worker && \
  ./node_modules/.bin/wrangler d1 execute vocaloid-title-search-dev \
    --local \
    --file ../../release/d1/local/vocaloid_titles.sql)
```

SQLiteだけ更新した場合は、Web UIを見る前に必ずこのlocal D1投入をやり直します。`vocaloid_titles.sqlite3` が新しくても、local D1が古いままだとWeb UIには古いデータが出ます。

### Daily Startup

SQLite DBとlocal D1を更新していない場合は、D1投入をやり直さずにサーバーだけ起動できます。

1. Worker API を起動します。

```bash
(cd cloudflare/worker && yarn dev)
```

Worker API: `http://127.0.0.1:8000/`

2. 別のターミナルで Vite dev server を起動します。

```bash
(cd frontend && yarn dev)
```

Vite dev server: `http://127.0.0.1:5173/`

`/api/*` は Vite の proxy で `http://127.0.0.1:8000` のWorkerへ転送されます。本番ではCloudflare Pagesが `frontend/dist` を静的配信し、`/api/*` と `/health` をWorker routeへ転送します。

起動確認:

```bash
curl http://127.0.0.1:8000/health
```

`{"ok":true,"database_ready":true}` が返ればWorker API とローカルD1の準備は完了です。

### After SQLite Update

`build_db` または `refresh_video_metadata` を実行した後:

1. `tools/export_d1_sql.py` でD1 SQLを再生成する
2. `wrangler d1 execute --local` でlocal D1へ投入する
3. `/health` を確認する
4. Web UIを再読み込みする

動画タイトルやサムネイルだけを更新した場合も、SQLite内の詳細JSONが変わるためlocal D1再投入が必要です。

### When Local D1 Needs Reload

local D1へ再投入が必要なタイミング:

- `build_db` で `vocaloid_titles.sqlite3` を作り直した
- `refresh_video_metadata` で動画タイトルやサムネイルを更新した
- `tools/export_d1_sql.py` やD1 schemaに関わるコードを変更した
- `/health` が `database_ready:false` を返す

再投入が不要なケース:

- フロントエンドのCSSやVueコンポーネントだけを変更した
- Worker APIの表示ロジックだけを変更し、DB schemaやデータを変えていない
- 既にlocal D1へ同じSQLiteの内容を投入済みで、サーバーだけ再起動したい

`127.0.0.1:8000` が使用中でWorkerが起動しない場合は、既存の `wrangler` / `workerd` プロセスが残っていないか確認します。

```bash
ps -eo pid,ppid,stat,command | grep -E 'wrangler|workerd|yarn dev' | grep -v grep
```

意図せず残っている開発用プロセスだけを停止してから、Worker API を起動し直します。通常DB `vocaloid_titles.sqlite3` の再構築は不要です。

local D1を初期化し直したい場合は、Wranglerのローカル状態を削除してから、`First Run Or After DB Update` の手順で再投入します。削除対象はWranglerのローカルD1だけに限定し、`vocaloid_titles.sqlite3`、staging D1、production D1は変更しません。

### Stop Servers

通常は、起動したターミナルで `Ctrl-C` を押します。

プロセスが残っている場合だけ確認します。

```bash
ps -eo pid,ppid,stat,command | grep -E 'wrangler|workerd|yarn dev' | grep -v grep
```

意図せず残った開発用プロセスだけを停止します。DB再構築やD1再投入は、プロセス停止だけなら不要です。

### Missing Video Metadata

動画タイトルやサムネイルがWeb UIに出ない場合は、まずSQLiteとlocal D1のどちらが古いかを分けます。

```bash
python3 - <<'PY'
import sqlite3
con = sqlite3.connect("vocaloid_titles.sqlite3")
print(con.execute("""
select count(*)
from song_details
where payload_json like '%"thumbnail_url"%'
  and payload_json not like '%YouTube %'
  and payload_json not like '%ニコニコ動画 sm%'
""").fetchone()[0])
PY
```

`0` に近い場合は、動画メタデータ更新が未実行です。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.refresh_video_metadata --request-interval 0
```

SQLiteに動画メタデータがあるのにWeb UIへ出ない場合は、local D1が古い状態です。上の `First Run Or After DB Update` の手順で、D1投入用SQLを再生成してlocal D1へ投入します。

## Web UI

Web UI は検索ビューと統計ビューを持ちます。検索ビューは条件なし検索、ページング、表示項目切替、曲詳細表示に対応します。統計ビューは文字数、公開年、根拠タグ、作曲者の分布を表示し、各項目から検索へ移動できます。画面仕様の詳細は [frontend-ui.md](frontend-ui.md) を参照してください。

## Tests

```bash
tools/check_all.sh
```
