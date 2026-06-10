# Development Backlog

この文書は、開発を進めるための未完了タスクを管理する場所です。ドキュメントだけの改善は [documentation-improvement-backlog.md](documentation-improvement-backlog.md) に分けます。

## How To Use

- 完了したタスクは `Done` にして、必要なら後で削除します。
- 依存関係があるタスクは `Depends on` にタスクIDを書きます。
- 人間の判断や外部作業が必要な場合は `Owner` を `Human` または `Shared` にします。
- 開発サイクル自体の改善は `Process Improvement` に追加します。
- 秘匿情報や実ドメインは書かず、[repository-privacy.md](repository-privacy.md) に従います。

## Task Template

| Field | Value |
| --- | --- |
| ID | `DEV-000` |
| Status | `Open` |
| Priority | `High` / `Medium` / `Low` |
| Owner | `Agent` / `Human` / `Shared` |
| Area | code / frontend / worker / data / infra / tooling / docs / process |
| Depends on | task IDs or `none` |
| Decision needed | human decision or `none` |
| Acceptance | observable completion condition |
| Verification | tests, commands, smoke checks, or review |

## Status Values

| Status | Meaning |
| --- | --- |
| `Open` | 未着手。依存関係や作業範囲の確認が必要 |
| `Ready` | 依存関係がなく、Agentがすぐ着手できる |
| `Blocked` | Human decision、外部作業、別タスク完了が必要 |
| `Done` | Acceptance と Verification を満たした |

## ID Rules

- 開発タスクは `DEV-001` から連番にします。
- Human decision は `HD-001` から連番にします。
- Process improvement は `PI-001` から連番にします。
- 既存IDは再利用しません。削除済みタスクの番号も再利用しません。
- 新規タスクを追加するときは、この文書内の最大番号を確認して次の番号を使います。
- ドキュメントだけで完了するタスクは [documentation-improvement-backlog.md](documentation-improvement-backlog.md) に置きます。

## High

