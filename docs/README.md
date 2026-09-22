# Documentation Guide

このディレクトリは、ローカル開発、データ構築、Cloudflare運用、設計判断を目的別に分けています。迷ったときは、このページから読み始めます。

## Fast Routes

| 目的 | 最初に読む | 次に読む |
| --- | --- | --- |
| 開発を始める | [usage.md](usage.md) | [testing.md](testing.md) |
| DBを更新する | [concepts.md](concepts.md) | [cli-reference.md](cli-reference.md), [operations.md](operations.md#database-update) |
| stagingで確認する | [operations.md](operations.md) | [quality-gates.md](quality-gates.md) |
| productionへdeployまたはD1投入する | [operations.md](operations.md#production-readiness-checklist) | [production.md](production.md) |
| Cloudflareの器を変える | [infrastructure.md](infrastructure.md) | [cloudflare-dns.md](cloudflare-dns.md) |
| UIやAPIを直す | [frontend-ui.md](frontend-ui.md), [web-api.md](web-api.md) | [testing.md](testing.md) |
| データ抽出を直す | [detail-extraction.md](detail-extraction.md) | [detail-extraction-algorithm.md](detail-extraction-algorithm.md) |
| UI変更の回帰確認をする | [testing.md](testing.md#frontend-e2e) | [quality-gates.md](quality-gates.md#e2e-policy) |
| 動画タイトル・サムネイルが欠けている | [usage.md](usage.md#missing-video-metadata) | [cli-reference.md](cli-reference.md#refresh_video_metadata) |
| CI・実Workerの結合検証 | [testing.md](testing.md#ci-and-worker-integration) | [quality-gates.md](quality-gates.md) |
| 公開APIの性能を継続計測する | [testing.md](testing.md#api-performance-history) | [production.md](production.md) |
| 検索SQLの性能を測る | [testing.md](testing.md#search-sql-benchmark) | [production.md](production.md) |
| タスクや改善候補を管理する | [development-backlog.md](development-backlog.md) | [documentation-improvement-backlog.md](documentation-improvement-backlog.md) |
| ドキュメントをブラウザで確認する | [documentation-quality.md](documentation-quality.md#docs-site) | [testing.md](testing.md#documentation-checks) |

このREADMEは開発者と個人運用者向けの地図です。利用者向けの宣伝文やSEO目的の説明は置かず、作業に必要な文書へ短く案内します。

## Document Boundaries

| Document | 置くもの | 置かないもの |
| --- | --- | --- |
| [usage.md](usage.md) | ローカル開発、ローカルD1準備 | 全CLIオプション、公開環境手順 |
| [concepts.md](concepts.md) | 全文書で共有する概念と用語 | 個別コマンドの詳細手順 |
| [cli-reference.md](cli-reference.md) | CLIのオプション、既定値、実行例 | Web UI の画面仕様 |
| [project-structure.md](project-structure.md) | ファイル配置と各領域の責務 | 個別関数の詳細仕様 |
| [data-model.md](data-model.md) | schema と保存データの意味 | API のURL一覧 |
| [web-api.md](web-api.md) | HTTP API contract | ローカル開発手順、UI レイアウト理由 |
| [frontend-ui.md](frontend-ui.md) | 画面構成と表示ルール | API 実装詳細 |
| [detail-extraction.md](detail-extraction.md) | 詳細情報の保存方針、入出力 | ヒューリスティックの細部 |
| [detail-extraction-algorithm.md](detail-extraction-algorithm.md) | 抽出アルゴリズム | 運用手順 |
| [cloudflare-serverless.md](cloudflare-serverless.md) | Cloudflare 全体像と責務分担 | Terraform import の細かい手順 |
| [infrastructure.md](infrastructure.md) | Terraform 管理範囲、API token、import/apply | 日常のDB更新手順 |
| [operations.md](operations.md) | 日常運用、deploy、DB更新、ログ、rollback | 長い設計説明、Terraform import 詳細 |
| [production.md](production.md) | 本番設計判断、性能方針 | コピペ用の詳細 runbook |
| [cloudflare-dns.md](cloudflare-dns.md) | DNS / route の期待状態 | Cloudflare API token の作り方、Terraform import 手順 |
| [testing.md](testing.md) | テスト実行、smoke test、テストの責務境界 | 運用runbook、設計判断の長い説明 |
| [quality-gates.md](quality-gates.md) | release前チェック、品質基準、性能予算、backlog棚卸し | 個別API仕様、長い障害対応ログ |
| [development-backlog.md](development-backlog.md) | 開発タスク、依存関係、担当、プロセス改善 | 詳細な実装手順、完了済み作業ログ |
| [documentation-quality.md](documentation-quality.md) | ドキュメント品質、用語、見出し、自然な日本語の基準 | 個別の運用手順、設定値 |
| [documentation-improvement-backlog.md](documentation-improvement-backlog.md) | ドキュメント改善タスク、依存関係、担当、プロセス改善 | 実際の運用手順、長い作業ログ |

## Privacy Rule

ドキュメントには個人の実値を入れません。ユーザー名、メールアドレス、実ドメイン、実IP、Cloudflare ID、API token はプレースホルダーで書きます。

詳しいルールと表記例は [repository-privacy.md](repository-privacy.md) を参照してください。
