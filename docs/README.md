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
| ドキュメントをブラウザで確認する | [documentation-quality.md](documentation-quality.md#docs-site) | [testing.md](testing.md#documentation-checks) |

このREADMEは開発者と個人運用者向けの地図です。利用者向けの宣伝文やSEO目的の説明は置かず、作業に必要な文書へ短く案内します。

## By Task

### Development

| 状況 | 読む順番 |
| --- | --- |
| 手元で画面を確認したい | [usage.md](usage.md) → [web-api.md](web-api.md) |
| Web UIに出るデータが古い・足りない | [concepts.md](concepts.md) → [usage.md](usage.md#missing-video-metadata) → [operations.md](operations.md#troubleshooting) |
| DB再構築が必要か判断したい | [concepts.md](concepts.md) → [usage.md](usage.md#when-local-d1-needs-reload) |
| CLI オプションだけ確認したい | [cli-reference.md](cli-reference.md) |
| テストを追加・実行したい | [testing.md](testing.md) |
| UI変更後にブラウザ操作を確認したい | [testing.md](testing.md#frontend-e2e) → [frontend-ui.md](frontend-ui.md#testing-boundary) |
| ドキュメントをブラウザで読みたい | [documentation-quality.md](documentation-quality.md#docs-site) → [project-structure.md](project-structure.md#docs-site) |
| release前の品質確認をしたい | [quality-gates.md](quality-gates.md) → [testing.md](testing.md) → [operations.md](operations.md) |

### Data

| 状況 | 読む順番 |
| --- | --- |
| 動画タイトルやサムネイルだけ更新したい | [usage.md](usage.md#missing-video-metadata) → [cli-reference.md](cli-reference.md#refresh_video_metadata) |
| DBを作り直して公開環境へ投入したい | [concepts.md](concepts.md) → [usage.md](usage.md) → [operations.md](operations.md) |
| 詳細情報の抽出がおかしい | [detail-extraction.md](detail-extraction.md) → [detail-extraction-algorithm.md](detail-extraction-algorithm.md) → [testing.md](testing.md) |

### Operations

| 状況 | 読む順番 |
| --- | --- |
| Cloudflare構成を初期設定・変更したい | [concepts.md](concepts.md) → [cloudflare-serverless.md](cloudflare-serverless.md) → [infrastructure.md](infrastructure.md) → [cloudflare-dns.md](cloudflare-dns.md) |
| Cloudflare DNS や Worker route が合っているか確認したい | [cloudflare-dns.md](cloudflare-dns.md) → [operations.md](operations.md#health-checks) |
| Cloudflareの低コスト負荷対策を確認したい | [production.md](production.md#low-cost-traffic-protection) → [operations.md](operations.md#traffic-protection-checks) |
| Cloudflare API token や実ドメインを書いてよい場所を確認したい | [repository-privacy.md](repository-privacy.md) → [infrastructure.md](infrastructure.md#create-cloudflare-api-token) |
| deploy後やD1投入後の疎通確認をしたい | [testing.md](testing.md#smoke-test) → [operations.md](operations.md#health-checks) |
| 個人情報や実ドメインを入れないルールを確認したい | [repository-privacy.md](repository-privacy.md) |
| 開発タスクの依存関係や担当を整理したい | [development-backlog.md](development-backlog.md) |
| 品質基準やrelease前チェックを確認したい | [quality-gates.md](quality-gates.md) |

### Design

| 状況 | 読む順番 |
| --- | --- |
| SQLite / D1 / deploy / Terraform import の関係を先に知りたい | [concepts.md](concepts.md) |
| なぜこの構成なのか知りたい | [concepts.md](concepts.md) → [production.md](production.md) → [project-structure.md](project-structure.md) |
| ドキュメントの品質基準や書き方を確認したい | [documentation-quality.md](documentation-quality.md) |
| ドキュメント改善候補を依存関係・担当つきで整理したい | [documentation-improvement-backlog.md](documentation-improvement-backlog.md) |

## Reference

| Document | 内容 |
| --- | --- |
| [concepts.md](concepts.md) | SQLite / local D1 / staging D1 / production D1、用語、環境の流れ |
| [usage.md](usage.md) | ローカルDB構築、CLI検索、local D1、開発サーバー |
| [operations.md](operations.md) | deploy、D1投入、health check、logs、rollback |
| [web-api.md](web-api.md) | Cloudflare Worker API 仕様 |
| [cli-reference.md](cli-reference.md) | CLIのコマンド、オプション、既定値 |
| [project-structure.md](project-structure.md) | ファイル配置、言語境界、生成物 |
| [data-model.md](data-model.md) | SQLite / D1 schema、文字数計算、人気度、曲詳細 |
| [frontend-ui.md](frontend-ui.md) | Web UI の検索ビュー、統計ビュー、レスポンシブ方針 |
| [detail-extraction.md](detail-extraction.md) | 曲ページ詳細の入出力、保存運用、動画メタデータ更新 |
| [detail-extraction-algorithm.md](detail-extraction-algorithm.md) | 詳細抽出ヒューリスティックの実装仕様 |
| [cloudflare-serverless.md](cloudflare-serverless.md) | Cloudflare Pages + Workers + D1 の全体構成 |
| [infrastructure.md](infrastructure.md) | Terraform 管理範囲、Cloudflare API token、import/apply |
| [production.md](production.md) | 本番ランタイム境界、読み取り専用運用、性能上の設計判断 |
| [cloudflare-dns.md](cloudflare-dns.md) | DNS CNAME、Pages custom domain、Worker route の期待状態 |
| [testing.md](testing.md) | テスト実行、smoke test、テストファイルの責務 |
| [quality-gates.md](quality-gates.md) | release前の品質基準、DB/API/UIの合格ライン |
| [development-backlog.md](development-backlog.md) | 開発タスク、依存関係、担当、プロセス改善 |
| [repository-privacy.md](repository-privacy.md) | 実値・秘匿情報を追跡ファイルに入れないルール |
| [documentation-quality.md](documentation-quality.md) | ドキュメント編集時の配置、用語、確認観点 |
| [documentation-improvement-backlog.md](documentation-improvement-backlog.md) | ドキュメント改善タスク、依存関係、担当、プロセス改善 |

## Document Boundaries

| Document | 置くもの | 置かないもの |
| --- | --- | --- |
| `usage.md` | ローカル開発、ローカルD1準備 | 全CLIオプション、公開環境手順 |
| `concepts.md` | 全文書で共有する概念と用語 | 個別コマンドの詳細手順 |
| `cli-reference.md` | CLIのオプション、既定値、実行例 | Web UI の画面仕様 |
| `project-structure.md` | ファイル配置と各領域の責務 | 個別関数の詳細仕様 |
| `data-model.md` | schema と保存データの意味 | API のURL一覧 |
| `web-api.md` | HTTP API contract | ローカル開発手順、UI レイアウト理由 |
| `frontend-ui.md` | 画面構成と表示ルール | API 実装詳細 |
| `detail-extraction.md` | 詳細情報の保存方針、入出力 | ヒューリスティックの細部 |
| `detail-extraction-algorithm.md` | 抽出アルゴリズム | 運用手順 |
| `cloudflare-serverless.md` | Cloudflare 全体像と責務分担 | Terraform import の細かい手順 |
| `infrastructure.md` | Terraform 管理範囲、API token、import/apply | 日常のDB更新手順 |
| `operations.md` | 日常運用、deploy、DB更新、ログ、rollback | 長い設計説明、Terraform import 詳細 |
| `production.md` | 本番設計判断、性能方針 | コピペ用の詳細 runbook |
| `cloudflare-dns.md` | DNS / route の期待状態 | Cloudflare API token の作り方、Terraform import 手順 |
| `testing.md` | テスト実行、smoke test、テストの責務境界 | 運用runbook、設計判断の長い説明 |
| `quality-gates.md` | release前チェック、品質基準、性能予算、backlog棚卸し | 個別API仕様、長い障害対応ログ |
| `development-backlog.md` | 開発タスク、依存関係、担当、プロセス改善 | 詳細な実装手順、完了済み作業ログ |
| `documentation-quality.md` | ドキュメント品質、用語、見出し、自然な日本語の基準 | 個別の運用手順、設定値 |
| `documentation-improvement-backlog.md` | ドキュメント改善タスク、依存関係、担当、プロセス改善 | 実際の運用手順、長い作業ログ |

## Privacy Rule

ドキュメントには個人の実値を入れません。ユーザー名、メールアドレス、実ドメイン、実IP、Cloudflare ID、API token はプレースホルダーで書きます。

詳しいルールと表記例は [repository-privacy.md](repository-privacy.md) を参照してください。
