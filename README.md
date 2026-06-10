# Vocaloid Title Search

有名ボカロ曲をタイトル文字数、作曲者、公開年、根拠タグで検索するための開発・個人運用向けツールです。初音ミク Wiki から取得したデータをSQLiteに保存し、CLI検索とWeb UIで参照します。

本番ランタイムは Cloudflare Pages + Worker + D1 です。Python は本番で常駐させず、Wiki取得、HTML解析、SQLite DB構築、D1投入用SQL生成のための build-time toolchain として使います。

主な責務:

- `python -m vocaloid_title_search.cli.build_db`: 曲一覧、人気度、曲詳細、公開年を取得してSQLite DBを作る
- `python -m vocaloid_title_search.cli.refresh_video_metadata`: 既存DB内の動画IDから動画タイトルとサムネイルURLを補完する
- `python -m vocaloid_title_search.cli.validate_db`: SQLite DBの品質と整合性を検査する
- `python -m vocaloid_title_search.cli.report_detail_quality`: 曲詳細JSONの欠損候補を一覧化する
- `python -m vocaloid_title_search.cli.search_titles`: 作成済みDBをCLIで検索する
- Cloudflare Worker + D1: 公開APIを読み取り専用で提供する
- Vue + Vite: Web UIを提供する

## What It Does

- タイトル文字数、作曲者、公開年、根拠タグで有名ボカロ曲を検索
- 人気度順、文字数順、公開年順で並び替え
- 50 / 100 / 200 件のページングで検索結果を閲覧
- DB に保存した曲ページ詳細、基本情報、動画、関連動画を Web UI で表示
- 文字数、公開年、根拠タグ、作曲者の統計ビュー
- 記号を 1 文字として数え、空白文字と空白風の U+2800 はカウント対象外にする文字数計算
- `タイトル/作曲者/補足` 形式を `title`, `artist`, `artist_note` に分離

## Quick Start

