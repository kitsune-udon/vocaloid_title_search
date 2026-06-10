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
| SQLite DB が公開投入できる状態 | `python -m vocaloid_title_search.cli.validate_db` | metadata、詳細件数、JSON破損、schema versionを直す |
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
| 詳細JSON | 破損が0件 |
| 作曲者派生テーブル | 空でない |
| 公開年 | 空でない |

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
| ヘッダー | アプリ名、説明、ビュー切替が縦に伸びすぎない |
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
