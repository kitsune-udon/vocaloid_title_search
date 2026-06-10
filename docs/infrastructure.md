# Infrastructure As Code

Cloudflare の永続リソースは Terraform で管理します。対象は `infra/cloudflare/` です。

この文書は Terraform と Cloudflare リソースの管理手順です。アプリケーションのデプロイやDBデータ投入だけを行う場合は [operations.md](operations.md) を参照してください。

Terraform コマンドは、特に明記がない限り `infra/cloudflare/` で実行します。リポジトリルートから実行する wrapper は `tools/cloudflare_iac.sh` です。

この文書で扱う `Terraform import` は、既存Cloudflareリソースを Terraform state へ取り込む操作です。曲データをD1へ入れる操作ではありません。曲データのD1投入は [operations.md](operations.md#database-update) の `tools/update_d1.sh` で行います。

操作の違い:

| 操作 | 変更するもの | 変更しないもの | 主なコマンド |
| --- | --- | --- | --- |
| Terraform import | 既存Cloudflare resourceをlocal Terraform stateへ登録 | Cloudflare上のresource本体、D1データ | `tools/cloudflare_iac.sh import ...` |
| Terraform plan / apply | DNS、Pages custom domain、D1 databaseの器、Worker routeなど | Worker script、Pages artifact、D1曲データ | `tools/cloudflare_iac.sh plan`, `tools/cloudflare_iac.sh apply` |
| Pages / Worker deploy | frontend artifact、Worker script | DNS、D1曲データ、Terraform state | `tools/deploy_cloudflare.sh --env staging` |
| D1投入 | D1内の曲データ | Terraform resource、Worker script、Pages artifact | `tools/update_d1.sh --env staging` |

迷った場合は、Cloudflare上の「器」を変えるなら Terraform、アプリコードを公開するなら deploy、曲データを入れるなら D1投入です。

Terraform と Wrangler の境界:

| 対象 | 主担当 | 理由 |
| --- | --- | --- |
| Pages project, custom domain, DNS record, D1 database, Worker route | Terraform | 長く残るCloudflare resourceで、差分確認とimportが必要 |
| Pages artifact, Worker script | Wrangler経由のdeploy script | アプリケーションのrelease単位で頻繁に変わる |
| D1内の曲データ | `tools/update_d1.sh` | SQLiteから生成したデータ投入で、Terraform resourceではない |
| `cloudflare/worker/wrangler.toml` | `tools/generate_wrangler_toml.py` | 実D1 IDやCORS originを含むignore対象の派生設定 |

低レベルのWranglerコマンドは、通常の入口ではありません。日常運用では `tools/deploy_cloudflare.sh` と `tools/update_d1.sh` を使い、Terraform-managed resource の変更だけ `tools/cloudflare_iac.sh` を使います。

読む場所の目安:

| 状況 | 参照セクション |
| --- | --- |
| 何をTerraformで管理するか確認したい | Managed Resources / Terraform Scope |
| token や `terraform.tfvars` を準備したい | Setup / Credential Boundary / Collect Values |
| Dashboard や Wrangler で作った既存リソースをTerraform管理に入れたい | Existing Environment First / Existing Environment Import |
| 何もないCloudflare環境を新規作成したい | New Environment |
| 日常の差分確認だけしたい | Day Two Operations |

## Managed Resources

Terraform が管理するもの:

- Cloudflare Pages project
- Pages custom domains
- DNS CNAME records
- D1 databases
- Worker routes for `/api/*` and `/health`

Terraform が管理しないもの:

- Worker script のアップロード
- Pages の静的ファイルアップロード
- D1 への曲データ投入
- Cloudflare API credential や secret 本体

これらは既存スクリプトで扱います。

```bash
tools/deploy_cloudflare.sh --env staging
tools/update_d1.sh --env staging
```

## Terraform Scope

Worker script と Pages artifact はアプリケーションのリリース単位です。Terraform 管理に含めると、コードデプロイとインフラ変更が過度に結合します。

D1 database は Terraform で器だけを作り、データは `tools/update_d1.sh` で投入します。D1 resource には `prevent_destroy` を付けて、誤削除を防ぎます。

Worker route は Terraform で管理します。`cloudflare/worker/wrangler.toml` には route を書かず、Wrangler は Worker script と bindings のデプロイだけを担当します。

`prevent_destroy` が守るのはTerraform管理下のresource削除です。D1内の曲データ、手動Dashboard操作、Cloudflare側での外部変更、local state紛失までは守りません。D1データは `tools/update_d1.sh` のbackupとstaging確認で守ります。

## Setup

この節は `infra/cloudflare/` で作業します。

```bash
cd infra/cloudflare
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` に実値を入れます。このファイルは git ignore 対象です。

`account_id` と `zone_id` は名前ではなく Cloudflare のIDです。

```text
account_id = "Cloudflare Account ID"
zone_id    = "Cloudflare Zone ID"
zone_name  = "example.com"
```

`account_id` にメールアドレス、`zone_id` にドメイン名を入れないでください。Cloudflare Dashboard の Overview などに表示される ID を使います。

Cloudflare API credential は `terraform.tfvars` に書きません。Cloudflare provider が読む標準の環境変数で渡します。

```bash
export CLOUDFLARE_API_TOKEN=...
```

または、ignore 対象の `.env` に書きます。`tools/cloudflare_iac.sh` はプロジェクトルートの `.env` を自動で読み込みます。

```bash
CLOUDFLARE_API_TOKEN=...
```

## Credential Boundary

Cloudflare API token は主に Terraform / IaC 操作用です。`tools/deploy_cloudflare.sh` と `tools/update_d1.sh` も `.env` を読み込むため、`CLOUDFLARE_API_TOKEN` が環境にある場合は Wrangler がその token を利用する可能性があります。

| 操作 | 認証 |
| --- | --- |
| `tools/cloudflare_iac.sh verify-token` | `CLOUDFLARE_API_TOKEN` を直接 Cloudflare API に送る |
| `tools/cloudflare_iac.sh plan/apply/import` | Terraform Cloudflare provider が `CLOUDFLARE_API_TOKEN` を読む |
| `tools/deploy_cloudflare.sh` | Wrangler のログイン状態、または環境にある `CLOUDFLARE_API_TOKEN` など Wrangler が対応する認証を使う |
| `tools/update_d1.sh` | Wrangler のログイン状態、または環境にある `CLOUDFLARE_API_TOKEN` など Wrangler が対応する認証を使う |
| Worker runtime / frontend runtime | Cloudflare API token は使わない |

`CLOUDFLARE_API_TOKEN` を Worker secrets、`wrangler.toml`、frontend env、D1 に入れないでください。

必要な Cloudflare API credential 権限:

- Account: Cloudflare Pages: Edit
- Account: Workers Scripts: Edit
- Account: D1: Edit
- Zone: DNS: Edit
- Zone: Workers Routes: Edit

## Create Cloudflare API Token

Cloudflare Dashboard で user API token を作ります。Cloudflare公式ドキュメントでは、user token は `My Profile > API Tokens` から作成します。

Dashboard のメニュー名は変わることがあります。`My Profile` や `API Tokens` が見つからない場合は、Cloudflare Dashboard 内の検索、または account / profile 周辺の token 管理画面を探します。重要なのは、account API token ではなく user API token を作り、対象 account と zone だけに権限を絞ることです。

1. Cloudflare Dashboard にログイン
2. 右上の profile menu から `My Profile`
3. `API Tokens`
4. `Create Token`
5. `Create Custom Token`
6. Token name に用途が分かる名前を付ける
7. Permissions に次を追加

```text
Account / Cloudflare Pages / Edit
Account / Workers Scripts / Edit
Account / D1 / Edit
Zone / DNS / Edit
Zone / Workers Routes / Edit
```

8. Account Resources は対象 account に限定
9. Zone Resources は対象 zone に限定
10. `Continue to summary`
11. `Create Token`
12. 表示された secret を `.env` に保存

```bash
CLOUDFLARE_API_TOKEN=replace-with-cloudflare-api-token
```

token は作成直後の一度しか表示されません。漏れた場合やログに出した場合は Cloudflare Dashboard で roll するか revoke して作り直します。

tokenをrollした後:

1. 古いtokenをCloudflare Dashboardでrevokeする
2. 新しいtokenをignore対象の `.env` に保存する
3. shellを開き直すか、`.env` を読むwrapperを使う
4. `tools/cloudflare_iac.sh verify-token` を実行する
5. `tools/cloudflare_iac.sh plan` が認証エラーなく通ることを確認する

古いtokenをREADME、docs、`terraform.tfvars`、`wrangler.toml.example` に移してはいけません。

作成後に検証します。

```bash
tools/cloudflare_iac.sh verify-token
```

期待値は `success:true` です。

## Collect Values

`terraform.tfvars` に入れる値:

| key | 値 | 取得方法 |
| --- | --- | --- |
| `account_id` | Cloudflare Account ID | `wrangler whoami` または Dashboard |
| `zone_id` | Cloudflare Zone ID | Dashboard の対象 zone Overview、または Cloudflare API |
| `zone_name` | Zone 名 | 例: `example.com` |
| `project_name` | Pages project 名 | `wrangler pages project list` |
| `production_hostname` | production custom domain | Pages custom domain / DNS |
| `staging_hostname` | staging custom domain | Pages custom domain / DNS |

Dashboard で確認するもの:

| key | Dashboard上の主な場所 |
| --- | --- |
| `account_id` | Account Home または account overview |
| `zone_id` | 対象zoneのOverview |
| `production_hostname`, `staging_hostname` | Pages custom domains または DNS records |

Wrangler で確認できるもの:

```bash
env WRANGLER_LOG_PATH=/tmp/wrangler.log \
  cloudflare/worker/node_modules/.bin/wrangler whoami

env WRANGLER_LOG_PATH=/tmp/wrangler.log \
  cloudflare/worker/node_modules/.bin/wrangler pages project list

env WRANGLER_LOG_PATH=/tmp/wrangler.log \
  cloudflare/worker/node_modules/.bin/wrangler d1 list
```

`zone_id` は Wrangler の通常出力だけでは見つけにくいことがあります。その場合は Cloudflare Dashboard で対象 zone を開き、Overview の Zone ID をコピーします。

Cloudflare API で確認するもの:

| 値 | 用途 |
| --- | --- |
| DNS record ID | 既存DNS recordをTerraform stateへimportする |
| Worker route ID | 既存Worker routeをTerraform stateへimportする |

これらのIDは通常のアプリケーション運用では使いません。Terraform import が必要な時だけ取得します。

`terraform.tfvars` の例:

```hcl
account_id = "replace-with-account-id"
zone_id    = "replace-with-zone-id"
zone_name  = "example.com"

project_name        = "vocaloid-title-search"
production_branch   = "production"
production_hostname = "vocaloid-title-search.example.com"
staging_hostname    = "staging.vocaloid-title-search.example.com"
```

import に必要な追加ID:

| resource | 必要なID | 主な取得方法 |
| --- | --- | --- |
| D1 database | database UUID | `wrangler d1 list` |
| DNS record | DNS record ID | Cloudflare API |
| Worker route | route ID | Cloudflare API |
| Pages domain | domain name | `wrangler pages project list` |

Cloudflare API token が `.env` にある場合は、`tools/cloudflare_iac.sh` が自動で読み込みます。token の有効性は次で確認します。

```bash
tools/cloudflare_iac.sh verify-token
```

`terraform.tfvars.example` に変数を追加した場合は、この文書の `Collect Values` と `Setup` も同時に更新します。本文にだけ変数を足す、または example にだけ変数を足すと、初回設定で迷います。

## Existing Environment First

このプロジェクトは既に Cloudflare 上に Pages / Worker / D1 / DNS がある前提です。`Plan: ... to add` が大量に出た状態で `apply` しないでください。先に Terraform state へ import します。

このリポジトリの wrapper は、安全のため local `terraform.tfstate` がない状態の `apply` を拒否します。完全な新規環境だけ、次の環境変数で明示的に許可します。

```bash
VOCALOID_TERRAFORM_ALLOW_EMPTY_STATE_APPLY=1 tools/cloudflare_iac.sh apply
```

apply前に見る危険パターン:

| planの兆候 | 意味 | 対応 |
| --- | --- | --- |
| 既存環境なのに大量の `to add` | import漏れかstate紛失 | applyせずimport状況を確認 |
| D1 database の destroy / replace | データ消失リスク | 変数、resource名、stateを確認 |
| DNS record の target がproduction aliasへ変わる | stagingがproductionを向く可能性 | `cloudflare-dns.md` の期待値と照合 |
| Worker route のpatternが消える | `/api/*` や `/health` がHTMLを返す可能性 | route一覧を確認 |
| Pages custom domain の削除 | 公開URLが外れる | Dashboardのcustom domainも確認 |

Terraform state が壊れた、または紛失した場合:

1. applyしない
2. Cloudflare Dashboard と Wrangler で既存resourceが残っているか確認する
3. `terraform.tfvars` の値が現在の環境と合っているか確認する
4. `Existing Environment Import` の手順でstateへimportし直す
5. `terraform plan` の差分が期待値だけになるまでapplyしない

## Existing Environment Import

既に Dashboard / Wrangler で作成済みのリソースがある場合、最初に Terraform state へ import します。import なしで apply すると、同名リソース作成で失敗することがあります。

ID 形式は Cloudflare provider のバージョンで変わる可能性があるため、失敗したら provider のエラーに出る期待形式に合わせます。

Cloudflare APIで取得するIDとWranglerで取得しやすいIDは異なります。

| 対象 | Wranglerで確認 | Cloudflare APIで確認 | 用途 |
| --- | --- | --- | --- |
| account | `wrangler whoami` | account API | `terraform.tfvars` |
| D1 database | `wrangler d1 list` | D1 API | Terraform stateへD1 databaseを取り込む |
| Pages project | `wrangler pages project list` | Pages API | Pages project import |
| DNS record | なし | DNS records API | DNS record import |
| Worker route | なし | Workers routes API | Worker route import |

この例は `infra/cloudflare/` で実行します。

```bash
cd infra/cloudflare
terraform init

terraform import cloudflare_pages_project.app '<account_id>/<project_name>'
terraform import cloudflare_d1_database.dev '<account_id>/<dev_database_id>'
terraform import cloudflare_d1_database.staging '<account_id>/<staging_database_id>'
terraform import cloudflare_d1_database.production '<account_id>/<production_database_id>'

terraform import 'cloudflare_pages_domain.app["staging"]' '<account_id>/<project_name>/staging.vocaloid-title-search.example.com'
terraform import 'cloudflare_pages_domain.app["production"]' '<account_id>/<project_name>/vocaloid-title-search.example.com'

terraform import 'cloudflare_dns_record.pages_cname["staging"]' '<zone_id>/<dns_record_id>'
terraform import 'cloudflare_dns_record.pages_cname["production"]' '<zone_id>/<dns_record_id>'

terraform import 'cloudflare_workers_route.api["staging_api"]' '<zone_id>/<route_id>'
terraform import 'cloudflare_workers_route.api["staging_health"]' '<zone_id>/<route_id>'
terraform import 'cloudflare_workers_route.api["production_api"]' '<zone_id>/<route_id>'
terraform import 'cloudflare_workers_route.api["production_health"]' '<zone_id>/<route_id>'
```

import 後:

```bash
terraform plan
```

差分が custom domain / DNS target / route の期待値だけになっていることを確認してから apply します。

## New Environment

完全な新規環境では、Worker route を最後に作ります。Worker script がまだ存在しない状態で route を作ろうとすると失敗するためです。

初回の流れ:

```text
Terraform: Pages / custom domain / DNS / D1
  -> generate_wrangler_toml.py
  -> Wrangler: Worker script deploy
  -> Terraform: Worker routes
  -> update_d1.sh: D1 data
```

Worker routes を後回しにする理由は、routeが指すWorker scriptが先に存在している必要があるためです。scriptがない状態でrouteだけ作ると、Terraform applyが失敗するか、公開経路が中途半端になります。

まず Pages project、custom domain、DNS、D1 database だけを作ります。

このブロックは `infra/cloudflare/` で実行します。

```bash
cd infra/cloudflare
terraform init
../../tools/cloudflare_iac.sh plan
VOCALOID_TERRAFORM_ALLOW_EMPTY_STATE_APPLY=1 ../../tools/cloudflare_iac.sh apply -var 'manage_worker_routes=false'
```

apply 後に ignore 対象の `cloudflare/worker/wrangler.toml` を生成します。生成スクリプトは Terraform state から D1 database ID と Pages custom domain を読みます。

```bash
cd ../..
python3 tools/generate_wrangler_toml.py
```

Worker script と Pages artifact を deploy します。

```bash
tools/deploy_cloudflare.sh --env staging
tools/deploy_cloudflare.sh --env production
```

Worker script を作成した後、通常の apply で Worker routes を作成します。

```bash
tools/cloudflare_iac.sh plan
tools/cloudflare_iac.sh apply
```

最後にDBを構築してD1へ投入します。stagingで確認してからproductionへ進めます。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db
tools/update_d1.sh --env staging
tools/update_d1.sh --env production
```

## Common Errors

| エラー | 主な原因 | 対応 |
| --- | --- | --- |
| `401 Unauthorized` | `CLOUDFLARE_API_TOKEN` が未設定、無効、期限切れ、または現在のshellにない | tokenを検証し、必要ならrollする |
| `403 Forbidden` | tokenの権限不足、account / zone範囲違い | token permissionsとresource scopeを確認 |
| `Plan: ... to add` が既存環境で大量に出る | Terraform stateにimportされていない | applyせずimportする |
| D1 resourceのdestroyが出る | resource名、変数、stateの不一致 | applyせずstateとtfvarsを確認 |
| provider upgrade後に差分が増える | provider schemaやID形式変更 | lockfile、provider changelog、planを確認 |

`401 Unauthorized` の場合は、まず token を検証します。

```bash
curl -sS https://api.cloudflare.com/client/v4/user/tokens/verify \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"
```

`success:true` にならない場合は token を作り直します。権限不足の場合は `403 Forbidden` になることが多く、`401` は認証そのものの失敗を疑います。

Terraform providerをupgradeする場合:

1. `.terraform.lock.hcl` の差分を確認する
2. `terraform init -upgrade` 後に `tools/cloudflare_iac.sh plan` を見る
3. provider都合の表記差分と実resource変更を分ける
4. import ID形式の変更がある場合はproviderのエラーに従う
5. productionに関わる変更はstaging相当の差分確認を先に行う

## Day Two Operations

日常のアプリケーションdeployやD1投入は [operations.md](operations.md) を正本にします。この節は、インフラ変更が必要な時の入口だけを示します。

インフラ変更:

```bash
cd infra/cloudflare
../../tools/cloudflare_iac.sh plan
../../tools/cloudflare_iac.sh apply
```

アプリケーション更新:

```bash
tools/deploy_cloudflare.sh --env staging
tools/deploy_cloudflare.sh --env production
```

DBデータ更新:

```bash
tools/update_d1.sh --env staging
tools/update_d1.sh --env production
```

## State File Handling

- `terraform.tfvars`, `.terraform/`, `*.tfstate` は追跡しません。
- Terraform state には resource ID などの運用情報が入るため、ローカル管理する場合も公開リポジトリへ置きません。
- team運用にする場合は、Terraform Cloud、private backend、または状態ファイルを安全に保管できる仕組みを検討します。
