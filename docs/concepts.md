# Core Concepts

この文書は、他のドキュメントを読む前に知っておくと迷いにくい共通概念をまとめます。手順そのものは [usage.md](usage.md) と [operations.md](operations.md) を参照してください。

## Data Stores

| 名前 | 用途 | 書き換える操作 |
| --- | --- | --- |
| `vocaloid_titles.sqlite3` | 生成済み曲データの source of truth | `build_db`, `refresh_video_metadata` |
| local D1 | 手元の Worker API を本番に近い経路で動かすためのローカルDB | `wrangler d1 execute --local` |
| staging D1 | production投入前に公開API経由で確認するDB | `tools/update_d1.sh --env staging` |
| production D1 | 公開中の本番APIが読むDB | `tools/update_d1.sh --env production` |

通常の開発では、まずSQLiteを作ります。Web UIやWorker APIを本番に近い経路で確認する場合はlocal D1へ投入します。公開環境のDBを更新する場合だけ、staging D1、production D1の順に投入します。

```text
初音ミク Wiki
  -> build_db
  -> vocaloid_titles.sqlite3
  -> export_d1_sql.py
  -> D1 SQL
  -> local D1 / staging D1 / production D1
```

## Safety Levels

操作ごとの影響範囲を先に見ます。迷った場合は、staging / production に触れる操作を後回しにして、local D1 か dry-run で確認します。

| 操作 | 影響範囲 | 注意 |
| --- | --- | --- |
| `search_titles` | 読み取りのみ | SQLiteを変更しない |
| `export_d1_sql.py` | ローカルSQLファイル生成 | D1は変更しない |
| `wrangler d1 execute --local` | local D1 | staging / production D1は変更しない |
| `build_db` | ローカルSQLite | 完了時に `vocaloid_titles.sqlite3` を差し替える |
| `refresh_video_metadata` | ローカルSQLite | 既存詳細JSON内の動画情報を書き換える |
| `tools/update_d1.sh --env staging` | staging D1 | production D1は変更しない |
| `tools/update_d1.sh --env production` | production D1 | staging確認後に実行する |
| `tools/deploy_cloudflare.sh --env production` | production Pages / Worker | アプリケーションを本番へ公開する |
| `tools/cloudflare_iac.sh apply` | Cloudflare永続リソース | plan確認後に実行する |

## Change Operations

```text
deploy
  Pages / Worker のコードや静的ファイルを公開する

D1投入
  既存SQLiteから作った曲データをD1へ読み込ませる

Terraform apply
  DNS、custom domain、D1 database、Worker route などの器を変更する
```

| 操作 | 主な対象 | 代表コマンド |
| --- | --- | --- |
| deploy | Pages artifact / Worker script | `tools/deploy_cloudflare.sh --env staging` |
| D1投入 | staging D1 / production D1 のデータ | `tools/update_d1.sh --env staging` |
| Terraform apply | Cloudflare永続リソース | `tools/cloudflare_iac.sh apply` |

source of truth は「正本となるデータ」という意味です。このプロジェクトでは、生成済み曲データの正本はローカルSQLiteです。D1は公開APIが読む配布先です。

## Runtime Boundary

本番ランタイムは Cloudflare Pages + Worker + D1 です。Python は本番で常駐しません。

| 領域 | 役割 |
| --- | --- |
| Python CLI | Wiki取得、HTML解析、SQLite DB構築、動画メタデータ補完、D1 SQL生成 |
| Cloudflare Worker | D1を読み、検索・統計・詳細APIを返す |
| Cloudflare Pages | `frontend/dist` を静的配信する |
| Vue + Vite | Web UIを実装する |

Workerは通常リクエストで外部Wikiや動画サイトへアクセスしません。外部取得はDB構築や動画メタデータ更新のジョブだけが行います。

## Operation Words

このリポジトリでは、似た言葉を次の意味で使い分けます。

| 用語 | 意味 |
| --- | --- |
| 生成 | ローカルに派生ファイルを作る。例: D1 SQL、`wrangler.toml` |
| 投入 | 生成済み曲データをD1へ読み込ませる |
| deploy | Worker script や Pages artifact をCloudflareへ公開する |
| Terraform import | 既存CloudflareリソースをTerraform stateへ取り込む |
| 更新 | 文脈に応じた広い語。対象が曖昧になる場合は避ける |

例えば、D1に曲データを入れる操作は「投入」と書きます。Terraform の `import` と混同しないため、曲データについては「import」と書きません。

## Environment Flow

staging と production は役割を分けます。

1. 手元でSQLiteを作る
2. 必要ならlocal D1へ投入して画面を確認する
3. stagingへアプリケーションをdeployする
4. staging D1へデータを投入する
5. stagingの `/health` と代表検索を確認する
6. productionへ同じ流れで進める

`main` はCloudflare Pagesのproduction branchとして使いません。Cloudflare運用では `staging` と `production` ブランチを使います。
