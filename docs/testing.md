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

代表APIのレスポンスタイムを測る場合は、Worker APIを起動済みまたは公開済みの状態で次を実行します。

```bash
python3 tools/profile_worker_api.py --base-url http://127.0.0.1:8000 --repeat 3
```

このスクリプトは `/health`, `/api/metadata`, `/api/stats`, 代表的な `/api/search` 条件、`/api/song-detail` を測ります。厳密な負荷試験ではなく、検索条件や統計APIの相対的な遅さを見つけるための軽量プロファイルです。

JSONで記録したい場合:

```bash
python3 tools/profile_worker_api.py --base-url https://staging.vocaloid-title-search.example.com --repeat 5 --json
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