| ID | Status | Owner | Area | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEV-001 | Done | Agent | frontend | none | 検索・統計・詳細表示の主要ユーザーフローをPlaywrightでE2E smoke化する | local Worker + Viteで検索、統計遷移、詳細アコーディオン、ページングが自動確認できる | `(cd frontend && yarn test:e2e)` |
| DEV-002 | Done | Agent | frontend | DEV-001 | フロントエンドのアクセシビリティ基礎監査を追加する | キーボード操作、focus visible、aria label、色コントラストの主要問題が検出・修正される | `tools/check_frontend_accessibility.py`, `tools/check_all.sh` |
| DEV-003 | Done | Agent | frontend | DEV-001 | APIエラー時のUI表示を標準化する | `400` / `404` / `503` / network error がユーザーに分かる文言で表示される | `frontend/src/api.ts`, `yarn build` |
| DEV-004 | Done | Agent | worker | none | Worker APIのエラーレスポンス契約をテストで網羅する | `/api/search`, `/api/song-detail`, `/api/stats`, `/api/metadata` の代表エラーがテストされる | `(cd cloudflare/worker && yarn test)` |
| DEV-005 | Done | Agent | data | none | DB品質検査コマンドを追加する | 曲数、詳細件数、作曲者件数、公開年件数、動画件数、metadata整合性をローカルSQLiteで検査できる | `tests/test_database_quality.py`, `uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.validate_db --json` |
| DEV-006 | Done | Agent | data | DEV-005 | D1投入前にDB品質検査を実行する導線を追加する | `tools/update_d1.sh` 実行前にローカルSQLite品質の失敗を検出できる | `tests/test_update_d1_script.py`, `tools/update_d1.sh --env staging --dry-run --skip-smoke-checks`, `tools/check_all.sh` |
| DEV-007 | Done | Shared | product | none | 品質指標の合格ラインを決める | 検索レスポンス、初期表示、詳細表示、DB品質件数、アクセシビリティの最低基準が文書化される | [quality-gates.md](quality-gates.md) |
| DEV-008 | Done | Agent | worker | DEV-007 | APIレスポンスタイムの計測ログを追加する | 主要APIの処理時間をローカル/production logsで確認できる | Worker timing log test |
| DEV-009 | Done | Agent | frontend | DEV-007 | フロントエンドのパフォーマンス予算を設定する | bundle size、主要画面の初期表示、詳細展開の目標値が定義される | [quality-gates.md](quality-gates.md), frontend build |
| DEV-010 | Done | Agent | data | none | 詳細抽出の失敗・空データを一覧化するレポートを追加する | credits、introduction、videos、published_year の欠損を曲URL付きで確認できる | `tests/test_detail_quality.py`, `uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.report_detail_quality --limit 0` |
| DEV-011 | Done | Agent | frontend | DEV-001 | モバイル表示の回帰スクリーンショット確認方針を決める | スクリーンショット差分を今入れるか判断し、代替確認が決まる | 操作E2Eのmobile projectを採用。スクリーンショット差分は見送り |
| DEV-012 | Done | Agent | infra | none | staging smoke testをdeploy scriptの成功条件として明確化する | staging deploy後に主要API smoke testが自動または明示手順で必ず走る | `tests/test_deploy_cloudflare_script.py`, `tools/deploy_cloudflare.sh --env staging --dry-run --base-url ...` |
| DEV-036 | Done | Agent | frontend | DEV-024 | noindex / robots の回帰検査を追加する | frontend build後に `noindex,nofollow,noarchive` と `robots.txt` の `Disallow: /` が検査される | `tools/check_frontend_metadata.py`, `tools/check_all.sh` |
| DEV-037 | Done | Agent | worker | DEV-007 | Worker APIの基本セキュリティヘッダーを点検する | JSON APIと静的HTMLで付与すべきヘッダー方針が実装・テスト・文書で揃う | Worker tests, `frontend/public/_headers`, `tools/check_frontend_metadata.py` |
| DEV-038 | Done | Shared | infra | DEV-024 | Cloudflare側の低コスト負荷対策を決める | 個人運用向けのWAF/rate limiting/cache/log確認の最低方針が決まる | [production.md](production.md#low-cost-traffic-protection) |
| DEV-043 | Done | Agent | docs | none | VitePressでローカルDocsプレビューを追加する | 既存Markdownを使い、目的別ナビゲーション、サイドバー、ローカルpreviewが使える | `(cd docs-site && yarn build)` |
| DEV-044 | Done | Agent | tooling | DEV-043 | docs専用チェックコマンドを追加する | リンク切れ、秘匿情報、孤立文書、見出し重複の最低限を1コマンドで確認できる | `tools/check_docs.sh` |
| DEV-045 | Done | Agent | tooling | DEV-044 | docsチェックと既存品質ゲートの関係を整理する | `check_all.sh` に含める軽量検査と、手動実行する重いdocs検査の境界が実装される | `tools/check_all.sh`, `tools/check_docs.sh`, [testing.md](testing.md#documentation-checks) |

## Medium

| ID | Status | Owner | Area | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEV-013 | Done | Agent | frontend | DEV-003 | 空状態・未検索状態・検索結果0件の表示を磨く | 初期表示、条件なし、結果0件、エラー時の表示が一貫する | `yarn build` |
| DEV-014 | Done | Agent | frontend | DEV-001 | 表示項目メニューの操作性を改善する | desktop/mobileで表示項目の変更が分かりやすく、誤タップしにくい | `yarn build` |
| DEV-015 | Done | Agent | frontend | DEV-001 | 統計ビューから検索へ遷移した時の条件表示を明確化する | 統計由来の検索条件が検索画面で確認でき、解除できる | `yarn build` |
| DEV-016 | Done | Agent | worker | DEV-004 | API validationのエラーメッセージを整理する | ユーザー起因エラーとDB未準備エラーの文言が区別される | Worker tests |
| DEV-017 | Done | Agent | data | DEV-005 | 動画メタデータ更新結果の成功率を出力する | 更新対象数、成功数、失敗数、フォールバック残り件数が分かる | `tests/test_video_metadata.py`, refresh progress output |
| DEV-018 | Done | Agent | data | DEV-010 | 作曲者抽出の品質サンプルレビューを支援する | composer欠損や不自然な値を上位から確認できる | `report_detail_quality`, `tests/test_detail_quality.py` |
| DEV-019 | Done | Agent | data | DEV-010 | 公開年抽出の品質サンプルレビューを支援する | NULLや範囲外候補、保存値不一致候補を確認できる | `tests/test_detail_quality.py`, `report_detail_quality` |
| DEV-020 | Done | Agent | frontend | DEV-009 | 詳細アコーディオンの表示遅延をユーザーに分かる形にする | loading表示と遅延時文言が自然に出る | `yarn build` |
| DEV-021 | Done | Agent | worker | DEV-008 | `/api/stats` の重い集計を見直す | stats APIのqueryとindex利用を確認し、必要なら最適化される | Worker stats metadata-count test、`tools/profile_worker_api.py` |
| DEV-022 | Done | Agent | worker | DEV-008 | `/api/search` の代表条件ごとの性能を測る | length/composer/year/tag/page_size別の処理時間を比較できる | `tools/profile_worker_api.py`, `tests/test_profile_worker_api.py` |
| DEV-023 | Done | Agent | frontend | DEV-002 | アイコンボタンのラベルとtooltipを点検する | Wikiリンク、開閉、表示項目などの操作名が支援技術でも分かる | `yarn build`、aria/title確認 |
| DEV-024 | Done | Shared | product | DEV-007 | SEO / クロール方針を決める | robots、metadata、検索エンジンに見せる範囲の方針が決まる | 検索エンジン流入を抑制する方針を [production.md](production.md#search-engine-policy) に記録 |
| DEV-025 | Done | Agent | frontend | DEV-024 | basic metadataとOGPを整える | title/description/OGPがプロダクト内容を正しく表す | `frontend/index.html`, `frontend/public/robots.txt`, frontend build |
| DEV-026 | Done | Agent | docs | DEV-007 | 品質ゲートをREADMEまたは運用文書に追加する | release前に見る品質チェックが一覧化される | README, [quality-gates.md](quality-gates.md), [operations.md](operations.md) |
| DEV-027 | Done | Agent | process | DEV-001 | E2Eを`tools/check_all.sh`に入れるか判断する | 通常checkに含める/別コマンドにする基準が決まる | [quality-gates.md](quality-gates.md#e2e-policy) |
| DEV-028 | Done | Agent | worker | none | Worker APIの型生成・共有型運用を点検する | 実装、shared型、docsの乖離を検出する方法が決まる | `tools/check_api_contract_sources.py`, [web-api.md](web-api.md) |
| DEV-039 | Done | Agent | process | DEV-034 | 完了済み開発タスクの削除基準を整える | Done削除後も正本文書・テスト・履歴から変更理由を追える | Done deletion criteria |
| DEV-040 | Done | Agent | tooling | DEV-012 | deploy / D1投入 script のdry-run出力を標準化する | 変更対象、変更しない対象、smoke test対象URLが同じ形式で表示される | `tools/lib.sh`, script tests, `--dry-run` |

## Low

| ID | Status | Owner | Area | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEV-029 | Done | Agent | frontend | DEV-013 | 検索条件の入力補助文言を改善する | 文字数、作曲者、公開年の入力意図が短く分かる | `yarn build` |
| DEV-030 | Done | Agent | frontend | DEV-014 | 結果カードの情報密度を微調整する | desktopで余白が大きすぎず、mobileで詰まりすぎない | `yarn build` |
| DEV-031 | Done | Agent | frontend | DEV-015 | 統計ビューのヒストグラム表示を読みやすくする | 長いラベルや少数項目でも崩れない | `yarn build` |
| DEV-032 | Done | Agent | data | DEV-017 | 動画サムネイルのフォールバック候補を見直す | ニコニコ/YouTubeのサムネイル表示失敗が減る | `tests.test_video_metadata`, `tests.test_detail_extraction` |
| DEV-033 | Done | Agent | docs | DEV-026 | ユーザー向けの機能説明を短く改善する | README冒頭で何ができるかすぐ分かる | README冒頭を開発・個人運用向けに更新 |
| DEV-034 | Done | Agent | process | none | 品質改善タスクの棚卸し周期を決める | backlogを見直す頻度と削除基準が書かれる | [quality-gates.md](quality-gates.md#backlog-review) |
| DEV-035 | Done | Human | product | none | 優先したい利用シーンを選ぶ | CLI中心、Web UI中心、公開サイト中心のどれを優先するか決まる | 公開サイト運用中心 + Web UI重視を [production.md](production.md#product-priority) に記録 |
| DEV-041 | Done | Agent | docs | DEV-033 | READMEからユーザー向け宣伝色のある表現をさらに削る | READMEが開発者・運用者向け入口として短く読める | README `What It Does`, privacy scan |
| DEV-042 | Done | Agent | frontend | DEV-024 | OGPやSNS向けmetadataを増やさないことを検査する | 検索流入やSNS流入を増やすmetadataを意図せず追加しない | `tools/check_frontend_metadata.py` |

## Human Decisions

| ID | Status | Decision | Needed by | Notes |
| --- | --- | --- | --- | --- |
| HD-001 | Done | 品質指標の合格ラインを決める | DEV-007 | 初期基準を [quality-gates.md](quality-gates.md) に記録。実測に応じて見直す |
| HD-002 | Done | SEO / クロール方針を決める | DEV-024 | 検索エンジンにはなるべく載せず、負荷増を避ける |
| HD-003 | Done | 優先する利用シーンを決める | DEV-035 | 公開サイト運用中心 + Web UI重視 |
| HD-004 | Done | Cloudflare側の負荷対策レベルを決める | DEV-038 | 標準レベル。Turnstileや強いrate limitは問題発生後に検討 |

## Process Improvement

| ID | Status | Owner | Trigger | Improvement | Done when |
| --- | --- | --- | --- | --- | --- |
| PI-001 | Done | Agent | E2E導入 | E2Eを毎回実行するか、release前だけにするか決める | [quality-gates.md](quality-gates.md#e2e-policy) に反映済み |
| PI-002 | Done | Agent | DB品質検査導入 | DB更新からD1投入までの品質ゲートを標準化する | `validate_db`, `tools/update_d1.sh`, [quality-gates.md](quality-gates.md) に反映済み |
| PI-003 | Done | Shared | 品質指標策定 | 人間判断が必要な品質基準を定期的に見直す | [quality-gates.md](quality-gates.md#review-cadence) と backlog review に反映済み |

## Done Deletion Criteria

`Done` タスクは、変更内容が安定し、正本文書、テスト、または実装から追えるようになったら削除して構いません。

削除前に確認すること:

- 後続タスクの `Depends on` に残っていない
- 完了理由が backlog にしか残っていない状態ではない
- Human decision の根拠になっている場合は、判断内容が正本文書へ移っている
- 実装済みの内容が tests / docs / scripts のどこで検証されるか分かる
- 削除してもIDを再利用しない