Python version は `.python-version`、Node.js version は `.node-version` で管理します。初回セットアップの詳細は [docs/usage.md](docs/usage.md#setup) を参照してください。

目的別の最短ルート:

| やりたいこと | 読む場所 |
| --- | --- |
| 開発環境を用意する | [docs/usage.md](docs/usage.md) |
| CLI検索だけ試す | Minimal CLI Check |
| Web UIをローカルで見る | Web UI Check |
| SQLite DBを更新する | [docs/usage.md](docs/usage.md), [docs/cli-reference.md](docs/cli-reference.md) |
| stagingで確認する | [docs/operations.md](docs/operations.md#application-deploy), [docs/operations.md](docs/operations.md#database-update) |
| 公開環境へdeployまたはD1投入する | [docs/operations.md](docs/operations.md) |
| Cloudflare構成を変更する | [docs/infrastructure.md](docs/infrastructure.md) |

開発だけなら、Cloudflare の実アカウントや production 設定は不要です。公開環境へdeployまたはD1投入する場合だけ、Terraform state、Wrangler認証、staging / production D1 を確認します。

### Minimal CLI Check

依存関係を同期し、DBを作ってCLI検索だけ確認します。

```bash
uv sync --cache-dir .uv-cache
```

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db
```

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.search_titles 3
```

DB更新後やD1投入前の品質確認:

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.validate_db
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.report_detail_quality --limit 20
```

### Web UI Check

Web UIまで確認する場合は、Node依存を同期し、local D1へ既存SQLiteの内容を投入します。この操作は staging / production D1 を変更しません。

```bash
(cd frontend && yarn install)
(cd cloudflare/worker && yarn install)
```

```bash
uv run --cache-dir .uv-cache python tools/export_d1_sql.py \
  --db-path vocaloid_titles.sqlite3 \
  --output release/d1/local/vocaloid_titles.sql
(cd cloudflare/worker && \
  ./node_modules/.bin/wrangler d1 execute vocaloid-title-search-dev \
    --local \
    --file ../../release/d1/local/vocaloid_titles.sql)
```

```bash
(cd cloudflare/worker && yarn dev)
```

別のターミナル:

```bash
(cd frontend && yarn dev)
```

Web UI: `http://127.0.0.1:5173/`

動画タイトルやニコニコの実サムネイルURLまで事前取得する場合は、`refresh_video_metadata` を実行してからlocal D1へ再投入します。日常起動、再投入が必要なタイミング、起動確認、ポート競合時の確認方法は [docs/usage.md](docs/usage.md#local-dev-server) を参照してください。

## Documentation

このREADMEは、開発者と個人運用の保守者向けの入口です。利用者向けの宣伝ページではなく、ローカル開発、DB更新、Cloudflare運用へ進むための導線を優先します。

ドキュメント全体の入口は [docs/README.md](docs/README.md) です。

| 目的 | Document |
| --- | --- |
| SQLite / D1 / deploy の関係を把握する | [docs/concepts.md](docs/concepts.md) |
| ローカルで動かす | [docs/usage.md](docs/usage.md) |
| CLIオプションを確認する | [docs/cli-reference.md](docs/cli-reference.md) |
| 構造とデータモデルを把握する | [docs/project-structure.md](docs/project-structure.md), [docs/data-model.md](docs/data-model.md) |
| 詳細抽出を理解する | [docs/detail-extraction.md](docs/detail-extraction.md), [docs/detail-extraction-algorithm.md](docs/detail-extraction-algorithm.md) |
| Web UI / API を確認する | [docs/frontend-ui.md](docs/frontend-ui.md), [docs/web-api.md](docs/web-api.md) |
| Cloudflare運用を行う | [docs/cloudflare-serverless.md](docs/cloudflare-serverless.md), [docs/infrastructure.md](docs/infrastructure.md), [docs/operations.md](docs/operations.md) |
| 秘密情報・実ドメインの混入を防ぐ | [docs/repository-privacy.md](docs/repository-privacy.md) |
| ドキュメントを書く・直す | [docs/documentation-quality.md](docs/documentation-quality.md) |

ドキュメントをブラウザで確認する場合:

```bash
(cd docs-site && yarn install)
(cd docs-site && yarn dev)
```

Docs UI: `http://127.0.0.1:5173/`

VitePress のプレビューは、サイドバー、ページ間リンク、見出しの見え方を確認したいときに使います。短い確認だけならMarkdownを直接読んで構いません。

## Checks

通常開発の基本チェック:

```bash
tools/check_all.sh
```

UI変更時やrelease前のブラウザE2E:

```bash
(cd frontend && yarn test:e2e)
```

ドキュメントだけを確認する場合:

```bash
tools/check_docs.sh
```

`check_all.sh` は軽量な単体・静的検査、`check_docs.sh` はドキュメント専用のリンク・秘匿情報・構造検査、`yarn test:e2e` はブラウザ上の検索、詳細、ページング、統計遷移のsmoke確認です。初回だけPlaywrightのChromium導入が必要です。詳細は [docs/testing.md](docs/testing.md#frontend-e2e) を参照してください。

## Main Files

| File | Role |
| --- | --- |
| `vocaloid_title_search/cli/build_db.py` | DB構築CLI |
| `vocaloid_title_search/cli/refresh_video_metadata.py` | 動画メタデータ更新CLI |
| `vocaloid_title_search/cli/search_titles.py` | 検索CLI |
| `vocaloid_title_search/` | DB、Wiki取得、詳細抽出、CLI本体のPython package |
| `frontend/` | Vue + TypeScript + Vite の Web UI |
| `docs-site/` | VitePress によるローカルドキュメントプレビュー |
| `cloudflare/` | Pages / Worker / D1 用のWorker API |
| `infra/cloudflare/` | Cloudflare Pages / DNS / D1 / Worker route の Terraform |
| `AGENTS.md` | Codexなどのエージェント向けリポジトリ編集ルール |
| `tools/check_sensitive_values.py` | 追跡ファイル内の実値・秘密情報らしき値を検出する補助スクリプト |
| `tools/cloudflare_iac.sh` | `infra/cloudflare` の Terraform wrapper |
| `tools/generate_wrangler_toml.py` | Terraform state から ignore 対象の `cloudflare/worker/wrangler.toml` を生成 |
| `tools/deploy_cloudflare.sh` | `staging` / `production` へ Pages と Worker をデプロイするスクリプト |
| `tools/update_d1.sh` | 既存SQLite DBをD1へ投入し、任意でAPI smoke testを実行する更新スクリプト |
| `tools/check_all.sh` | Python/Worker/frontend/機密値をまとめて検証するスクリプト |
| `tools/lib.sh` | shell tools の共通処理 |

## Operational Notes

- 公開APIは通常リクエストでDBへ書き込みません。D1更新は `tools/update_d1.sh` からの投入に限定します。
- 本番ランタイムは Cloudflare Pages + Worker + D1 です。Python は本番環境で常駐させません。
- 検索CLIはDB専用です。DBなしでWikiへ直接取りに行く機能は削除しました。
- Wikiへのネットワーク取得はDB構築に限定します。
- DB構築CLIは既定で同一ホストへのリクエスト間隔を0.2秒空け、HTTP 429/502/503/504 はバックオフして再試行します。
- 動画メタデータ取得はDB構築後に `refresh_video_metadata` CLIで実行します。DB構築中には取得しません。
- Cloudflare の永続リソースは `infra/cloudflare` の Terraform で管理します。
- Cloudflare D1 を更新する場合は `tools/update_d1.sh --env staging|production` を使います。Terraform state があればD1名と公開URLを自動解決し、更新後に公開APIの smoke test を実行します。smoke test は公開経路と主要APIの短い疎通確認です。
