# Operations Runbook

日常運用の短い手順集です。現在の推奨本番構成は Cloudflare Pages + Workers + D1 です。Cloudflare構成の詳細は [cloudflare-serverless.md](cloudflare-serverless.md) を参照してください。

この文書は「すでにCloudflareリソースがある」前提の運用手順です。Pages project、DNS、D1 database、Worker route を作成またはimportする場合は [infrastructure.md](infrastructure.md) を先に確認してください。

SQLite、local D1、staging D1、production D1 の役割は [concepts.md](concepts.md) を参照してください。

運用は個人運用を基本にします。production操作では staging確認、dry-run、smoke test、backup確認を行いますが、大規模な常時監視体制は前提にしません。公開サイトは検索エンジン流入を増やさない方針で、robots と `noindex` により善意のcrawlerを抑制します。

## First Five Minutes

障害や違和感に気づいたら、まず変更対象を増やさず状態確認だけを行います。

1. custom domain の `/health` を見る
2. 代表検索がJSONを返すか見る
3. 画面だけの問題か、Worker APIも壊れているか分ける
4. 直前の操作が deploy、D1投入、Terraform apply のどれか確認する
5. Worker logs、Pages deployments、D1 metrics の順に見る

すぐ再deployや再投入を行うと原因が分かりにくくなります。`database_ready:false`、HTML応答、HTTP 4xx/5xx のどれかを先に分類します。

## Traffic Protection Checks

