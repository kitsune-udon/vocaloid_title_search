# Cloudflare DNS And Routes

Cloudflare Pages + Workers + D1 の公開経路だけをまとめます。作成・変更手順は [infrastructure.md](infrastructure.md)、日常確認は [operations.md](operations.md) を参照してください。

## Request Flow

```text
Browser
  -> Cloudflare edge
     -> Pages: /
     -> Worker: /api/*, /health
        -> D1
```

責務境界:

| 要素 | 役割 | 管理場所 |
| --- | --- | --- |
| DNS CNAME | custom domain を Pages alias へ向ける | Terraform |
| Cloudflare Proxy | DNS応答をedge IPにし、Cloudflare経由で受ける | Cloudflare DNS record |
| Pages | `/` などの静的Web UIを配信する | Pages deploy |
| Worker route | `/api/*` と `/health` を Worker へ送る | Terraform |
| Worker | D1を読んでJSON APIを返す | Worker deploy |
| D1 | 検索DBを保持する | Terraformで器、`update_d1.sh`でデータ |

## DNS Records

DNS は Cloudflare Proxy 有効の CNAME として Terraform で管理します。

| 用途 | Host | CNAME target |
| --- | --- | --- |
| staging | `staging.vocaloid-title-search.example.com` | `staging.vocaloid-title-search.pages.dev` |
| production | `vocaloid-title-search.example.com` | `vocaloid-title-search.pages.dev` |

## Pages Branch Alias

`staging` は branch alias の `staging.vocaloid-title-search.pages.dev` に向けます。production の `vocaloid-title-search.pages.dev` に向けないでください。staging custom domain が production Pages deployment を指すと、stagingで確認しているつもりでもproduction相当の画面を見てしまいます。

branch alias は Pages の静的配信確認用です。API route の確認は custom domain 側の `/health` と `/api/*` で行います。

Pages branch alias と custom domain の見え方:

| 確認対象 | 期待するもの | 注意点 |
| --- | --- | --- |
| `staging.<project>.pages.dev` | staging branch の静的HTML | Worker route は通常ここには付けない |
| `<production-project>.pages.dev` | production branch の静的HTML | staging custom domain の CNAME target にしない |
| staging custom domain `/` | staging Pages の静的HTML | DNS CNAME は staging branch alias を指す |
| staging custom domain `/health` | staging Worker の JSON | Worker route が custom domain に必要 |
| production custom domain `/health` | production Worker の JSON | D1 binding も production を見る |

## Worker Routes

Worker routes も Terraform で管理します。`cloudflare/worker/wrangler.toml` には routes を書きません。

| 用途 | Pattern | Worker |
| --- | --- | --- |
| staging API | `staging.vocaloid-title-search.example.com/api/*` | `vocaloid-title-search-api-staging` |
| staging health | `staging.vocaloid-title-search.example.com/health` | `vocaloid-title-search-api-staging` |
| production API | `vocaloid-title-search.example.com/api/*` | `vocaloid-title-search-api-production` |
| production health | `vocaloid-title-search.example.com/health` | `vocaloid-title-search-api-production` |

route確認では、DashboardとCLIの役割を分けます。

| 場面 | 優先する確認 |
| --- | --- |
| custom domain が正しい Pages project に付いているか | Dashboard の Pages custom domains |
| CNAME target が期待通りか | Dashboard の DNS Records または Terraform plan |
| `/api/*` と `/health` がWorkerへ向いているか | Dashboard の Workers Routes と custom domain の `curl` |
| 実際にAPIとして動くか | `curl https://<custom-domain>/health` |

Worker routeのpatternが重複または不足すると、`/api/*` がPagesのHTMLを返したり、`/health` だけ404になることがあります。`/api/*` と `/health` は別routeなので、片方だけ成功しても両方確認します。

## Health Checks

