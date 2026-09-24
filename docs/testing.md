# Testing

このプロジェクトの自動テストは Python の `unittest` discovery、Worker API の Node test、フロントエンドのPlaywright smoke testに分けています。通常開発では `tools/check_all.sh` を軽量な基本チェックとして使い、ブラウザE2EはUI変更時やrelease前に独立して実行します。

## Run

全体の基本チェック:

```bash
tools/check_all.sh
```

Python unit tests:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --cache-dir .uv-cache python -m unittest
```

Frontend build:

```bash
(cd frontend && yarn build)
```

Frontend E2E smoke:

```bash
(cd frontend && yarn test:e2e)
```

Documentation checks:

```bash
tools/check_docs.sh
(cd docs-site && yarn build)
```

初回だけPlaywrightのChromiumが必要です。

```bash
(cd frontend && ./node_modules/.bin/playwright install chromium)
```

Worker API typecheck and tests:

```bash
(cd cloudflare/worker && yarn typecheck)
(cd cloudflare/worker && yarn test)
```

`PYTHONDONTWRITEBYTECODE=1` は `tests/__pycache__` などの生成物を残さないための指定です。

## Runtime Expectations

所要時間はマシン性能、依存関係のキャッシュ、Node.js / uv の状態で変わります。目安は次の通りです。

| チェック | 目安 | 内容 |
| --- | ---: | --- |
| shell syntax / Python compile | 1秒未満 | script の構文と Python tool の import 可能性 |
| Python unit tests | 数秒 | SQLite、詳細抽出、HTTP retry、動画メタデータ処理 |
| Worker typecheck / test | 数秒 | TypeScript型検査と Worker API contract |
| Frontend build | 数秒 | Vue型検査と Vite production build |
| Frontend E2E smoke | 数秒から十数秒 | Chromiumで検索、詳細、ページング、統計遷移を確認 |
| Documentation checks | 数秒 | 秘匿情報、docsリンク、見出し重複、孤立文書、VitePress build |
| `tools/check_all.sh` 全体 | 10秒前後 | 上記をまとめて実行 |

依存関係の初回取得やローカル環境の再構築が入る場合は、これより長くなります。長時間止まっているように見える場合は、どのセクション名で止まっているかを確認します。

CIで実行する候補とローカル向けチェック:

| チェック | CI | ローカル |
| --- | --- | --- |
| `tools/check_all.sh` | はい | はい |
| Python unit tests | はい | はい |
| Worker API tests | はい | はい |
| frontend build | はい | はい |
| frontend E2E smoke | release前候補 | UI変更時 |
| documentation checks | はい | docs変更時 |
| `tools/check_worker_api.py` against staging / production | いいえ | deploy後の手動確認 |
| 実DB再構築 | いいえ | データ更新時だけ |

## Documentation Checks

ドキュメントだけを直した場合は、まず `tools/check_docs.sh` を実行します。このコマンドは追跡ファイルの秘匿情報スキャンと、`docs/` 内のMarkdownリンク、アンカー、孤立文書、見出し重複を確認します。

```bash
tools/check_docs.sh
```

ブラウザで読む体験を確認したい場合は、VitePress buildも実行します。

```bash
(cd docs-site && yarn build)
```

`tools/check_all.sh` は通常開発の軽量ゲートとして、秘匿情報スキャンと `tools/check_docs.py` を含みます。`tools/check_docs.sh` はドキュメント作業時に単独で実行しやすい入口です。

## Smoke Test

smoke test は、デプロイ済みまたは起動済みのWorker APIが最低限使える状態かを短時間で確認する疎通確認です。単体テストの代わりではなく、deploy後やD1投入後に「公開経路、Worker route、D1 binding、主要APIレスポンス」がつながっているかを見るために使います。

```bash
python3 tools/check_worker_api.py \
  --base-url https://staging.vocaloid-title-search.example.com
