# Documentation Improvement Backlog

この文書は、ドキュメントだけで完結する改善タスクを管理する場所です。コード、API、UI、運用ツールの変更を伴うものは [development-backlog.md](development-backlog.md) に置きます。

## How To Use

- 完了したタスクは `Done` にして、必要なら後で削除します。
- 依存関係があるタスクは `Depends on` にタスクIDを書きます。
- 人間の判断や外部作業が必要な場合は `Owner` を `Human` または `Shared` にします。
- ドキュメント改善サイクル自体の改善は `Process Improvement` に追加します。
- 秘匿情報や実ドメインは書かず、[repository-privacy.md](repository-privacy.md) に従います。
- 品質基準は [documentation-quality.md](documentation-quality.md) を正本にします。

## Task Template

| Field | Value |
| --- | --- |
| ID | `DOC-000` |
| Status | `Open` |
| Priority | `High` / `Medium` / `Low` |
| Owner | `Agent` / `Human` / `Shared` |
| Area | onboarding / operations / data / api / frontend / infrastructure / quality / process |
| Documents | target docs or `multiple` |
| Depends on | task IDs or `none` |
| Decision needed | human decision or `none` |
| Task | concise action |
| Acceptance | observable completion condition |
| Verification | review checklist, commands, link check, or human review |

## Status Values

| Status | Meaning |
| --- | --- |
| `Open` | 未着手 |
| `Ready` | 依存関係がなく、すぐ作業できる |
| `Blocked` | 外部情報、人間判断、別タスク完了が必要 |
| `Done` | Acceptance と Verification を満たした |

## ID Rules

- 通常タスクは `DOC-001` から連番にします。
- Human decision は `DH-001` から連番にします。
- Process improvement は `DPI-001` から連番にします。
- 新規タスクを追加するときは、この文書内の最大番号を確認し、次の番号を使います。
- 既存IDは再利用しません。削除済みタスクの番号も再利用しません。
- 依存関係を書く場合は、`Depends on` に `DOC-001` のようなIDだけを書きます。説明は `Task` または `Acceptance` に書きます。

## Backlog Split Examples

| 例 | 置く場所 | 理由 |
| --- | --- | --- |
| `operations.md のrollback説明を短くする` | Documentation backlog | tracked docsだけで完了する |
| `READMEの導線を整理する` | Documentation backlog | 文書構成の変更だけで完了する |
| `deploy scriptにsmoke testを追加する` | Development backlog | tool codeの変更を伴う |
| `API error responseを変更する` | Development backlog | Worker実装とテストが必要 |
| `SEO方針を決める` | Human Decisions | プロダクト判断が必要 |

迷った場合は、コードやツールの変更が必要なら development backlog、文書だけなら documentation backlog に置きます。

## High

