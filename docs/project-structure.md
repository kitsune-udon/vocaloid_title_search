# Project Structure

このプロジェクトは、DB構築用Python package、Cloudflare Worker API、Vue frontend、運用補助スクリプトを分けて配置します。Python package は本番ランタイムではなく、ローカルまたはCIでDBを生成するための build-time tooling です。

```text
vocaloid_title_search/
  models.py          データモデル、タイトル分離、文字数計算
  http.py            HTTP取得、rate limit、429/502/503/504 backoff
  wiki.py            初音ミク Wiki タグページ取得
  detail.py          曲ページ詳細の構造化抽出
  database.py        SQLite schema、検索、詳細保存/読込
  video_metadata.py  動画メタデータ取得と詳細JSON更新
  cli/
    common.py        CLI共通オプション
    build_db.py      DB構築CLI本体
    refresh_video_metadata.py
                     動画メタデータ更新CLI本体
    search_titles.py
                     検索CLI本体

frontend/
  src/               Vue + TypeScript UI
  tests/e2e/         Playwright E2E smoke tests
  playwright.config.ts
                     Playwright設定

shared/
  api-types.ts       frontend と Worker が共有するAPI型

cloudflare/
  worker/            Cloudflare Worker API

infra/
  cloudflare/        Terraform for Pages, DNS, D1, Worker routes

docs/                設計・運用ドキュメント
docs-site/           VitePress docs preview
tests/               Python unit tests
tools/               repository checks, D1 SQL generation, smoke test, maintenance helpers
  lib.sh             shell tools shared helpers
.python-version      uv が使う Python version
.node-version        nodenv が使う Node.js version
AGENTS.md            coding agent rules
```

## CLI

CLI は package 内の module として実行します。トップレベルにはCLIファイルを置きません。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.refresh_video_metadata
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.search_titles 3
```

## Language Boundary

TypeScript は公開APIとWeb UIのランタイムを担当します。Python はWiki取得、HTML解析、SQLite DB構築、D1 SQL生成、検索CLIを担当します。

Python処理をTypeScriptへ全面移行する必要は現時点ではありません。将来移行する場合も、D1 SQL生成、動画メタデータ更新、DB構築オーケストレーション、詳細抽出の順に段階的に置き換えます。詳細抽出はBeautifulSoupと既存テストに依存するため、最後に検討します。

## Runtime Versions

Python version はリポジトリ直下の `.python-version`、Node.js version はリポジトリ直下の `.node-version` に集約します。`frontend/` と `cloudflare/worker/` は同じ Node.js version を使います。

サブディレクトリごとに `.node-version` を置かない理由は、frontend build、Worker test、Wrangler deploy が同じ Node.js toolchain を共有するためです。バージョンを上げる場合は root の `.node-version` を変更し、`tools/check_all.sh` で frontend と Worker の両方を確認します。

依存関係の責務:

| ファイル | 役割 |
| --- | --- |
| `.node-version` | 実行するNode.js version |
| `frontend/yarn.lock` | frontend依存の解決結果 |
| `cloudflare/worker/yarn.lock` | Worker / Wrangler依存の解決結果 |
| `docs-site/yarn.lock` | VitePress docs preview依存の解決結果 |
| `shared/api-types.ts` | frontendとWorkerが共有するAPI型 |
| `frontend/playwright.config.ts` | frontend E2E smoke の起動設定 |

API型を変更する場合は、`shared/api-types.ts`、Worker実装、frontendの利用箇所、Worker test、`docs/web-api.md` を合わせて確認します。

## Infrastructure Boundary

Cloudflare の永続リソースは `infra/cloudflare/` の Terraform で管理します。Worker script と Pages artifact はリリース成果物なので、Terraform ではなく `tools/deploy_cloudflare.sh` と Wrangler でデプロイします。

`cloudflare/worker/wrangler.toml.example` は追跡対象のテンプレートです。実値を入れる `cloudflare/worker/wrangler.toml` は ignore 対象で、D1 binding と CORS origin を置きます。この実設定は `tools/generate_wrangler_toml.py` で Terraform state から再生成できます。Worker routes、Pages custom domains、DNS records は Terraform 管理のため `wrangler.toml` には書きません。

```text
infra/cloudflare
  -> Pages project / DNS / D1 database / Worker routes

cloudflare/worker
  -> Worker script / D1 binding / API implementation

frontend
  -> Pages artifact
```

## Docs Site

`docs-site/` は、`docs/` のMarkdownをVitePressでブラウザ表示するための補助プロジェクトです。ドキュメントの正本は `docs/` に置き、`docs-site/` には設定、依存関係、preview用の生成物だけを置きます。

```text
docs-site/
  package.json       VitePress scripts and dependencies
  yarn.lock          docs preview dependency lockfile
  .vitepress/
    config.ts        srcDir, sidebar, local search, noindex metadata
```

使い分け:

| 確認したいこと | 方法 |
| --- | --- |
| 文章やコマンドの短い確認 | Markdownを直接読む |
| リンク、サイドバー、表の折り返し、見出し階層 | `(cd docs-site && yarn dev)` |
| release前のdocs build確認 | `(cd docs-site && yarn build)` |

`docs-site` は公開ランタイムではありません。検索流入抑制方針に合わせ、VitePress側にも `noindex,nofollow,noarchive` を設定します。

## Generated Files

以下は生成物またはローカル環境で、Git管理しません。

```text
.uv-cache/
.venv/
frontend/node_modules/
frontend/dist/
frontend/test-results/
frontend/playwright-report/
cloudflare/worker/node_modules/
cloudflare/worker/.wrangler/
docs-site/node_modules/
docs-site/.vitepress/cache/
docs-site/.vitepress/dist/
infra/cloudflare/.terraform/
release/
vocaloid_titles.sqlite3
```

`release/` はD1投入用SQLやbackupなどの生成物を置く場所です。再生成できるため追跡しません。削除する場合は、直近のrollbackに必要なbackupが不要であることを確認します。

代表的なignore対象:

| Path | 内容 |
| --- | --- |
| `.venv/`, `.uv-cache/` | Python環境とcache |
| `node_modules/` | Node.js依存 |
| `frontend/dist/` | Pagesへdeployするビルド成果物 |
| `frontend/test-results/`, `frontend/playwright-report/` | Playwright E2Eの実行結果 |
| `cloudflare/worker/wrangler.toml` | 実D1 IDやCORS originを含むローカル設定 |
| `release/` | D1 SQL、backup、deploy用生成物 |
| `vocaloid_titles.sqlite3` | 生成済みローカルSQLite |
