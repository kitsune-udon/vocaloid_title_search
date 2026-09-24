# Quality Gates

この文書は、開発・D1投入・production反映の前に見る品質基準をまとめます。数値は現時点の運用基準です。実測と利用状況に応じて見直します。

## When To Check

| タイミング | 必須確認 |
| --- | --- |
| Pull request前 | `tools/check_all.sh` |
| ドキュメントだけの変更後 | `tools/check_docs.sh`, 必要なら `(cd docs-site && yarn build)` |
| SQLite DB更新後 | `validate_db`, 必要なら `report_detail_quality` |
| staging D1投入後 | `/health`, 代表検索, 統計, 代表曲詳細 |
| production反映前 | staging確認結果、変更対象、rollback手順 |
| 障害対応後 | 原因、再発防止、backlog更新 |

## Baseline Commands

```bash
tools/check_all.sh
tools/check_docs.sh
(cd docs-site && yarn build)
(cd frontend && yarn test:e2e)
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.validate_db
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.report_detail_quality --limit 20
tools/update_d1.sh --env staging --dry-run
tools/deploy_cloudflare.sh --env staging --dry-run
```

`validate_db` は合格必須です。`report_detail_quality` はレビュー用なので、欠損候補があるだけでは失敗扱いにしません。

`tools/check_all.sh` が失敗した場合は、最初に表示されたセクション名で切り分けます。`tools/check_docs.sh` はドキュメントだけを直したときの入口です。`yarn test:e2e` は通常チェックとは分け、UI変更時やrelease前に実行します。

| 失敗した領域 | 単独確認 | 主な修正先 |
| --- | --- | --- |
| shell syntax | `bash -n <script>` | `tools/*.sh` |
| Python compile / tests | `uv run --cache-dir .uv-cache python -m unittest` | `vocaloid_title_search/`, `tests/` |
| Worker typecheck / tests | `(cd cloudflare/worker && yarn typecheck && yarn test)` | `cloudflare/worker/`, `shared/` |
| frontend build | `(cd frontend && yarn build)` | `frontend/src/`, `frontend/index.html` |
| frontend E2E | `(cd frontend && yarn test:e2e)` | `frontend/src/`, `frontend/tests/e2e/` |
| docs check | `tools/check_docs.sh` | `docs/`, `README.md`, `docs-site/` |
| privacy scan | `python3 tools/check_sensitive_values.py` | docs、README、設定例 |

単独確認で原因を絞ってから全体チェックに戻します。複数領域を同時に直した場合は、最後に `tools/check_all.sh` を再実行します。

## Gate Matrix

| 品質基準 | 確認コマンドまたは確認先 | 失敗時の初動 |
| --- | --- | --- |
| Shell / Python / Worker / frontend が壊れていない | `tools/check_all.sh` | 失敗したセクション名から対象領域を直す |
| 追跡ファイルに実値やsecretがない | `python3 tools/check_sensitive_values.py` | 実値をプレースホルダーへ置き換える |
| ドキュメントのリンク・構造が壊れていない | `tools/check_docs.sh`, `(cd docs-site && yarn build)` | リンク先、見出し、サイドバー、配置を直す |
| フロントエンドの基本アクセシビリティが保たれている | `python3 tools/check_frontend_accessibility.py` | aria label、focus-visible、キーボード操作を確認する |
| 検索流入抑制metadataが保たれている | `python3 tools/check_frontend_metadata.py` | `robots.txt`、`noindex`、OGP/Twitter/structured data追加を確認する |
| 基本セキュリティヘッダーが保たれている | `python3 tools/check_frontend_metadata.py`, Worker tests | Pages `_headers` と Worker API response headers を確認する |
| API contract の正本が共有型に寄っている | `python3 tools/check_api_contract_sources.py` | Worker、frontend、docsが `shared/api-types.ts` を参照する形へ戻す |
| SQLite DB が公開投入できる状態 | `python -m vocaloid_title_search.cli.validate_db --require-video-metadata` | metadata、詳細件数、JSON破損、schema versionを直す |
| 詳細抽出の品質候補を把握している | `python -m vocaloid_title_search.cli.report_detail_quality --limit 20` | 欠損候補を確認し、必要なら抽出改善タスクを追加する |
| D1投入で変更される対象が分かる | `tools/update_d1.sh --env staging --dry-run` | database name、SQL path、public URLを確認する |
| Pages / Worker deploy対象が分かる | `tools/deploy_cloudflare.sh --env staging --dry-run` | Pages project、Worker env、smoke test対象URLを確認する |
| 公開経路で主要APIが使える | `python3 tools/check_worker_api.py --base-url <public-url>` | `/health`、Worker route、D1 binding、D1データを切り分ける |

## Database Quality

