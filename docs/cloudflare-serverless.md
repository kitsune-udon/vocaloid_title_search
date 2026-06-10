# Cloudflare Serverless Architecture

Cloudflare Pages + Workers + D1 で公開する現在の構成概要です。この構成は、VPS上で常駐プロセスを運用する負担を減らし、静的フロントエンド、読み取り中心のAPI、D1上の検索DBを分けて管理するために採用しています。Terraform の実作業は [infrastructure.md](infrastructure.md)、日常運用は [operations.md](operations.md) を参照してください。

この文書は全体像だけを扱います。実行手順は次に分けます。

| やりたいこと | 参照先 |
| --- | --- |
| Cloudflareリソースを作成・Terraform import・変更する | [infrastructure.md](infrastructure.md) |
| staging / production へdeployする | [operations.md](operations.md) |
| DNS / Worker route の期待状態を確認する | [cloudflare-dns.md](cloudflare-dns.md) |
| API contract を確認する | [web-api.md](web-api.md) |
| 低コスト負荷対策の方針を確認する | [production.md](production.md#low-cost-traffic-protection), [operations.md](operations.md#traffic-protection-checks) |

## Architecture

```text
Browser
  -> Cloudflare Pages
       frontend/dist

  -> Cloudflare Worker
       /health
       /api/metadata
       /api/popularity-labels
       /api/search
       /api/stats
       /api/song-detail

  -> Cloudflare D1
       songs
       metadata
       song_details
       song_credit_people
```

Python は本番ランタイムでは使いません。Wiki 取得、HTML 解析、SQLite DB 構築、D1 投入用 SQL 生成だけを手元または CI の build-time toolchain として実行します。

## Responsibilities

| 領域 | 管理方法 | 変更するもの | 変更しないもの |
| --- | --- | --- | --- |
| Cloudflare 永続リソース | Terraform | Pages project, custom domains, DNS CNAME, D1 database, Worker routes | D1内の曲データ、Worker script本文 |
| Worker script | Wrangler / `tools/deploy_cloudflare.sh` | Worker API のコード | DNS、custom domain、D1データ |
| Pages artifact | Wrangler / `tools/deploy_cloudflare.sh` | `frontend/dist` | DNS、Worker routes、D1データ |
| D1 data | `tools/update_d1.sh` | staging / production D1 内のテーブルデータ | SQLite DB構築、Wiki取得、Pages / Worker deploy |
| Local DB build | Python CLI | ローカル SQLite | Cloudflare上のD1、Pages、Worker |

日常運用では wrapper script を優先します。低レベルの Wrangler / Terraform コマンドを直接使うのは、状態確認や障害切り分けで wrapper だけでは足りない場合に限定します。

## Branch Policy

`main` は Cloudflare の production branch として使いません。

| Branch | Pages | Worker | D1 | custom domain |
| --- | --- | --- | --- | --- |
| `staging` | preview / staging artifact | staging Worker | staging D1 | staging custom domain |
| `production` | production artifact | production Worker | production D1 | production custom domain |

Cloudflare Pages の production branch は `production` に設定し、preview branch として `staging` を使います。

## Environment Matrix

staging と production は同じ構成を持ちますが、成果物、D1、custom domain は分けます。

| 領域 | staging | production |
| --- | --- | --- |
| Git branch | `staging` | `production` |
| Pages artifact | staging branch の `frontend/dist` | production branch の `frontend/dist` |
| Worker script | staging Worker | production Worker |
| D1 database | staging D1 | production D1 |
| custom domain | staging custom domain | production custom domain |
| DNS target | staging Pages branch alias | production Pages alias |
| Worker route | staging custom domain の `/api/*`, `/health` | production custom domain の `/api/*`, `/health` |
| 主な用途 | production前の確認 | 公開経路 |

どちらの環境でも、Pages は静的UI、Worker はJSON API、D1 は検索DBを担当します。stagingで確認しているつもりがproductionのD1やPages aliasを見ていないか、DNS target、Worker route、D1 bindingを分けて確認します。

## Traffic Protection Boundary

Cloudflare Proxy、WAF、bot対策、rate limiting、logs、D1 metrics は「公開経路を守る運用」の領域です。アプリケーションコードやDB構築CLIで過剰アクセスを直接止めようとせず、Cloudflare側の観測と制御を使います。

| 対象 | 主な責務 | 正本 |
| --- | --- | --- |
| `robots.txt` / `noindex` | 善意のcrawlerと検索流入を抑える | [production.md](production.md#search-engine-policy) |
| Cloudflare Proxy / WAF / bot対策 | 過剰アクセスや攻撃的trafficを抑える | [production.md](production.md#low-cost-traffic-protection) |
| Worker logs / D1 metrics | 遅いAPI、失敗、読み取り増加を観測する | [operations.md](operations.md#traffic-protection-checks) |

Turnstileや強いrate limitは初期状態では入れません。実際の過剰アクセスやbot trafficを確認してから検討します。

## Local Development

ローカル開発では Worker と Vite dev server を分けて起動し、Vite の proxy が `/api/*` を Worker dev server へ転送します。Worker はD1を読むため、ローカルD1へSQLite由来のデータを入れてから起動します。

具体的な手順とポート確認は [usage.md](usage.md#local-dev-server) に置きます。この文書では、本番構成と同じ Worker + D1 経路を手元で再現する、という目的だけを確認します。

| ローカル | Cloudflare |
| --- | --- |
| Vite dev server | Pages |
| Wrangler dev Worker | Worker |
| local D1 | staging / production D1 |
| `vocaloid_titles.sqlite3` | D1へ投入する元データ |

## Wrangler Config

実設定は ignore 対象の `cloudflare/worker/wrangler.toml` に置きます。追跡するのは `cloudflare/worker/wrangler.toml.example` だけです。

Terraform state がある場合は、D1 database ID と custom domain から自動生成します。

```bash
python3 tools/generate_wrangler_toml.py
```

生成元:

- `infra/cloudflare/terraform.tfstate`
- `cloudflare/worker/wrangler.toml.example`

state がまだない完全な初回だけ、テンプレートをコピーして仮設定します。

```bash
cp cloudflare/worker/wrangler.toml.example cloudflare/worker/wrangler.toml
```

`wrangler.toml` に入るもの:

- Worker script name
- `main`
- `compatibility_date`
- `CORS_ORIGINS`
- D1 binding `DB`
- 各環境の D1 database name / database ID

`wrangler.toml` に書かないもの:

- Worker routes
- Pages custom domains
- DNS records
- API token や secret

Worker routes、Pages custom domains、DNS records、D1 database の器は Terraform (`infra/cloudflare`) で管理します。Wrangler は Worker script と D1 binding を使った deploy を担当します。

この構成の公開経路は custom domain の Worker routes です。Wrangler deploy 時に `workers.dev` や preview URL に関する警告が出ても、custom domain の `/health` と `/api/*` が正しく Worker を指していれば本番経路の確認としては十分です。`workers.dev` 自体を無効化するかどうかは、公開経路の方針を変えるときに別途判断します。

D1 database ID は Terraform import / apply 後に state へ入り、生成スクリプトが `wrangler.toml` へ書き出します。

```bash
python3 tools/generate_wrangler_toml.py --dry-run
```

## Deploy Flow

初回環境構築では Worker script がまだ存在しないため、Terraform の Worker routes は最後に作ります。詳細は [infrastructure.md](infrastructure.md) の `New Environment` を参照してください。

通常更新の流れ:

1. Terraform で Cloudflare 永続リソースの差分を確認
2. staging に Pages / Worker をデプロイ
3. staging D1 を更新
4. staging の `/health` と代表検索を確認
5. production に同じ流れでdeployし、必要な場合はproduction D1へ投入

コピペ用の詳細手順は [operations.md](operations.md) に置きます。ここでは責務分担だけを確認します。

```bash
tools/cloudflare_iac.sh plan
tools/deploy_cloudflare.sh --env staging
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db
tools/update_d1.sh --env staging
```

Wrangler deployとPages deployの違い:

| 操作 | 成果物 | 影響 |
| --- | --- | --- |
| Worker deploy | Worker script | `/api/*`, `/health` の挙動 |
| Pages deploy | `frontend/dist` | 画面のHTML/CSS/JS |
| D1投入 | D1 table data | 検索結果、統計、曲詳細 |

## Failure Isolation

| 症状 | 疑う領域 | 最初の確認 |
| --- | --- | --- |
| 画面が開かない | Pages / custom domain | Pages deployments |
| 画面は開くが検索できない | Worker route / Worker | `/health` |
| `/health` はOKだが結果が古い | D1 data | `/api/metadata` |
| 詳細だけ開かない | `song_details` | `/api/song-detail` |
| stagingだけおかしい | staging DNS / Worker / D1 | staging custom domain |
| productionだけおかしい | production DNS / Worker / D1 | production custom domain |

## Runtime Boundaries

- Worker は通常リクエストで外部 Wiki や動画サイトへアクセスしません。
- Worker routes は Terraform 管理です。`wrangler.toml` で routes を重複管理しません。
- D1 database は Terraform で器だけを作り、データ更新は `tools/update_d1.sh` に限定します。
- production D1投入はatomic swapではなくテーブル置換を伴うため、staging で確認してから実行します。