| ID | Status | Owner | Area | Documents | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | Done | Agent | onboarding | README.md, docs/README.md, docs/usage.md | none | 初回読者向けの最短ルートを再点検する | READMEからローカル起動、DB構築、Cloudflare運用の入口へ迷わず進める | documentation checklist, privacy scan |
| DOC-002 | Done | Agent | operations | docs/operations.md, docs/quality-gates.md | none | production前チェックとrollback確認の重複・抜けを整理する | production前に見る項目、失敗時の初動、rollback確認が一貫している | documentation checklist |
| DOC-003 | Done | Agent | infrastructure | docs/infrastructure.md, docs/cloudflare-dns.md, docs/cloudflare-serverless.md | none | Cloudflare Pages / Worker / D1 / DNS の責務境界を読み比べて矛盾をなくす | 各文書で同じ操作を別名で説明していない | documentation checklist, term search |
| DOC-004 | Done | Agent | quality | docs/quality-gates.md, docs/testing.md | none | 品質ゲートとテスト手順の対応表を追加する | どの品質基準をどのコマンドで確認するか分かる | documentation checklist |
| DOC-005 | Done | Agent | privacy | docs/repository-privacy.md, AGENTS.md | none | 秘匿情報を書かないための判断例を増やす | 実ドメイン、token、Cloudflare ID、ローカル設定の扱いが例で分かる | privacy scan, documentation checklist |
| DOC-026 | Done | Agent | onboarding | README.md, docs/README.md | none | 開発者・個人運用者向けの最短導線を再整理する | READMEから「開発する」「DBを更新する」「stagingへ確認する」「productionへdeployまたはD1投入する」へ迷わず進める | README Quick Start, docs Fast Routes, privacy scan |
| DOC-027 | Done | Agent | operations | docs/production.md, docs/operations.md | none | 検索流入抑制と負荷対策の関係を整理する | `robots.txt` / `noindex` / Cloudflare防御 / rate limit の役割差が分かる | production Search Engine Policy, documentation checklist |
| DOC-028 | Done | Agent | infrastructure | docs/infrastructure.md, docs/cloudflare-serverless.md, docs/cloudflare-dns.md | none | staging / production のCloudflare構成を個人運用前提で再点検する | Pages, Worker, D1, custom domain, DNS のproduction/staging差分が1か所から追える | cloudflare-serverless Environment Matrix, privacy scan |
| DOC-029 | Done | Agent | operations | docs/operations.md, docs/quality-gates.md | none | production前チェックを個人運用で実行しやすい順序に並べ直す | 事前確認、deploy、smoke、rollback判断が時系列で分かる | operations First Five Minutes / readiness checklist |
| DOC-030 | Done | Agent | privacy | docs/repository-privacy.md, docs/production.md | none | 公開サイトに載せない情報とリポジトリに書かない情報を分けて説明する | SEO抑制、秘匿情報、公開してよいプレースホルダーの違いが分かる | repository privacy comparison, privacy scan |
| DOC-051 | Done | Agent | quality | docs/testing.md, docs/quality-gates.md | none | Playwright E2E smokeの位置づけを追加する | `yarn test:e2e`、初回Chromium導入、通常checkから分ける理由が分かる | testing Frontend E2E, quality-gates |
| DOC-052 | Done | Shared | operations | docs/production.md | DH-004, DH-005 | 公開サイト運用中心 + Web UI重視とCloudflare標準負荷対策を文書化する | 優先軸と低コスト防御レベルがproduction設計から追える | production Product Priority / Low-Cost Traffic Protection |
| DOC-053 | Done | Agent | onboarding | docs/README.md | DOC-051 | E2E導入後の読む順番をdocs入口に反映する | UI変更時やrelease前に `testing.md#frontend-e2e` へ迷わず到達できる | docs README Fast Routes / By Task |
| DOC-060 | Done | Agent | onboarding | docs/README.md, README.md | DEV-043 | Docsプレビューの入口をREADME群に追加する | ローカルでドキュメントを読む最短コマンドと、Markdown直読みとの使い分けが分かる | README Documentation / docs Fast Routes |
| DOC-061 | Done | Agent | quality | docs/documentation-quality.md | DEV-043 | Docsサイトで読みやすくするためのMarkdownルールを追加する | サイドバー、見出し階層、ページタイトル、短い導入文の基準がある | [documentation-quality.md](documentation-quality.md#docs-site) |

## Medium

| ID | Status | Owner | Area | Documents | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-006 | Done | Agent | data | docs/data-model.md, docs/detail-extraction.md, docs/cli-reference.md | DOC-004 | DB品質検査と詳細品質レポートの使い分けを整理する | `validate_db` と `report_detail_quality` の目的差が明確 | documentation checklist |
| DOC-007 | Done | Agent | api | docs/web-api.md, docs/frontend-ui.md | DOC-004 | API error contract とフロント表示方針の対応を整理する | 400/404/503/network error の扱いが文書間で一致 | documentation checklist |
| DOC-008 | Done | Agent | operations | docs/operations.md, docs/testing.md | DOC-002 | smoke test の範囲と限界を整理する | smoke test が保証すること・しないことが運用手順から分かる | documentation checklist |
| DOC-009 | Done | Agent | infrastructure | docs/infrastructure.md | DOC-003 | Terraform import / apply / D1投入の違いを短い比較表にする | 初見読者が3つの操作を取り違えない | documentation checklist |
| DOC-010 | Done | Agent | frontend | docs/frontend-ui.md, docs/quality-gates.md | none | モバイルUI確認観点をチェックリスト化する | 検索条件、結果カード、下部バー、統計ビューの確認観点がある | documentation checklist |
| DOC-011 | Done | Agent | process | docs/development-backlog.md, docs/documentation-improvement-backlog.md | none | 開発backlogとドキュメントbacklogの使い分け例を追加する | 迷いやすい例を見てどちらへ積むか判断できる | documentation checklist |
| DOC-012 | Done | Agent | operations | docs/operations.md, docs/production.md | DOC-002 | staging確認からproduction反映までの時系列を1本化する | deploy、D1投入、Terraform変更の順序が混線しない | documentation checklist |
| DOC-013 | Done | Agent | data | docs/detail-extraction-algorithm.md | DOC-006 | 詳細抽出アルゴリズム文書の長い節を読者目的別に分割する | 調査したい抽出対象へ見出しから到達しやすい | documentation checklist |
| DOC-014 | Done | Agent | api | docs/web-api.md | DOC-007 | API query parameter のvalidation例を表にまとめる | parameterごとに正常例・エラー例・statusが分かる | documentation checklist |
| DOC-015 | Done | Agent | onboarding | docs/usage.md | DOC-001 | local D1 が必要な場面と不要な場面を冒頭で明確化する | CLIだけ、Web UI、Worker確認の違いが分かる | documentation checklist |
| DOC-031 | Done | Agent | data | docs/data-model.md, docs/detail-extraction.md | none | SQLite生成物とD1投入物の責務境界を読みやすくする | Python側のDB生成、D1用SQL export、Workerからのreadの流れが分かる | data-model responsibility table |
| DOC-032 | Done | Agent | api | docs/web-api.md, docs/frontend-ui.md | none | API仕様とフロント表示の対応を再点検する | search/detail/stats/video metadata の表示先とエラー表示が対応している | web-api UI Mapping |
| DOC-033 | Done | Agent | frontend | docs/frontend-ui.md | none | 検索ビューと統計ビューの状態遷移を図解テキストで補足する | 統計から検索へ移るときの条件初期化とページングが分かる | frontend-ui state flow |
| DOC-034 | Done | Agent | quality | docs/testing.md, docs/quality-gates.md | none | `check_all.sh` の内訳と失敗時の切り分けを補足する | どの失敗がPython/Worker/frontend/docsのどこに属するか分かる | quality-gates failure table |
| DOC-035 | Done | Agent | infrastructure | docs/infrastructure.md | none | Terraform管理対象とWrangler操作対象の境界を再整理する | Terraformで管理するもの、Wranglerでdeploy/投入するもの、手動判断が必要なものが分かる | infrastructure Terraform / Wrangler boundary |
| DOC-036 | Done | Agent | operations | docs/operations.md | none | staging確認を省略してよい変更・省略しない変更の基準を作る | 個人運用でもproduction前に迷いにくい判断表がある | operations staging criteria |
| DOC-037 | Done | Agent | process | docs/development-backlog.md, docs/documentation-improvement-backlog.md | none | backlogの棚卸し時にDoneを削除する判断基準を改善する | Done削除後も正本文書から変更理由を追える基準がある | documentation backlog Done deletion criteria |
| DOC-038 | Done | Agent | onboarding | docs/usage.md, docs/cli-reference.md | none | ローカル開発サーバー起動手順とD1有無の関係を再整理する | 初回開発時に必要なコマンドと不要な準備が分かる | usage Local Dev Server decision table |
| DOC-039 | Done | Agent | data | docs/detail-extraction-algorithm.md, docs/detail-extraction.md | none | 詳細抽出の失敗例と調査手順を簡潔にまとめる | 作曲者や動画項目がおかしいときの確認先が分かる | detail-extraction Investigation Flow |
| DOC-040 | Done | Agent | api | docs/web-api.md | none | API response examples の網羅性を上げる | 空結果、validation error、DB未投入、metadataなしの例がある | web-api empty / not-ready examples |
| DOC-054 | Done | Agent | onboarding | README.md | DOC-051 | READMEのテスト導線にE2Eを追加する | `tools/check_all.sh` と `yarn test:e2e` の使い分けがREADMEから分かる | README Checks |
| DOC-055 | Done | Agent | infrastructure | docs/project-structure.md | DOC-051 | Playwright関連ファイルと生成物の配置をproject structureに反映する | `frontend/playwright.config.ts`, `frontend/tests/e2e`, `frontend/test-results` の扱いが分かる | project-structure frontend / generated files |
| DOC-056 | Done | Agent | operations | docs/operations.md, docs/cloudflare-serverless.md | DOC-052 | Cloudflare標準負荷対策の運用確認先を日常運用へ接続する | WAF/bot/rate limit/logsをどの文書で確認するか分かる | operations Traffic Protection Checks / cloudflare-serverless |
| DOC-057 | Done | Agent | quality | docs/quality-gates.md | DOC-051 | E2Eを通常checkへ昇格する条件をより具体化する | 実行時間、安定性、CI有無、スクリーンショット有無の判断基準がある | quality-gates E2E Policy |
| DOC-062 | Done | Agent | quality | docs/testing.md, docs/quality-gates.md | DEV-044 | docs専用チェックの実行タイミングを文書化する | `tools/check_docs.sh` と `tools/check_all.sh` の役割差が分かる | [testing.md](testing.md#documentation-checks), [quality-gates.md](quality-gates.md) |
| DOC-063 | Done | Agent | process | docs/documentation-improvement-backlog.md | DEV-044 | docsチェックで見つけた問題をbacklogへ積む基準を追加する | リンク切れ、孤立文書、重複説明、見出し問題をどうタスク化するか分かる | Triage Rules更新 |

## Low

| ID | Status | Owner | Area | Documents | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-016 | Done | Agent | onboarding | README.md | DOC-001 | README冒頭の機能説明をさらに短くする | 初見で何ができるプロジェクトか3行以内で分かる | documentation checklist |
| DOC-017 | Done | Agent | quality | docs/documentation-quality.md | none | よい見出し・悪い見出しの例を増やす | セクション名レビュー時に参照できる例がある | documentation checklist |
| DOC-018 | Done | Agent | quality | docs/documentation-quality.md | none | 自然な日本語の推敲例を追加する | 硬すぎる文、冗長な文、曖昧な文の改善例がある | documentation checklist |
| DOC-019 | Done | Agent | operations | docs/operations.md | DOC-008 | よく見るログと次の確認先の表を短くする | 障害時に表が長すぎず、初動に使いやすい | documentation checklist |
| DOC-020 | Done | Agent | infrastructure | docs/cloudflare-dns.md | DOC-003 | DNS Proxy mode の期待状態を図解テキストで補足する | proxied CNAME と Worker route の関係を文章だけで追える | documentation checklist |
| DOC-021 | Done | Agent | data | docs/data-model.md | DOC-006 | schema version 更新時のドキュメント更新箇所を明記する | schema変更時に更新する文書・テストが分かる | documentation checklist |
| DOC-022 | Done | Agent | frontend | docs/frontend-ui.md | DOC-010 | 統計ビューから検索ビューへ移動する時の状態管理説明を追加する | 統計由来条件と通常検索条件の扱いが分かる | documentation checklist |
| DOC-023 | Done | Agent | api | docs/web-api.md | DOC-014 | API response examples の実データらしさと匿名性を両立する | 例が分かりやすく、実ドメインや実IDに依存しない | privacy scan, documentation checklist |
| DOC-024 | Done | Agent | process | docs/documentation-improvement-backlog.md | none | ドキュメントbacklogのID採番ルールを明記する | 新規タスク追加時にID重複を避けられる | documentation checklist |
| DOC-025 | Done | Agent | quality | docs/quality-gates.md | none | 品質ゲートの数値を見直すタイミングを追記する | いつ性能予算や基準を更新するか分かる | documentation checklist |
| DOC-041 | Done | Agent | quality | docs/documentation-quality.md | none | 「短く書く」と「背景を残す」のバランス基準を追加する | 文脈不足と冗長さのどちらも避ける判断例がある | documentation-quality Context Density |
| DOC-042 | Done | Agent | quality | docs/documentation-quality.md | none | セクション名の改善例をプロジェクト文書から追加する | 実際の文書名に近いよい例・悪い例がある | documentation-quality section name examples |
| DOC-043 | Done | Agent | onboarding | README.md | DOC-026 | READMEの導入文を個人運用前提でさらに自然にする | 宣伝文ではなく開発・運用の入口として読める | README opening paragraph |
| DOC-044 | Done | Agent | frontend | docs/frontend-ui.md | none | UI用語の表記揺れを整理する | 検索条件、表示項目、統計、カード、詳細の呼び方が揃う | frontend-ui label / API mapping |
| DOC-045 | Done | Agent | data | docs/data-model.md | none | DBテーブル説明に「誰が書くか」「誰が読むか」を追加する | songs/details/video metadata/statistics のwriter/readerが分かる | data-model writer / reader tables |
| DOC-046 | Done | Agent | operations | docs/operations.md | none | 障害時の最初の5分で見る場所を短いリストにする | 個人運用で慌てたときに最小限の確認先が分かる | operations First Five Minutes |
| DOC-047 | Done | Agent | infrastructure | docs/cloudflare-dns.md | DOC-027 | Proxy modeの説明を検索流入抑制方針と矛盾しない形に調整する | Proxy modeがSEO対策ではなくorigin保護・観測のためだと分かる | cloudflare-dns Proxy role table |
| DOC-048 | Done | Agent | process | AGENTS.md, docs/documentation-quality.md | none | Agent向けドキュメント編集ルールの重複を減らす | AGENTS.mdは入口、詳細はdocsへ分離されている | AGENTS privacy rule references canonical docs |
| DOC-049 | Done | Agent | quality | docs/README.md | none | docs配下の読む順番を目的別に再分類する | 開発、運用、Cloudflare、データ、品質の入口が分かる | docs Fast Routes |
| DOC-050 | Done | Agent | quality | multiple | none | 文書内の古い表現・曖昧語を棚卸しする | 「必要に応じて」「適切に」などが具体化できる箇所を修正またはタスク化する | term search, concrete wording updates |
| DOC-058 | Done | Agent | frontend | docs/frontend-ui.md | DOC-051 | E2Eで守るUI導線と手動確認に残すUI観点を分ける | 自動確認対象と目視確認対象の境界が分かる | frontend-ui Testing Boundary |
| DOC-059 | Done | Agent | process | docs/documentation-improvement-backlog.md | none | Doneタスクが増えた後の削除候補を棚卸しする | 正本文書から追えるDoneタスクを削除候補として整理できる | Done Cleanup Candidates |
| DOC-064 | Done | Agent | onboarding | docs/README.md | DEV-043 | Docsプレビュー用サイドバーの並びを目的別にレビューする | VitePressのサイドバーが開発、運用、Cloudflare、データ、品質の流れで読める | docs-site sidebar config, docs Fast Routes |
| DOC-065 | Done | Agent | quality | docs/project-structure.md | DEV-043 | Docsプレビュー関連ファイルの配置をproject structureへ反映する | docs site設定、生成物、依存関係の置き場所が分かる | [project-structure.md](project-structure.md#docs-site) |

## Human Decisions

| ID | Status | Decision | Needed by | Notes |
| --- | --- | --- | --- | --- |
| DH-001 | Done | 公開サイトを検索エンジンに積極的に見せるか | DOC-023 | 検索エンジン流入はなるべく抑制する。`robots.txt` と `noindex,nofollow,noarchive` を使い、SEO最適化は行わない |
| DH-002 | Done | READMEの主読者をCLI利用者、Web UI利用者、運用者のどれに寄せるか | DOC-016 | 開発者と個人運用の保守者に寄せる |
| DH-003 | Done | ドキュメントで扱う運用レベルを個人運用中心にするか、公開サービス運用中心にするか | DOC-002, DOC-012 | 基本は個人運用向け。production操作だけstaging確認、dry-run、smoke test、backupを明確にする |
| DH-004 | Done | 今後の品質改善で優先する利用シーンをどれにするか | DOC-052 | 公開サイト運用中心 + Web UI重視 |
| DH-005 | Done | Cloudflare側の低コスト負荷対策レベルをどこまでにするか | DOC-052 | 標準レベル。Turnstileや強いrate limitは問題発生後に検討 |

## Process Improvement

| ID | Status | Owner | Trigger | Improvement | Done when |
| --- | --- | --- | --- | --- | --- |
| DPI-001 | Done | Agent | ドキュメント改善後 | 完了済みDOCタスクの削除タイミングを決める | Doneタスクを残す期間、削除条件、参照先の正本文書が明文化される |
| DPI-002 | Done | Agent | backlog追加後 | ドキュメントbacklogの週次棚卸し手順を整える | Ready/Open/Blocked/Done を見直す短い手順が書かれる |
| DPI-003 | Done | Agent | 文書間の重複発見時 | 重複説明を正本へ寄せる判断基準を改善する | どちらを残し、どちらをリンクにするか判断できる |
| DPI-004 | Done | Agent | 開発backlog完了後 | 開発backlog完了時にドキュメントbacklogへ反映する手順を明確化する | Review Cycle更新 |

## Review Cycle

週1回、または大きなドキュメント整理の後に見直します。

1. `Ready` のうち、短時間で終わるものを先に処理する。
2. `Open` の依存関係が解消していれば `Ready` にする。
3. `Blocked` は必要な Human decision が残っているか確認する。
4. `Done` は正本文書に内容が残っているか確認する。
5. 新しい重複、古い手順、読者が迷う導線が見つかればタスクを追加する。

開発backlogを大きく更新または完了した後は、次も確認します。

1. 新しいコマンド、テスト、生成物が [testing.md](testing.md) と [project-structure.md](project-structure.md) に反映されているか。
2. 新しいプロダクト判断や運用判断が [production.md](production.md) または [quality-gates.md](quality-gates.md) に移っているか。
3. README と [docs/README.md](README.md) から新しい作業導線へ辿れるか。
4. development backlog にだけ残っている判断理由がないか。
5. documentation backlog に、文書だけで終わる後続改善が積まれているか。

`Done` タスクは、変更内容が正本文書から追え、次の棚卸しで参照不要と判断できたら削除して構いません。削除してもIDは再利用しません。

## Done Cleanup Candidates

Doneタスクが増えた場合は、次の順で削除候補を見ます。

| 候補 | 判断 |
| --- | --- |
| `DOC-001` から `DOC-025` | 初期整理の内容が正本文書へ移っているため、次の棚卸しで削除候補 |
| `DOC-026` から `DOC-050` | 直近の大きな文書整理の履歴としてしばらく残す |
| Human decision | 判断が [production.md](production.md), [repository-privacy.md](repository-privacy.md), [quality-gates.md](quality-gates.md) へ移っていれば削除候補 |
| Process improvement | Review Cycle / Deduplication Rule / Triage Rules に反映済みなら削除候補 |

削除は、同じ変更で正本文書のリンクや説明が失われないことを確認してから行います。削除したIDは再利用しません。

Done削除の判断:

| 状況 | 削除してよいか |
| --- | --- |
| 変更内容が正本文書に残り、関連リンクから辿れる | はい |
| 完了理由がbacklogにしか残っていない | まだ残す |
| 後続タスクの依存先になっている | 後続が完了するまで残す |
| Human decision の根拠になっている | 判断が正本文書へ移るまで残す |
| 同じ領域の新規タスクを積むときに参照が必要 | 棚卸し後に判断する |

削除前に、正本文書、関連テストや手順、必要なら [development-backlog.md](development-backlog.md) に変更理由が残っているか確認します。Doneを削除しても、IDは再利用しません。

## Deduplication Rule

同じ説明が複数文書にある場合は、次の順で整理します。

1. 正本にする文書を [docs/README.md](README.md) の Document Boundaries で確認する。
2. 正本文書には判断理由と手順の本体を残す。
3. 他の文書には短い要約と正本文書へのリンクだけを残す。
4. コマンド例が複数文書に必要な場合は、同じ意味のコマンドに揃える。
5. 正本を決められない場合は、先に documentation backlog に整理タスクを追加する。

## Triage Rules

ドキュメントタスクを追加するときは、次の順で分類します。

1. 読者が作業を進められない、誤操作しやすい、秘匿情報を書き込みやすい問題は `High`。
2. 既存情報はあるが探しにくい、重複している、表現が揺れている問題は `Medium`。
3. 読みやすさ、例の追加、文章の自然さの改善は `Low`。

`Owner` の判断:

- `Agent`: tracked docsだけで完了し、検証もローカルでできる。
- `Human`: 実アカウント、実ドメイン、プロダクト判断、公開可否判断が必要。
- `Shared`: Agentが文案を作り、人間が判断する。

docsチェックで見つけた問題の積み方:

| 問題 | 優先度 | Task化の目安 |
| --- | --- | --- |
| 秘匿情報スキャン失敗 | High | すぐ修正する。実値を残す判断はしない |
| リンク切れ | High | 正本へのリンクを直す。リンク先が未作成なら文書追加タスクにする |
| 孤立文書 | Medium | 入口から辿る必要がある文書なら `docs/README.md` または関連文書へリンクする |
| 見出し重複 | Medium | セクションの責務が重なっていないか確認し、見出し名または構造を直す |
| VitePress build失敗 | Medium | Markdownとして正しくてもブラウザ閲覧を壊す場合は修正する |
| 表の折り返しやサイドバーの違和感 | Low | 読みにくさが作業判断に影響するならMediumへ上げる |

## Verification Checklist

ドキュメントタスクを `Done` にする前に確認します。

- 対象読者と目的が分かる
- どの文書が正本か分かる
- 同じ手順を複数文書へ重複していない
- 実ドメイン、実IP、ユーザー名、メールアドレス、Cloudflare ID、tokenを書いていない
- コマンド例は現在のツール構成と一致している
- 見出しが内容を正しく表している
- 日本語が自然で、機械翻訳調や過度に硬い表現になっていない
- 必要な関連文書へリンクしている
- [documentation-quality.md](documentation-quality.md) のチェック観点に反していない