負荷対策は [production.md](production.md#low-cost-traffic-protection) の「標準」レベルを基本にします。日常運用では、強い制限を先に入れるのではなく、ログと指標を見て必要になったら追加します。

確認する場所:

| 見る場所 | 何を見るか | 次の判断 |
| --- | --- | --- |
| Cloudflare Analytics | request数、国、path、4xx/5xxの増加 | 急増していればlogsとWAF eventsを見る |
| Worker logs | `api_timing`, 5xx, 同じpathの連続失敗 | 遅いAPIや失敗pathを切り分ける |
| D1 metrics | read回数、error、latency傾向 | cacheやquery見直しを検討する |
| WAF / Security events | botらしいアクセス、同一IPの連続アクセス | managed rulesや軽いrate limitを検討する |
| Pages deployments | 直近deployと異常発生時刻 | deploy起因かtraffic起因か分ける |

すぐ入れないもの:

- Turnstile
- 強いrate limit
- ユーザー操作を妨げるchallenge

これらは、実際に過剰アクセスやbotアクセスが確認され、通常のProxy、robots/noindex、ログ確認だけでは足りない場合に検討します。

## Public Endpoints

| Environment | Page | Health | Representative search |
| --- | --- | --- | --- |
| staging | `https://staging.vocaloid-title-search.example.com/` | `https://staging.vocaloid-title-search.example.com/health` | `https://staging.vocaloid-title-search.example.com/api/search?length=7&sort=popularity` |
| production | `https://vocaloid-title-search.example.com/` | `https://vocaloid-title-search.example.com/health` | `https://vocaloid-title-search.example.com/api/search?length=7&sort=popularity` |

## Database Update

検索データの source of truth は手元の `vocaloid_titles.sqlite3` です。Cloudflare D1 は公開APIが読む配布先として扱います。

データ更新の流れ:

```text
初音ミク Wiki
  -> build_db
  -> vocaloid_titles.sqlite3
  -> update_d1.sh
  -> staging D1 / production D1
```

`tools/update_d1.sh` はWiki取得やSQLite DB構築を行いません。既存の SQLite DB からD1用SQLを生成し、指定したstaging / production D1へ投入します。

D1 SQLを生成する前に、`python -m vocaloid_title_search.cli.validate_db` でローカルSQLiteを検査します。曲数と詳細件数、metadata、詳細JSON、作曲者派生テーブルに問題がある場合はD1投入へ進みません。

D1投入の影響範囲:

| コマンド | 変更するもの | 変更しないもの |
| --- | --- | --- |
| `tools/update_d1.sh --env staging` | staging D1 | production D1、Pages、Worker script、Terraform resource |
| `tools/update_d1.sh --env production` | production D1 | staging D1、Pages、Worker script、Terraform resource |

SQLite DBを更新するのは `build_db` と `refresh_video_metadata` です。`tools/update_d1.sh` は既存SQLiteを読み、D1用SQLを生成して対象D1へ投入するだけです。

まずSQLite DBを作成または更新します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db
```

動画メタデータも更新する場合は、DB構築後に別途実行します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.refresh_video_metadata
```

その後、D1へ投入します。Terraform state がある場合、D1 database name と公開URLは自動解決され、投入後に公開APIの smoke test を実行します。stagingで確認してからproductionへ進めます。

ここでの smoke test は、D1投入後に公開APIが最低限使えるかを確認する短い疎通確認です。D1の中身を網羅的に検証するものではなく、`/health`、metadata、根拠タグ、代表検索、代表曲の詳細、統計APIが custom domain 経由でJSONを返すかを見ます。

```bash
tools/update_d1.sh --env staging
```

staging確認後にproduction D1へ投入します。

```bash
tools/update_d1.sh --env production
```

確認プロンプトを省略する場合:

```bash
tools/update_d1.sh --env staging --yes
```

実行前に何を行うかだけ確認する場合:

```bash
tools/update_d1.sh --env staging --dry-run
```

公開URLを明示的に上書きする場合は `--base-url` または `VOCALOID_PUBLIC_BASE_URL` を使います。Terraform state がなく公開URLも指定しない場合、D1投入後の公開API smoke test はスキップされます。明示的にスキップしたい場合は `--skip-smoke-checks` を使います。

D1投入の再実行判断:

| 状況 | 再実行してよいか | 次の確認 |
| --- | --- | --- |
| SQL生成前に失敗 | はい | `vocaloid_titles.sqlite3` が存在するか確認 |
| SQL生成後、D1投入前に失敗 | はい | 生成されたSQLを再利用するか再生成する |
| `wrangler d1 execute` が通信で失敗 | 多くの場合はい | D1 metrics と `/health` を確認してから再実行 |
| transaction文拒否で失敗 | そのまま再実行しない | `tools/export_d1_sql.py` でSQLを再生成 |
| smoke testだけ失敗 | すぐ再投入しない | `/health`、Worker binding、route、metadataを切り分ける |
| production投入途中に不明な失敗 | stagingへ戻らず確認優先 | backup SQL、D1 metrics、Worker logsを確認 |

## Update Matrix

何を変更したかによって、実行する手順を分けます。

| 変更内容 | 実行すること | 実行しないこと |
| --- | --- | --- |
| フロントエンドだけ | `tools/deploy_cloudflare.sh --env staging` → `tools/deploy_cloudflare.sh --env production` | DB再構築、D1投入 |
| Worker APIだけ | `tools/deploy_cloudflare.sh --env staging` → `tools/deploy_cloudflare.sh --env production` | DB再構築、D1投入 |
| Wiki由来データだけ | `build_db` → 必要なら `refresh_video_metadata` → `tools/update_d1.sh --env staging` → `tools/update_d1.sh --env production` | Pages / Worker deploy |
| DB schema と Worker API | DB構築、D1投入、Worker deployをstagingで確認してからproductionへ進める | productionだけの先行投入 |
| DNS / route / D1 resource | `tools/cloudflare_iac.sh plan` → `apply` | `wrangler.toml` にrouteを書く |

迷った場合は、stagingでアプリケーションとD1の両方を更新し、`/health` と代表検索で確認してからproductionへ進めます。

stagingからproductionへの時系列:

```text
1. 変更対象を決める
   -> app deploy / D1投入 / Terraform apply
2. stagingへdeploy、D1投入、またはTerraform applyを行う
3. staging smoke test と必要な画面確認を行う
4. productionで実行するコマンドを1つに絞る
5. productionへdeploy、D1投入、またはTerraform applyを行う
6. production smoke test を確認する
7. 失敗時は再実行前に /health、logs、backup を確認する
```

同じ日に複数種類の変更を行う場合も、staging確認を挟みます。D1投入、Pages / Worker deploy、Terraform apply を同時に実行した場合は、失敗時の切り分けが難しくなります。

## Production Readiness Checklist

productionへ進む前に、直近のstaging確認結果を残します。

共通の品質基準は [quality-gates.md](quality-gates.md) を確認します。

```text
対象:
  [ ] Pages / Worker deploy
  [ ] D1投入
  [ ] Terraform apply

staging確認:
  health checked at:
  representative search checked at:
  stats checked at:
  detail accordion checked at:

productionで実行する操作:
  command:
  expected changed target:
  expected unchanged target:
```

最終確認:

- productionで実行する操作が、deploy、D1投入、Terraform apply のどれか分かっている
- stagingの `/health` が `database_ready:true` を返した
- stagingの代表検索、統計、代表曲詳細がJSONまたは画面で確認できた
- production D1投入の場合、直前backupが作られることを理解している
- Terraform apply の場合、planに意図しない削除や作り直しがない
- 実ドメインやIDを追跡ファイルへ書いていない

staging確認を省略しない変更:

| 変更 | 理由 |
| --- | --- |
| Worker APIのレスポンス形状変更 | UIとAPI contractを同時に壊す可能性がある |
| DB schema、D1投入、metadata変更 | `database_ready` や検索結果に影響する |
| Terraform apply | DNS、route、D1など公開経路を変える |
| 検索条件、ページング、統計表示 | 主要体験に直接影響する |
| rollback手順を伴う変更 | 失敗時の戻し方を先に確認する必要がある |

staging確認を簡略化できることがある変更:

| 変更 | 最低限の確認 |
| --- | --- |
| 誤字修正だけのdocs | privacy scan |
| READMEやdocsのリンク修正 | 対象リンクとprivacy scan |
| UI文言だけでAPI契約に触れない変更 | frontend build |
| テストだけの追加 | 該当テストと `tools/check_all.sh` |

迷う場合は staging を使います。個人運用では手順を短くするより、失敗時の切り分けができる状態を優先します。

## Infrastructure Change

Cloudflare の永続リソースは Terraform で管理します。DNS / Pages custom domain / D1 / Worker route を変更する場合は [infrastructure.md](infrastructure.md) を先に確認します。

Cloudflare の永続リソースを変更する場合は、まず Terraform の差分を確認します。

```bash
tools/cloudflare_iac.sh plan
```

Terraform apply を実行する場合:

```bash
tools/cloudflare_iac.sh apply
```

## Application Deploy

Cloudflare Pages は `frontend/dist` をデプロイします。通常はWorker deployも含めて次を使います。このスクリプトは Worker deploy 前に Terraform state から `cloudflare/worker/wrangler.toml` を再生成します。

```bash
tools/deploy_cloudflare.sh --env staging
```

Terraform state または `--base-url` から公開URLが分かる場合、deploy後に Worker API の smoke test を実行します。smoke test が失敗した場合、スクリプトは失敗として終了します。

staging確認後にproductionへ進めます。production deploy は確認プロンプトを出します。自動化する場合だけ `--yes` を付けます。

```bash
tools/deploy_cloudflare.sh --env production
```

```bash
tools/deploy_cloudflare.sh --env production --yes
```

`--skip-build` を使う場合は、事前に `frontend/dist/index.html` が存在している必要があります。

実行前に変更対象だけ確認したい場合は dry-run を使います。

```bash
tools/deploy_cloudflare.sh --env staging --dry-run
tools/deploy_cloudflare.sh --env production --dry-run
```

dry-run は、ビルドやdeployの対象、利用する設定、実行予定のコマンドを確認するために使います。Cloudflare上のPages、Worker、D1は変更しません。

deploy後のsmoke testを明示的にスキップする場合は `--skip-smoke-checks` を使います。通常はstagingでスキップせず、公開経路の `/health` と主要APIまで確認します。

Wrangler が dirty worktree や `workers.dev` / preview URL に関する警告を出すことがあります。dirty worktree は未コミット変更を含む成果物をdeployする注意喚起です。`workers.dev` / preview URL の警告は、custom domain の Worker route が主経路である限り、custom domain の `/health` と `/api/*` で確認します。

productionへ進む前の確認:

- staging の `/health` が `database_ready:true` を返す
- staging の代表検索がJSONを返し、HTMLを返していない
- staging の画面で検索、統計、曲詳細が開ける
- productionへ進める変更が、アプリケーションdeployだけか、D1投入だけか、両方か分かっている
- Cloudflareリソースを変更する場合は `tools/cloudflare_iac.sh plan` の差分を確認済み

production判断:

| 状況 | 判断 |
| --- | --- |
| staging smoke test が通らない | productionへ進まない |
| stagingでUIまたは代表APIが壊れている | productionへ進まない |
| 変更対象がD1だけで、deploy差分がない | `tools/update_d1.sh --env production` のみ実行 |
| 変更対象がPages / Workerだけで、DB差分がない | `tools/deploy_cloudflare.sh --env production` のみ実行 |
| D1投入後のsmoke testだけ失敗 | すぐ再投入せず、`/health` とWorker bindingを切り分ける |
| productionで旧データへ戻す必要がある | `release/backups/<env>/<timestamp>/` のrollback SQLを使う |

production更新後の確認:

```bash
curl https://vocaloid-title-search.example.com/health
curl 'https://vocaloid-title-search.example.com/api/search?length=7&sort=popularity'
```

期待する状態:

- `/health` が `{"ok":true,"database_ready":true}` を返す
- `/api/search` がJSONを返す
- `/api/*` がPagesのHTMLを返さない

手動でPagesだけデプロイする場合:

```bash
(cd frontend && yarn build)
cloudflare/worker/node_modules/.bin/wrangler pages deploy frontend/dist \
  --project-name vocaloid-title-search \
  --branch staging
```

Worker を手動でデプロイする場合は、まず Terraform state から `cloudflare/worker/wrangler.toml` を再生成します。このファイルは ignore 対象で、実ドメインや D1 ID をリポジトリへ入れません。Worker routes は Terraform 管理なので `wrangler.toml` には書きません。

手動コマンドでは `npx wrangler` ではなく、`cloudflare/worker/node_modules/.bin/wrangler` または `./node_modules/.bin/wrangler` を使います。これは `cloudflare/worker/yarn.lock` で固定した Wrangler を使い、実行時にnpm側で別バージョンを解決しないためです。

```bash
python3 tools/generate_wrangler_toml.py
(cd cloudflare/worker && ./node_modules/.bin/wrangler deploy --env staging)
(cd cloudflare/worker && ./node_modules/.bin/wrangler deploy --env production)
```

手動Wranglerコマンドは、wrapper scriptで扱えない復旧や確認に限定します。通常のアプリケーションdeployは `tools/deploy_cloudflare.sh`、D1投入は `tools/update_d1.sh` を使います。

## Health Checks

```bash
curl https://staging.vocaloid-title-search.example.com/health
curl 'https://staging.vocaloid-title-search.example.com/api/search?length=7&sort=popularity'
```

Worker API全体のsmoke test:

```bash
python3 tools/check_worker_api.py \
  --base-url https://staging.vocaloid-title-search.example.com
```

この smoke test は custom domain の Worker route を確認します。`*.pages.dev` は Pages の静的配信用で、`/health` がHTMLを返しても custom domain の `/health` がJSONを返すならAPI route確認としては問題ありません。

smoke test が保証する範囲:

- custom domain から Worker API に到達できる
- Worker が想定する D1 binding を読める
- DB readiness、metadata、代表検索、代表詳細、統計が最低限応答する

smoke test が保証しない範囲:

- Web UI の全操作
- 全検索条件と全ページング条件
- 詳細抽出アルゴリズムの正しさ
- Cloudflare Dashboard上の全設定差分

smoke test が失敗した場合は、最初に `/health` の結果を見ます。`database_ready:false` ならD1投入、metadata、schema、Worker bindingを確認します。HTMLが返る場合はWorker routeやDNSを確認します。HTTP 403 やCloudflareのブロックが疑われる場合は、`tools/check_worker_api.py` が送るUser-AgentとCloudflare側のルールを確認します。

D1投入後に統計ビューで見る代表値:

- 総曲数が極端に少なくない
- 詳細件数が総曲数と一致している
- 作曲者あり件数が `0` ではない
- 公開年あり件数が `0` ではない
- 根拠タグ分布が空ではない

## Logs

Cloudflare Dashboard:

- Workers & Pages → 対象Worker → Logs / Metrics
- Pages → 対象プロジェクト → Deployments
- D1 → 対象DB → Metrics

Dashboardで見る場所の目安:

| 確認したいこと | Dashboard上の場所 |
| --- | --- |
| 最新のPagesデプロイが成功したか | Workers & Pages → Pages project → Deployments |
| custom domain が対象Pages projectに付いているか | Workers & Pages → Pages project → Custom domains |
| Worker script が最新か、エラーが出ていないか | Workers & Pages → Worker → Deployments / Logs |
| `/api/*` と `/health` がWorkerへ向いているか | 対象zone → Workers Routes |
| DNS CNAME が期待する Pages alias を指しているか | 対象zone → DNS → Records |
| D1にリクエストやエラーが出ているか | Workers & Pages → D1 → 対象DB → Metrics |

CLIでリアルタイムに見る場合:

```bash
(cd cloudflare/worker && ./node_modules/.bin/wrangler tail vocaloid-title-search-api-production)
```

最初に見る場所:

| 症状 | 最初に見るもの |
| --- | --- |
| 画面は開くが検索できない | custom domain `/health`, Worker logs |
| `/api/*` がHTMLを返す | Worker routes, DNS records |
| `database_ready:false` | D1 metadata, D1投入ログ |
| deploy直後に画面が古い | Pages deployments, browser cache |
| D1投入後に件数がおかしい | `tools/update_d1.sh` output, `/api/stats` |

Worker logsで見る代表的な兆候:

| ログや症状 | 主な原因 | 次の確認 |
| --- | --- | --- |
| `{"event":"api_timing",...}` | APIごとの処理時間ログ | 遅いpathを `tools/profile_worker_api.py` で再計測 |
| `database is not ready` | metadata不足、schema不一致、詳細件数不足 | `/health`, D1 metadata |
| `no such table` | D1投入先間違い、SQL投入失敗 | D1 database name、`tools/update_d1.sh --dry-run` |
| `page_size must be one of 50, 100, 200` | フロントまたは手動リクエストのquery不正 | `web-api.md` のvalidation |
| HTMLが返る | Worker route漏れ、Pages経路を見ている | `cloudflare-dns.md`、Workers Routes |
| CORS error | `CORS_ORIGINS` 不足 | `wrangler.toml` 生成元とWorker env |

## Rollback

Pages は Cloudflare Dashboard の Pages deployments から以前のデプロイを再昇格できます。

D1 への投入はテーブル置換を伴うため、直前のSQLがない場合は即時rollbackできません。`tools/update_d1.sh` は `release/backups/<env>/<timestamp>/` に更新前後のDB/SQLを保存します。smoke test が失敗した場合は、更新前SQLをD1へ再投入するrollbackコマンドを表示します。

rollbackコマンドも Terraform import ではありません。保存済みSQLを同じD1へ読み込ませ、D1のデータ内容を更新前の状態へ戻す操作です。

D1投入全体はatomic swapとして扱いません。productionのDB更新はstaging確認後、低トラフィックの時間帯に実行します。

rollback後の確認:

1. production `/health` が `database_ready:true` を返す
2. production 代表検索がJSONを返す
3. 統計APIが総曲数と詳細件数を返す
4. 代表曲の詳細アコーディオンが開く
5. 直前に失敗した操作が再発していないことをWorker logsで見る

## Troubleshooting

- `/api/*` がHTMLを返す: Terraform-managed Worker route が未作成、または違う Worker を指しています。`tools/cloudflare_iac.sh plan` と Cloudflare Dashboard の Worker routes を確認します。
- `database_ready:false`: D1投入失敗、metadata不足、またはWorkerが別DB bindingを見ています。
- `wrangler d1 execute` が transaction 文で失敗: Cloudflare上のD1へ投入するSQLに `BEGIN`, `COMMIT`, `SAVEPOINT` が含まれています。`tools/export_d1_sql.py` で再生成します。
- `workers.dev` が403: custom route運用では問題ない場合があります。カスタムドメインの `/health` と `/api/*` を確認します。
- `*.pages.dev/health` がHTMLを返す: branch alias 側にWorker routeを置いていない場合は想定内です。custom domain の `/health` を確認します。

失敗箇所別の初動:

| 失敗箇所 | 最初に見るもの | 次に見るもの |
| --- | --- | --- |
| Pages deploy | Pages Deployments | frontend build output |
| Worker deploy | Worker Deployments / Logs | `wrangler.toml`, D1 binding |
| D1投入 | `tools/update_d1.sh` output | D1 Metrics, `/health` |
| Terraform apply | Terraform plan / state | Cloudflare Dashboard resource |
| DNS / route | custom domain `/health` | DNS Records, Workers Routes |

障害時の初動:

1. `/health` を確認する
2. `/api/search?length=7&sort=popularity` がJSONを返すか確認する
3. Pages画面だけが壊れているのか、Worker APIも壊れているのかを分ける
4. 直前に実行した操作が deploy、D1投入、Terraform apply のどれかを確認する
5. Worker logs、Pages deployment、D1 metrics の順に確認する