```bash
curl https://staging.vocaloid-title-search.example.com/health
curl 'https://staging.vocaloid-title-search.example.com/api/search?length=7&sort=popularity'
curl https://vocaloid-title-search.example.com/health
curl 'https://vocaloid-title-search.example.com/api/search?length=7&sort=popularity'
```

`/api/*` が HTML を返す場合は、Terraform-managed Worker route が未作成か、route が違う Worker を指しています。

Worker routes は custom domain 側で管理しているため、`https://<staging-pages-alias>/health` は Pages のHTMLを返すことがあります。

Proxy有効時のDNS確認:

```bash
dig +short staging.vocaloid-title-search.example.com
dig +short vocaloid-title-search.example.com
```

Cloudflare Proxy が有効な場合、`dig` は Cloudflare の edge IP を返します。これは正常です。CNAME target が期待通りかは Dashboard の DNS record、または Terraform state / plan で確認します。公開経路が正しいかは、最終的に custom domain の `/health` がJSONを返すかで判断します。

`dig` と `/health` の読み方:

| 結果 | 読み方 |
| --- | --- |
| `dig` がCloudflare edge IPを返し、`/health` がJSON | 正常 |
| `dig` がCloudflare edge IPを返し、`/health` がHTML | DNSはProxy経由だがWorker routeが当たっていない |
| `dig` が何も返さない | DNS recordまたはcustom domain設定を確認 |
| `/api/search` はJSONだが `/health` がHTML | health routeだけ漏れている可能性 |
| `/health` はJSONだが `/api/search` がHTML | api routeだけ漏れている可能性 |

Cloudflare Proxyで隠れるものと隠れないもの:

| 項目 | Proxy有効時の扱い |
| --- | --- |
| DNS queryで見えるIP | Cloudflare edge IPになる |
| Pages / Workerへの公開経路 | Cloudflare edgeを経由する |
| リポジトリ内の実ドメイン | 隠れない。追跡ファイルへ書かない |
| Cloudflare account / D1 ID | 隠れない。ローカル設定やstateで管理 |
| 直接外部に公開したorigin IP | A recordや別経路があれば隠れない |

Proxy mode はSEO対策ではありません。検索エンジン流入を抑える方針は `robots.txt` とHTMLの `noindex` を中心に扱い、Proxy mode はCloudflare edge経由の配信、origin保護、WAFやログ確認のために使います。

役割の違い:

| 目的 | 使うもの |
| --- | --- |
| custom domain を Cloudflare edge 経由にする | proxied DNS record |
| `/api/*` と `/health` を Worker へ送る | Worker route |
| 検索結果への掲載を抑える | `robots.txt`, `noindex` |
| 過剰アクセスを観測・制御する | Cloudflare logs, WAF, rate limiting |

Proxy有効時の見え方:

```text
dig custom domain
  -> Cloudflare edge IP

curl https://custom-domain/health
  -> Worker route
  -> JSON health response

curl https://custom-domain/
  -> Pages
  -> Web UI HTML
```

Proxy有効時は、`dig` のIPだけでは Pages alias や Worker route が正しいか判断できません。DNS recordのCNAME target、Pages custom domain、Worker route、`/health` のJSON応答を分けて確認します。

## Operational Notes

| 確認項目 | 期待状態 |
| --- | --- |
| origin VM | 使わない |
| A record | origin IPを持たせない |
| staging CNAME | staging branch aliasを指す |
| production CNAME | production Pages aliasを指す |
| Worker routes | custom domain の `/api/*` と `/health` にある |
| 追跡ファイル | 実ドメイン、Cloudflare ID、D1 IDを書かない |

Pages custom domainを削除・再追加する場合は、DNS record、Pages custom domain、Worker routesを同時に確認します。custom domainだけ戻しても、Worker routeが外れているとAPIはHTMLや404を返します。

CNAME target誤りを疑う場合:

1. staging custom domain の CNAME target が staging branch alias か見る
2. production custom domain の CNAME target が production Pages alias か見る
3. custom domain `/` が期待する画面を返すか見る
4. custom domain `/health` が期待するWorker JSONを返すか見る