| 指標 | 合格ライン |
| --- | --- |
| `songs` | 0ではない |
| `song_details` | `songs` と同数 |
| `metadata.schema_version` | 実装が期待する値と一致 |
| `metadata.detail_schema_version` | 実装が期待する値と一致 |
| `metadata.song_count` | `songs` 件数と一致 |
| `metadata.detail_count` | `song_details` 件数と一致 |
| 詳細JSON | 破損・object以外・型不正が0件。公開用は全必須フィールドを持つ |
| 検索用派生値 | 詳細JSONの作曲者と公開年に一致する |
| 公開用動画補完 | 対象のある両サービスで取得成功率80%以上、集計件数と動画IDが一致 |
| 作曲者派生テーブル | 空でない |
| 公開年 | 空でない |

前回DBと比較する場合、曲数・作曲者あり件数・公開年あり件数・各サービスの動画ID数が20%を超えて減少すると停止します。作曲者・公開年の充足率、記録のある動画取得成功率が10ポイントを超えて低下しても停止します。新規曲の増加で欠損が隠れることを防ぐため、絶対件数と率を別々に見ます。

これは初期の運用基準です。削除・非公開動画を考慮して100%成功は要求しません。保持した旧動画情報は `retained` として記録し、今回の取得成功に加算しません。失敗した場合は比較レポートと抽出元を確認し、正常なデータ変更と確認できた場合に `QualityPolicy` の基準をテスト・文書と一緒に変更します。`validate_db` 単独の閾値オプションは調査用で、D1投入wrapperの検査基準を迂回しません。

`build_db` は既存ローカルDB、`update_d1.sh` は投入先から取得した直前DBを比較元とします。初回の空D1では比較のみを省略し、単体品質検査と空状態への復旧確認は行います。

## API Quality

| API | 合格ライン |
| --- | --- |
| `/health` | `200`, `{"ok":true,"database_ready":true}` |
| `/api/metadata` | `200`, schemaと件数metadataを返す |
| `/api/search` | 代表条件で `200`、`total` と `results` を返す |
| `/api/stats` | `200`、総曲数・詳細件数・分布を返す |
| `/api/song-detail` | 代表曲で `200`、未登録URLで `404` |

検索条件エラーは `400`、DB未準備は `503`、未知routeは `404` として区別します。

## Performance Budget

| 対象 | 目安 |
| --- | ---: |
| frontend production JS gzip | 50 KB以下を維持目標 |
| frontend production CSS gzip | 8 KB以下を維持目標 |
| `/api/search` 代表条件 | 体感で待たされないこと。遅延を感じたら計測タスクを追加 |
| `/api/stats` | 統計ビュー表示時に待たされないこと。遅延を感じたら集計見直し |
| 詳細アコーディオン | 取得中表示が自然に見えること |

現時点では厳密なSLOではなく、肥大化や明確な体感劣化を早期に見つけるための予算です。

## Review Cadence

品質基準は固定値ではありません。次のタイミングで見直します。

| タイミング | 見直すもの |
| --- | --- |
| 大きなUI変更後 | frontend bundle size、モバイル確認観点、アクセシビリティ |
| DB schema変更後 | `validate_db` の検査項目、metadata、D1投入前チェック |
| Worker API変更後 | API error contract、smoke test、Worker tests |
| production障害後 | readiness判定、rollback手順、運用チェックリスト |
| 利用者から遅さを指摘された後 | API処理時間、stats集計、詳細アコーディオン表示 |

見直しで基準を変えた場合は、この文書と関連テスト・運用文書を同じ変更で更新します。

## Frontend UX

| 観点 | 合格ライン |
| --- | --- |
| 初期表示 | 検索実行前の状態が自然で、結果が勝手に表示されない |
| 検索条件 | 文字数・作曲者・公開年を独立して指定できる |
| ページング | 50 / 100 / 200 を選べ、現在ページが分かる |
| 表示項目 | 結果カードの情報量を調整できる |
| モバイル | 検索・統計・ページング操作が画面を占有しすぎない |
| アクセシビリティ | キーボード操作と支援技術向けラベルを壊さない |

モバイル確認観点:

| 領域 | 確認すること |
| --- | --- |
| 上端固定欄 | 検索条件の見出し、検索／統計切替、開閉操作が重ならない |
| 検索条件 | 開閉ボタンが見つけやすく、入力欄が不自然に狭くない |
| 結果カード | 曲名、Wikiリンク、開閉操作、表示項目が読みやすい |
| 詳細アコーディオン | 読み込み中、空状態、エラー状態がカード内で破綻しない |
| 下部バー | ページ移動、表示件数、表示項目が画面を占有しすぎない |
| 統計ビュー | カテゴリ切替とスワイプ操作が分かりやすい |
| 画面遷移 | 検索ビューと統計ビューの切替後、スクロール位置が不自然でない |

## E2E Policy

`tools/check_all.sh` は、通常開発で頻繁に実行できる軽量な品質ゲートとして保ちます。Playwright E2E は導入済みですが、現時点では独立コマンドとして扱います。

昇格の目安:

| 条件 | 判断 |
| --- | --- |
| 実行時間が通常の開発ループを大きく妨げない | `check_all` へ含める候補にする |
| 外部ネットワークや実Cloudflare環境に依存しない | 昇格条件を満たしやすい |
| API mockだけで主要導線を確認できる | 昇格条件を満たしやすい |
| 失敗時のtraceやerror contextを見れば原因を追える | CI候補にできる |
| CIでPlaywright Chromiumを安定して用意できる | CIの通常check候補にできる |
| スクリーンショット差分が環境差で揺れやすい | release前または手動確認に分ける |
| デプロイ済みURLのsmoke確認が必要 | deploy scriptまたは運用手順に置く |

