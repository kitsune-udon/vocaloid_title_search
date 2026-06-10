# Repository Privacy

追跡ファイルに実ドメイン、実IP、ユーザー名、メールアドレス、各種秘匿情報を書き込まないためのルールです。

この文書を、リポジトリ内の秘匿情報ルールの正本として扱います。`AGENTS.md` はこの文書を参照し、同じ一覧を重複して持ちません。

## Basic Rule

Gitで追跡するファイルには実値を書かず、プレースホルダーを使います。

この文書で扱うのは「リポジトリに書かない情報」です。公開サイトに検索エンジン流入を増やす情報を載せない方針は [production.md](production.md#search-engine-policy) に置きます。両者は目的が異なります。

| 方針 | 守るもの | 例 |
| --- | --- | --- |
| Repository privacy | 個人、origin、Cloudflare resource、secretの混入を防ぐ | 実ドメイン、実IP、token、account IDを書かない |
| Search engine policy | 公開サイトへの不要な流入と負荷増を抑える | `robots.txt`, `noindex`, SEO最適化をしない |

公開サイトで見える値であっても、運用環境や個人を特定できる値は追跡ファイルに書きません。ドキュメントの例では `example.com` や `replace-with-...` を使います。

追跡ファイルには、次の実値を書きません。

| 種類 | 例 |
| --- | --- |
| 運用URL | 実ドメイン、実ホスト名、Pages custom domain、CORS origin |
| ネットワーク | public origin IP address |
| 個人情報 | server name、VM name、実ユーザー名、個人メールアドレス、SSH key path |
| 秘密情報 | API token、Cloudflare token、GitHub token、OAuth secret、cookie、password |
| Cloudflare ID | account ID、database ID、zone ID、route ID |
| ローカル設定 | `.env`, `.dev.vars`, `wrangler.toml` などの中身 |

| 種類 | 使う値 |
| --- | --- |
| ドメイン | `staging.vocaloid-title-search.example.com`, `vocaloid-title-search.example.com` |
| origin IP | `203.0.113.10` |
| メールアドレス | `user@example.com` |
| Cloudflare ID | `replace-with-...` |
| API token / secret | `replace-with-...` |

`example.com` と `203.0.113.0/24` はドキュメント用に予約された値です。

実値は `.env`, `.dev.vars`, `cloudflare/worker/wrangler.toml` など、ignore済みのローカルファイルにだけ置きます。

## Decision Examples

迷ったときは、次の表で判断します。

| 書こうとしているもの | 追跡ファイルに書くか | 代わりにどう書くか |
| --- | --- | --- |
| 本番custom domain | いいえ | `vocaloid-title-search.example.com` |
| staging custom domain | いいえ | `staging.vocaloid-title-search.example.com` |
| origin IP | いいえ | `203.0.113.10` |
| Cloudflare account ID / zone ID / D1 database ID | いいえ | `replace-with-account-id` など |
| Cloudflare Pages project name | 実運用名なら原則いいえ | `vocaloid-title-search` のような汎用名、または placeholder |
| `.env` の中身 | いいえ | `.env.example` にキー名だけを書く |
| API token の作り方 | はい | 権限名と保存先だけを書く。token値は書かない |
| 公式ドキュメントURL | はい | 公開仕様として必要なURLだけを書く |
| npm / PyPI package名 | はい | 個人・運用環境を特定しないため可 |
| smoke test用の例URL | はい、placeholderなら可 | `https://staging.vocaloid-title-search.example.com` |

判断基準:

- その値で個人、アカウント、運用環境、originを特定できるなら書かない。
- 他人が同じ値を使えないなら書かない。
- 公開仕様として誰でも参照できる値なら書いてよい。
- 迷ったら placeholder にする。

## Agent Rule

Codexなどのエージェント向けには repository root の `AGENTS.md` からこの文書を参照します。

エージェントへ秘匿情報混入防止を明示したいときは、以下を添えます。

```text
実ドメイン、実IP、ユーザー名、メールアドレス、Cloudflare ID、API tokenなどはファイルに書かず、必ずプレースホルダーにしてください。
```

## Local Config Files

追跡するのは example のみです。

```text
.env.example
*.example
cloudflare/worker/wrangler.toml.example
```

追跡しない実値ファイル:

```text
.env
.env.*
.dev.vars
cloudflare/worker/wrangler.toml
```

`wrangler.toml` には実環境の D1 database ID や CORS origin を置けますが、Worker routes、Pages custom domains、DNS records は Terraform 管理のため書きません。

Cloudflare API token は `.env` などのローカル環境に置きます。`terraform.tfvars`、`wrangler.toml.example`、README、docs、frontend env には書きません。

Terraform state がある場合、`cloudflare/worker/wrangler.toml` は次で再生成します。

```bash
python3 tools/generate_wrangler_toml.py
```

## Privacy Scan

コミット前に以下を実行します。

```bash
python3 tools/check_sensitive_values.py
```

このスクリプトは追跡ファイルを対象に、以下の値を検出します。

- `example.com` 以外のメールアドレス
- public IP address
- allowlist 外のドメイン名
- token, secret, password などに見える代入

検出された場合は、実値をプレースホルダーへ置き換えます。

| 検出対象 | 守れること | 限界 |
| --- | --- | --- |
| メールアドレス | 個人メールの混入検出 | 画像内の文字は検出しない |
| public IP | origin IPらしき値の検出 | private IPや文脈判断は限定的 |
| allowlist外ドメイン | 実ドメイン混入の検出 | 新しい公式ドメインはallowlist判断が必要 |
| secret風の代入 | tokenやpasswordの混入検出 | すべての秘密形式を網羅しない |

`.env` を共有しないでください。必要な値を共有する場合は、Cloudflare Dashboard、password manager、または権限を絞った再発行手順を使います。チャット、Issue、README、docsへ貼り付けません。

スクリーンショットを共有する場合も、実ドメイン、account ID、zone ID、D1 ID、token、メールアドレスが写っていないか確認します。

## Leak Response

実値をコミットした場合:

1. それ以上pushしない
2. tokenやsecretなら即座にrollまたはrevokeする
3. 追跡ファイルをプレースホルダーへ修正する
4. `python3 tools/check_sensitive_values.py` を実行する
5. 既にリモートへpush済みなら、履歴対応が必要か判断する
6. allowlistで隠すのではなく、なぜ漏れたかを再発防止する

## Allowlist Policy

`tools/check_sensitive_values.py` の allowlist は、公開仕様として必要な値だけを追加します。検出を黙らせるために、運用中の実ドメイン、個人アカウント、Cloudflare ID、token らしき値を allowlist へ入れてはいけません。

allowlist に追加してよい例:

- 仕様上固定の公開サービスドメイン
- パッケージレジストリや公式CDNなど、個人や運用環境を特定しないドメイン
- ドキュメント用に予約された `example.com`, `example.net`, `example.org`
- ドキュメント用に予約された `203.0.113.0/24`, `198.51.100.0/24`, `192.0.2.0/24`

allowlist に追加しない例:

- このアプリの実 custom domain
- Cloudflare Pages project の実ホスト名
- 実VM名、実ユーザー名、実メールアドレス
- Cloudflare account ID、zone ID、D1 database ID、route ID
- 一時的なトークン、署名付きURL、cookie

迷う場合は、値をプレースホルダーへ置き換えます。公開情報としてどうしても必要な場合だけ、なぜ追跡ファイルに必要かをコードレビューで説明できる形にします。

## Limitations

このスキャンは補助です。すべての秘密情報を完全に検出するものではありません。

特に新しい外部サービスのURLや公開仕様として必要なドメインを追加する場合は、値が本当に公開情報か確認し、必要なら `tools/check_sensitive_values.py` の allowlist を更新します。