```

確認する主な内容:

- `/health` がJSONを返し、`database_ready:true` である
- `/api/metadata` が取得できる
- `/api/popularity-labels` が取得できる
- `/api/search` が代表条件で検索結果を返す
- `/api/song-detail` が代表曲の詳細JSONを返す
- `/api/stats` が統計情報を返す

smoke test が通っても、UIの全操作、詳細抽出ロジック、全検索条件の正しさを保証するわけではありません。そうした契約は Python unit tests、Worker API tests、frontend build で確認します。

## Frontend E2E

Playwright E2Eは、実D1や外部APIに依存しないようにブラウザ側で `/api/*` をmockします。目的は、本番データの正しさではなく、主要UI操作が壊れていないことの確認です。

現在確認する導線:

- 未検索状態が表示される
- 検索条件を入力して結果を表示できる
- 詳細アコーディオンを開ける
- ページングできる
- 統計ビューから検索条件を適用できる
- desktop幅とmobile幅で同じ導線が成立する

スクリーンショット差分は現時点では導入しません。理由は、環境差で差分が揺れやすく、個人運用の通常開発ループに対してメンテナンスコストが高いためです。見た目の崩れは、まず操作E2E、frontend build、手動確認で扱います。

## API Profiling

代表APIのレスポンスタイムを測る場合は、Worker APIをローカルで起動した状態で次を実行します。

```bash
python3 tools/profile_worker_api.py --base-url http://127.0.0.1:8000 --repeat 3
```

このスクリプトは `/health`, `/api/metadata`, `/api/stats`, 代表的な `/api/search` 条件、`/api/song-detail` を測ります。厳密な負荷試験ではなく、検索条件や統計APIの相対的な遅さを見つけるための軽量プロファイルです。

JSONで記録したい場合:

```bash
python3 tools/profile_worker_api.py --base-url http://127.0.0.1:8000 --repeat 5 --json
```

環境別の使い方:

| 環境 | base URL | 目的 |
| --- | --- | --- |
| local | `http://127.0.0.1:8000` | local D1とWorker devの確認 |
| staging | staging custom domain | production前確認 |
| production | production custom domain | deploy後またはrollback後確認 |

## Layout

| 種類 | File | 対象 |
| --- | --- | --- |
| Python | `tests/helpers.py` | 一時DB、RawSong、曲詳細 fixture |
| Python | `tests/test_build_db_cli.py` | DB構築CLIの引数とvalidation |
| Python | `tests/test_database.py` | SQLite schema、検索、曲詳細、readonly参照 |
| Python | `tests/test_detail_extraction.py` | Wiki曲ページ詳細の構造化抽出 |
| Python | `tests/test_http_fetcher.py` | rate limit、429/502/503/504 retry、backoff |
| Python | `tests/test_models.py` | タイトル分離、文字数計算、grapheme cluster |
| Python | `tests/test_refresh_video_metadata_cli.py` | 動画メタデータ更新CLIの引数とvalidation |
| Python | `tests/test_video_metadata.py` | 動画メタデータ取得対象の収集とJSON更新 |
| Python | `tests/test_database_quality.py` | ローカルSQLiteの品質検査CLIとDB整合性 |
| Python | `tests/test_detail_quality.py` | 保存済み曲詳細JSONの欠損候補レポート |
| Python | `tests/test_wiki_fetching.py` | 人気度タグとタグページ取得の失敗許容 |
| Worker | `cloudflare/worker/test/worker-api.test.js` | Worker API route、validation、CORS、D1検索、詳細、統計 |
| Frontend E2E | `frontend/tests/e2e/search-flow.spec.ts` | 検索、詳細、ページング、統計遷移、mobile幅smoke |
| Tool | `tools/check_worker_api.py` | local / staging / production Worker API の smoke test |
| Tool | `tools/profile_worker_api.py` | 代表API条件の軽量レスポンスタイム計測 |
| Tool | `tools/check_docs.py` | docs内リンク、アンカー、見出し重複、孤立文書の検査 |
| Tool | `tools/check_docs.sh` | docs専用チェックの入口 |

## Naming

- テストファイルは `test_<対象領域>.py` とします。
- テストメソッド名は `test_<期待する振る舞い>` とし、実装詳細よりユーザーに見える結果や契約を表します。
- 新しいDB検索条件やAPI validationを追加した場合は、`test_database.py` と `cloudflare/worker/test/worker-api.test.js` に必要最小限のテストを置きます。
- 詳細抽出の個別ヒューリスティックは `test_detail_extraction.py` に置き、実ページ名に依存した回帰例も最小HTMLで再現します。

良いテスト名:

- `test_search_filters_by_stored_composer_credit`
- `test_drops_link_notes_but_keeps_meaningful_notes`

避けるテスト名:

- `test_case1`
- `test_fix_bug`
- `test_melt`

## Fixtures

DBを使うテストでは `tests.helpers.temporary_db()` を使います。これにより、一時ディレクトリ作成、DB構築、テスト後の削除が揃います。

```python
from tests.helpers import store_composer_detail, raw_song, temporary_db

with temporary_db([raw_song("メルト")]) as db_path:
    store_composer_detail(db_path, names=("ryo",))
```

外部ネットワークへはアクセスしません。HTTPや動画メタデータ取得のテストは `unittest.mock.patch` または fake opener を使います。

Worker APIテストも外部ネットワークと本物のD1には接続しません。`src/index.ts` をテスト実行時に `esbuild` で一時bundleし、D1互換のfake DBを渡して `fetch` handlerを直接呼びます。

`tools/check_worker_api.py` はデプロイ済みAPIまたはローカルWorkerへHTTPアクセスする smoke test です。Cloudflare 経由の確認で bot 判定や既定User-Agentによる拒否を避けるため、明示的な smoke test 用 User-Agent を送ります。

詳細抽出回帰テストの最小HTML例:

```python
html = """
<html><body>
<h3>基本情報</h3>
作曲：作者名（Twitter）
<h3>曲紹介</h3>
<p>曲名：『サンプル』（さんぷる）</p>
</body></html>
"""
detail = parse_song_detail(html, "https://w.atwiki.jp/hmiku/pages/1.html")
```

実ページ全体を貼らず、壊れた見出し、ラベル、値、リンクだけを残します。

## Test Boundaries

- `test_database.py` は repository / SQLite の契約を確認します。
- `cloudflare/worker/test/worker-api.test.js` は本番Worker APIのHTTP契約を確認します。Cloudflare本番の主APIはここを優先して守ります。
- 同じ振る舞いを両方で細かく重複検証しないようにし、DB側はデータ取得結果、API側はレスポンス/例外を中心にします。
- APIのレスポンス形状を変える場合は、Workerテスト、`shared/api-types`、[web-api.md](web-api.md) を同時に更新します。
- エラーレスポンスも契約です。Worker API のエラー本文は `detail` を使うため、`400` / `404` / `503` の本文を変える場合もテストと文書を合わせて確認します。

API contract変更時のチェックリスト:

- `shared/api-types.ts` を更新した
- Worker実装を更新した
- frontendの利用箇所を更新した
- Worker API testを更新した
- `docs/web-api.md` の例とvalidationを更新した

`tools/check_all.sh` が失敗した場合:

1. 失敗したセクション名を見る
2. Pythonなら `uv run --cache-dir .uv-cache python -m unittest` を単独実行する
3. Workerなら `(cd cloudflare/worker && yarn test)` を単独実行する
4. frontendなら `(cd frontend && yarn build)` を単独実行する
5. 秘匿情報スキャンなら検出値をプレースホルダーへ置き換える

## Search SQL Benchmark

検索SQLの変更は、APIの応答テストに加えてローカルSQLiteで測定します。Workerの実際のSQLをGit revisionと作業ツリーから読み、各条件で結果が完全一致することを確認してから実行時間の中央値を比較します。DBは読み取り専用で開き、D1には接続しません。

```bash
uv run --cache-dir .uv-cache python tools/benchmark_search_sql.py --baseline-ref HEAD --rounds 25
```

コミット後は `--baseline-ref` に変更前のrevisionを指定します。既定DBは `vocaloid_titles.sqlite3`、別DBは `--db-path` で指定できます。比較対象は先頭ページ、5文字検索、公開年降順、深いページです。最初の実行でキャッシュを温め、旧・新SQLの測定順を交互に変えます。SELECTの実行と結果取得のみを測り、件数取得・DB準備確認・通信・D1の課金上の読み取り行数は含みません。

2026-09-23の測定例（7,868曲、SQLite 3.47.1、25回の中央値、比較元 `c36c181`）。全曲分の作曲者集計を各結果の索引検索へ変更しました。

| 条件 | 変更前 | 変更後 |
| --- | --- | --- |
| 先頭50件 | 29.92ms | 6.89ms |
| 5文字の先頭50件 | 19.06ms | 0.36ms |
| 公開年降順の先頭50件 | 33.39ms | 14.33ms |
| 5,000件スキップ後の50件 | 39.62ms | 30.97ms |

深いページの効果は小さく、データ量・索引・SQLiteバージョンで値は変わります。D1やブラウザの応答時間を示す値ではありません。

`tests/test_search_sql.py` はWorkerのSQLをSQLiteで実行し、作曲者の並び順、作曲者なし、絞り込み、全ソート、ページ境界をPythonの検索結果と照合します。ネットワークを含むAPI性能は既存の `tools/profile_worker_api.py` で別途確認します。

## CI And Worker Integration

`.github/workflows/checks.yml` はpush・pull request・手動実行で、固定ランタイムとlockfileを使い、全体チェック、文書build、APIモックE2E、実Worker結合E2Eを実行します。Cloudflareの認証情報や実設定は不要です。GitHub上の実行にはworkflowを含む変更のpushが必要です。

```bash
(cd frontend && yarn test:integration)
```

結合E2Eは、合成データを専用local D1へ投入し、localhostのWorkerとfrontendを起動します。デスクトップ・モバイルで検索、詳細、ページング、統計からの検索、入力エラーを確認します。`test/wrangler.integration.toml` と `.wrangler/integration` を使い、通常の `wrangler.toml` と公開DBは読みません。localhostの4175・8789番ポートを空けて実行してください。

通常の `test:e2e` はAPIモックで競合検索・画像フォールバックなどを再現し、`test:integration` は実際の接続を検証します。両方ともrelease前に実行します。CI失敗時のPlaywright traceは7日間保存します。

## API Performance History

`tools/profile_worker_api.py` は代表APIの中央値・nearest-rank方式のp95・HTTP状態別件数・エラー率を測定します。HTTPエラー、通信失敗、DB未準備を検出した時点で残りの測定を打ち切ります。エラーがある場合、または指定したp95上限を超える場合は終了コード1になります。p95には失敗リクエストの所要時間も含みます。状態コード0は通信失敗またはhealth応答の検証失敗を表します。

```bash
python3 tools/profile_worker_api.py --base-url https://staging.vocaloid-title-search.example.com \
  --repeat 1 --interval 0.2 --redact-base-url --output release/performance/profile.json
```

`.github/workflows/api-profile.yml` は週次（月曜06:17 JST）と手動実行に対応します。リポジトリsecret `PROFILE_BASE_URL` に測定先を設定して有効にし、未設定なら明示してスキップします。認証tokenやCloudflare権限は不要です。対象は公開APIへのGETだけです。結果は実URLを除いて30日間artifactに保存します。

`PROFILE_MAX_P95_MS` をリポジトリvariableに設定すると遅延も失敗基準にできます。未設定は計測とエラー検知のみとし、実測を蓄積してから閾値を決めます。定点観測の少数サンプルであり、負荷試験や利用者全体のSLOとは区別します。公開先は各APIを1回だけ呼び出す疎通確認です。1回のp95はその1回の所要時間であり、性能傾向の判断には使いません。繰り返し測定はlocalhost・127.0.0.1・::1のみに許可します。正常時は最大9リクエスト、失敗時はその場で停止します。


## Local D1 Read Budget

無料枠の削減効果は、遅延だけでなくD1の `meta.rows_read` で判断します。Workerはリクエスト全体の `rows_read` と `d1_queries` を `api_timing` ログに記録し、`x-d1-rows-read` / `x-d1-queries` ヘッダーでも返します。D1から計測値が返らない場合、行数はログでは `null`、ヘッダーでは省略し、0と誤認させません。profilerの `rows_read` は各回、`total_rows_read` は合計です。取得方法は [D1 return objects](https://developers.cloudflare.com/d1/worker-api/return-object/) に基づきます。

```bash
uv run --cache-dir .uv-cache python tools/benchmark_d1_reads.py --baseline-ref HEAD
```

Node・Worker依存関係とローカルSQLiteが必要です。SQLiteを一時コピーし、検証済みSQLを隔離Miniflare D1へ投入して旧・新Workerの応答一致と読み取り量を記録します。Cloudflareには接続せず、元DBも変更しません。`--baseline-ref` は比較対象のGit revision、`--db-path` は別のSQLite、`--output` は結果の保存先です。既定の結果は `release/performance/d1-reads.json` です。

2026-09-24、7,868曲のコピーによるローカルD1測定では、公開状態・統計・タグ一覧は各1行、キャッシュヒット時の検索も1行でした。未キャッシュの通常検索は256行、5文字検索は254行です。公開年降順は23,816行、作曲者部分一致は16,588行が残るため、すべての検索が定数行になるわけではありません。実運用の課金量やヒット率を保証する数値ではありません。

## Internal Redesign Regression Checks

`tests/test_release_artifacts.py` は復旧だけでなく、hashが正しいSQLでも投入結果がsnapshotと違う場合に拒否することを検証します。`tests/test_video_metadata.py` はDB構築との競合を取得前に拒否し、同じ動画情報を再取得しても詳細行を書き換えないことを検証します。

画面E2Eは詳細を閉じた際の通信中断・再取得、検索の20秒タイムアウトと再試行、入力途中の条件をページ移動へ混ぜないことを検証します。APIモックのpage_sizeも実際の要求値に合わせます。

作業ツリーの変更前Workerを保存した場合は、次のように読み取り量を比較できます。保存先も出力もignore対象に置きます。

```bash
python3 tools/benchmark_d1_reads.py --baseline-source release/redesign-baseline/worker/index.ts \
  --output release/performance/redesign-d1.json
```

`--baseline-source` は保存済みentry pointからbundleします。通常は `--baseline-ref` を使い、そのGit revisionのWorkerとshared型を一時ディレクトリへ取り出すため、モジュール分割後のrevisionも比較できます。

2026-09-24、7,868曲をコピーしたローカルMiniflare D1で、直前の作業ツリーと比較しました。公開年降順の先頭50曲は29,951行から23,816行（約20%減）、2021年指定は1,777行から1,562行になりました。通常先頭256行、5文字254行、作曲者16,588行、20ページ目2,154行は同値、キャッシュ済み検索は1行です。代表APIの結果一致を検証しています。公開環境の実測や全検索条件の性能保証ではありません。

同じDBでSQLite 3.47.1のSELECTを25回測定した中央値は、公開年降順14.768ms→10.980ms、先頭ページ0.318ms→0.367msでした。ページ選択後の付加情報取得は並べ替え時の読み取りを減らしますが、通常先頭ページのCPU時間を一律に短縮するものではありません。


## Completion Audit Evidence

探索的な旧測定と撤回済みの完了判定は、現在の合格証拠として扱いません。終了判断は [台帳](completion/ledger.json) の要求別証拠を参照し、`release/completion/` のコマンド・環境・終了コード・ログhash・実行前後fingerprintが現行状態と一致することを確認します。古い測定値だけを文書へ転記して最終検証を代替しません。

今回のローカル受入範囲と検証限界は [開発backlogの監査表](development-backlog.md#completion-audit)、同一条件の性能比較は [事前合格基準](#performance-acceptance) を正本とします。


## Mechanical Completion Gate

終了判断の正本は `docs/completion/ledger.json`、初期定義と追加項目の履歴は `docs/completion/registry.json` です。台帳だけから項目を削除・弱体化しても完了にはできません。登録履歴を編集して条件を緩める行為も禁止し、内容レビューで変更差分を確認します。これは不正な編集を暗号学的に防ぐ仕組みではありません。

```bash
python3 tools/completion_gate.py run --id all
python3 tools/completion_gate.py check
python3 tools/completion_gate.py check --format json
```

`run` は台帳の登録コマンドを実行して、コマンド・対象・要求ID・関連残件ID・時刻・終了コード・ログhash・実行前後のソースfingerprintと実行環境（OS・CPU種別・Python/Node）を `release/completion/` に記録します。未追跡・未コミットのソースも含めます。台帳と履歴の2ファイルは状態として別検査し、生成物はGitのignore規則で除外します。検証対象に生成DB等が含まれる場合は、登録コマンドの `inputs` に指定して別途hashを照合します。ソース変更後は再実行が必要で、影響範囲を曖昧に推測して成功記録を再利用しません。

`--format json` は `ok`、`error_count`、IDと理由を含む `errors` を出力し、テキスト形式と同じ終了コードを返します。重複項目は `duplicate_of` で統合先を記録でき、存在しない統合先・参照の循環・未解決の統合先を拒否します。重複の記録だけでは解決扱いにならず、各項目の解決理由と証拠も必要です。

`check` は未解決、証拠なし、不正な参照、検証失敗・未実行・実行中、古いソースや変更されたログを拒否します。終了コード0になるまで作業完了とは扱いません。証拠の `finding`、修正不要理由、ユーザー承認参照が事実かどうかは、機械検査とは別に元の情報へ戻ってレビューします。完了ゲートは作業途中に失敗するのが正常なので、通常の `check_all.sh` にゲート実行そのものは含めず、ゲートの異常系回帰テストを含めます。

欠損候補の原文収集は `python3 tools/audit_detail_sources.py` です。表示上限なしで全候補をDBから列挙し、台帳に未登録の候補を検出したら失敗します。原文と再解析結果はignore対象の `release/completion/detail-sources/` に保存します。収集成功は修正不要の証明ではなく、すべての項目に個別レビューが必要です。元DBと公開環境は変更しません。


`python3 tools/check_detail_reviews.py` は全候補について `docs/completion/detail-reviews.json` の個別判断・原文hash・独立した期待値を照合します。原文が変わった場合や候補が増えた場合は再レビューが必要です。原文の不足を示す判断と、抽出修正の候補DBへの適用は別の残件として管理します。

候補DBの公開と復旧は次のコマンドでローカルSQLite上に再現できます。本番D1には接続せず、入力DBも変更しません。全テーブル・索引の更新後一致、元DBへの復旧一致、元DB比較を含む品質検査、成果物hashを確認します。検証成果物は `release/completion/candidate-release-*/` に保存されます。

```bash
python3 tools/verify_candidate_release.py --candidate release/completion/reviewed-candidate.sqlite3 --baseline vocaloid_titles.sqlite3
```

完了証拠として使う場合は候補・基準DBを `inputs` に指定して登録し、`completion_gate.py run --id candidate-release` から実行します。これはローカルSQLiteでの検証であり、D1上での実行確認を代替しません。

原文レビューの期待値が候補DBにも反映されていることは `python3 tools/check_detail_reviews.py --candidate release/completion/reviewed-candidate.sqlite3` で全候補を照合します。原文解析の成功だけではDBへの反映成功と扱いません。

完了チェックは実行環境の変更、空ログ、Python unittest・Node TAP・Playwrightの標準出力で報告される0件やスキップも拒否します。独自コマンドの検証対象が空でないことや検証内容の十分性は、各コマンドの検査と内容レビューで確認します。ログの文言だけで任意の検証プログラムの正しさを証明するものではありません。


## Performance Acceptance

最終ローカル比較の基準は [performance-criteria.json](completion/performance-criteria.json) に測定前に固定します。既存の探索的測定は、この基準への合格証拠として流用しません。

```bash
python3 tools/completion_gate.py run --id performance
```

登録済みの候補DBと保存した変更前ソースを使い、31回の交互SQL測定、同一ローカルD1での応答一致・読み書き、旧新各3回の交互Viteビルドを実行します。Node依存関係とGNU timeが必要です。DBと変更前ソースは入力fingerprint、基準と検証コードはソースfingerprintで固定します。元DB・公開環境・既存のfrontend/distは変更しません。

SQLは中央値の増加が20%または1 msの大きい方以内、かつ25 ms以内、D1の読み取りは増加なし、キャッシュ検索は1行、変更のない詳細に対するメタデータ更新は全投入の1%以内を要求します。JS gzipは増加2 KiB以内かつ45 KiB以内、CSSは増加512 B以内かつ6 KiB以内です。Viteビルド時間は増加25%または0.5秒以内、最大RSSは増加20%または32 MiB以内かつ768 MiB以内とします。固定ノイズ幅、増加を許す理由、確認限界は基準ファイルに記載します。

対象0件・欠損メトリクス・結果不一致・基準超過は失敗です。結果は `release/completion/performance-results.json`、実行記録とログは通常の完了チェッカーの保存先を確認します。失敗後に基準を緩めず、増加の原因と利用者への影響を調査します。時間とRSSはローカルビルド、読み書きはMiniflareの測定であり、本番の応答時間・ブラウザheap・請求額を保証しません。