現時点の運用:

| コマンド | 使うタイミング |
| --- | --- |
| `tools/check_all.sh` | 通常開発、commit前、軽量な全体確認 |
| `(cd frontend && yarn test:e2e)` | UI変更時、release前、検索/統計/詳細/ページングに触れた時 |

初期E2Eで優先するシナリオ:

- 未検索状態から検索して結果が表示される
- 統計ビューから検索条件を適用できる
- 詳細アコーディオンを開き、読み込み・成功・失敗状態が破綻しない
- ページングと表示件数変更が動く
- モバイル幅で主要操作が画面外に消えない

## Backlog Review

週1回、または大きな機能追加・大きなドキュメント整理の後に、[development-backlog.md](development-backlog.md) と [documentation-improvement-backlog.md](documentation-improvement-backlog.md) を見直します。

見直すこと:

- `Done` が溜まりすぎていないか
- 依存関係が古くなっていないか
- Human decision が開発を止めていないか
- 実装済みの内容が docs / tests に反映されているか
- 新しい品質問題がタスク化されているか
- ドキュメントだけで完了する改善が development backlog に混ざっていないか
- コード変更が必要な改善が documentation backlog に混ざっていないか

完了済みタスクは、変更内容が安定し、関連ドキュメントから参照できるようになったら削除して構いません。

## Completion Audit

大きな最適化作業は、全領域を点検し、重大な既知問題の解消、現行機能とUI方針の維持、同一条件での改善測定、最終コードの検証、残課題の分類を終えた時点で閉じます。時間の消費や改善案の数は終了判定にしません。

対象と証拠は [開発backlogの監査表](development-backlog.md#completion-audit) に記録します。commit・push・本番適用を含むかも最初に明示します。リリースの承認とstaging・production確認はこのローカル完了判定とは別です。


完了は未証明として、各受入条件に最終状態の直接証拠と確認限界を対応付けます。テスト件数、Done表記、実装したという説明だけでは終了しません。実装後には、入力境界、欠損、通信失敗、中断、再試行、競合、互換性、復旧から反証を試み、既存テスト自体が誤った前提を固定していないか確認します。発見した問題の修正後は影響範囲を再検証し、未検証・失敗・権限不足を成功に読み替えません。終了条件と証拠の照合が済むまで監査を閉じません。


## Machine Completion Records

継続監査の受入条件と個別課題は `docs/completion/ledger.json`、登録済み定義は `docs/completion/registry.json` に保持します。これらの監査項目は解決後も削除せず、解決理由と証拠を残します。検証はプロジェクトのPythonとNode環境で次の記録器から実行します。

```bash
python tools/completion_gate.py run --id all
python tools/completion_gate.py check
python tools/completion_gate.py check --format json
```

`run`は登録コマンドの実行環境、開始終了時刻、終了コード、ログとハッシュ、実行前後のソース・入力fingerprintを `release/completion/` に保存します。`check`は全必須検証、証拠、未解決状態を照合し、不足があれば非ゼロ終了します。ソース変更後は過去の成功をそのまま再利用しません。

クレジットの個別原文照合は `docs/completion/credit-reviews.json` に期待値・原文ハッシュ・判定理由を保存します。`credit-reviewed` はそこに記録済みの項目だけを検証し、`credit-coverage` は台帳にある全クレジット候補の網羅も要求します。一部の照合成功を全件確認済みと扱ってはいけません。`credit-atomic-names`は確認済みの単一リンク人名を根拠に、候補DB全曲の全役割で既知の名前断片が残っていないか検査します。これは未確認の全人名の正しさを証明するものではありません。

```bash
python tools/completion_gate.py run --id credit-reviewed
python tools/completion_gate.py run --id credit-coverage
python tools/completion_gate.py run --id credit-atomic-names
```

候補DBの照合は更新前コピーと比較し、レビュー対象外の値、動画メタデータ、紹介文、曲一覧、更新日時の保持と、作曲者派生表の整合性を検証します。原文HTMLと候補DBはローカルの生成物です。不在・変更・期待値の欠落は成功ではありません。


各残件の `acceptance`（合格基準）と `verification`（検証方法）、`next_action` を必須にします。成功した検証でも、その `requirements` に対象要求が含まれなければ証拠には使えません。複数要求に属する残件は全要求を証拠で覆う必要があります。実行時の関連IDと現在の台帳の関連IDも照合し、追加した項目を古い実行記録で検証済みにはしません。子コマンドが終了コード0でも、Python・Node・Playwright/pytestの明示的な失敗サマリーを拒否します。Nodeのspec reporterを含む既知のテスト出力で0件・skip・todoも拒否しますが、任意の独自スクリプトの出力から検証内容を証明するものではありません。独自検証は対象件数と独立した期待値を明示的に検査します。
