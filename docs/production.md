# Production Design

公開環境では Cloudflare Pages + Workers + D1 を推奨構成とします。この文書は本番設計の判断を説明します。日常の deploy、DB更新、ログ確認、rollback は [operations.md](operations.md) を参照してください。

運用レベルは、基本的に個人運用を前提にします。大規模なSRE体制や常時監視を前提にせず、staging確認、dry-run、smoke test、backup、rollback手順で事故を減らす方針です。productionへ影響する操作だけは、個人運用でも慎重に扱います。

データストアと環境の基本用語は [concepts.md](concepts.md) にまとめています。

## Recommended Topology

- `frontend/dist`: Cloudflare Pages で静的配信
- `/api/*`, `/health`: Cloudflare Worker
- 検索DB: Cloudflare D1
- DB 更新ジョブ: 手元でSQLiteを作成し、D1用SQLを生成してstaging / production D1へ投入

Cloudflare構成の全体像は [cloudflare-serverless.md](cloudflare-serverless.md)、Terraform 管理範囲は [infrastructure.md](infrastructure.md) を参照してください。

## Product Priority

当面の品質改善は「公開サイト運用中心 + Web UI重視」で進めます。

この方針にした理由:

- Cloudflare Pages / Worker / D1 で公開運用する構成に移行済みである
- 利用者が直接触る入口はWeb UIである
- 個人運用では、機能追加よりも低負荷、壊れにくいdeploy、分かりやすいUIの優先度が高い
- CLIはDB構築・品質検査・D1投入のための運用ツールとして安定性を重視する

優先順位:

| 順位 | 対象 | 重視すること |
| ---: | --- | --- |
| 1 | 公開サイト運用 | deploy安全性、D1投入、smoke test、負荷抑制、rollback |
| 2 | Web UI | 検索、統計、詳細表示、モバイル操作性 |
| 3 | CLI | DB構築、品質検査、動画メタデータ更新の確実性 |

## Runtime Boundary

本番ランタイムは Cloudflare Pages、Cloudflare Worker、Cloudflare D1 だけで構成します。Python package は本番サーバーで常駐させず、手元またはCIのDB更新ジョブでだけ使います。

Python 側の責務は、初音ミク Wiki の取得、曲ページHTML解析、SQLite DB構築、動画メタデータ更新です。`tools/update_d1.sh` は既存SQLiteからD1投入用SQLを生成してstaging / production D1へ投入します。Worker 側の責務は、D1を読み取り、検索・統計・詳細APIを返すことです。通常リクエスト時に外部Wikiや動画サイトへアクセスしません。

この境界にした理由:

- リクエスト時に外部Wikiや動画サイトへアクセスすると、レスポンスタイムと失敗要因が増えるため
- Cloudflare Worker は軽い読み取りAPIに向いており、HTML解析や長時間の一括取得はローカルジョブの方が扱いやすいため
- SQLite を source of truth として手元で検証してから D1 へ投入できるため
- Python の BeautifulSoup ベースの詳細抽出を、公開ランタイムから切り離してテストしやすくするため

本番ランタイムがしないこと:

- Wikiページの巡回
- 曲詳細HTMLの解析
- 動画メタデータの外部取得
- D1の通常リクエスト時更新

## Artifacts And Data

本番更新は、アプリケーション成果物とデータ更新を分けます。

| 対象 | 作るもの | 更新方法 |
| --- | --- | --- |
| Web UI | `frontend/dist` | Cloudflare Pages deploy |
| Worker API | Worker script | Wrangler deploy |
| 検索DB | SQLite DB / D1 SQL | `tools/update_d1.sh` で D1 へ投入 |

`tools/update_d1.sh` は D1 SQL生成とstaging / production D1への投入だけを担当します。Wiki取得やSQLite DB構築は `python -m vocaloid_title_search.cli.build_db`、動画メタデータ更新は `python -m vocaloid_title_search.cli.refresh_video_metadata` が担当します。

staging / production の具体的なコマンドは [operations.md](operations.md) に置きます。

## Read-Only Runtime

Cloudflare WorkerはD1を参照するだけで、通常リクエストではDBを更新しません。D1更新は `tools/update_d1.sh` からの投入に限定します。

## Search Engine Policy

公開サイトは、検索エンジンからの流入を積極的に増やす目的では運用しません。利用者増加によるD1/API負荷や、データ取得元への間接的な負荷増加を避けるためです。

方針:

- `robots.txt` は `Disallow: /` とする
- HTMLには `noindex,nofollow,noarchive` を設定する
- OGPや構造化データなど、検索流入を増やすための最適化は行わない
- 必要な利用者にはURLを直接共有する

これは善意のcrawler向けの抑制です。悪意あるアクセスや過剰アクセスへの対策は、Cloudflare側のWAF、rate limiting、ログ確認など別の仕組みで扱います。

役割の違い:

| 対策 | 主な目的 | 限界 |
| --- | --- | --- |
| `robots.txt` | crawlerへ巡回しないでほしい範囲を伝える | 従わないbotには効かない |
| `noindex,nofollow,noarchive` | 検索結果への掲載やリンク追跡を抑える | 既に知られたURLのアクセス自体は止めない |
| OGP/構造化データを増やさない | 検索・SNS流入を積極的に増やさない | 共有されたURLの閲覧は止めない |
| Cloudflare WAF / rate limiting | 過剰アクセスや攻撃的なtrafficを抑える | ルール設計とログ確認が必要 |
| Worker logs / D1 metrics | 負荷やエラーの兆候を観測する | 予防ではなく検知に近い |

個人運用では、検索エンジン抑制を「負荷対策の一部」として扱います。負荷が実際に増えた場合は、robots設定だけで解決しようとせず、Cloudflare側の制御とログ確認へ進みます。

## Low-Cost Traffic Protection

Cloudflare側の負荷対策は、まず「標準」レベルで運用します。強い制限やTurnstileは、実際に過剰アクセスやbotアクセスが問題になってから検討します。

標準レベルで行うこと:

| 対策 | 方針 |
| --- | --- |
| Cloudflare Proxy | custom domain はProxy経由で公開する |
| 検索流入抑制 | `robots.txt` と `noindex,nofollow,noarchive` を維持する |
| WAF / bot対策 | 無料または低コストで使える範囲のmanaged rulesやbot対策を検討する |
| rate limiting | まずはログとアクセス傾向を見て、必要になったら軽い制限を追加する |
| Worker logs | 5xx、429相当、`api_timing` の遅いpathを確認する |
| D1 metrics | 読み取り増加や失敗がないかdeploy後に見る |

当面は、UXを悪化させやすいTurnstileや厳しすぎるrate limitは入れません。

エスカレーションの目安:

| 症状 | 次に検討すること |
| --- | --- |
| 短時間に同一IPから大量アクセス | rate limiting rule |
| 明らかなbot trafficが増える | Cloudflare bot対策 / WAF rule |
| `/api/stats` や検索APIが遅くなる | API cache、query見直し、rate limiting |
| D1読み取りが想定より増える | cache対象APIの選定 |
| 悪意あるフォーム的アクセスが必要になる | Turnstile。ただし現状は検索UIなので優先度は低い |

## Atomic Database Update

DB構築CLIは一時 SQLite ファイルを同じディレクトリに作成し、曲一覧と曲詳細の全件取得が完了した後に `os.replace()` で差し替えます。稼働中の API は、古い完全な DB か新しい完全な DB のどちらかを見ます。

D1更新では、生成済みSQLiteからD1用SQLを作り、staging / production D1へ投入します。この処理全体をDB全体のatomic swapとして扱いません。投入中はD1が一時的に利用できない、または更新途中の状態を読まれる可能性があります。

現在の方針は、staging確認後にproduction D1へ投入し、production更新は低トラフィックの時間帯に実行することです。ユーザーから見て旧データか新データのどちらかだけを見せる必要が出た場合は、`generation_id` と `metadata.active_generation` を使うアプリケーションレベルの世代切り替えを検討します。

将来案:

| 案 | 効果 | コスト |
| --- | --- | --- |
| `generation_id` を全テーブルに持たせる | 旧世代と新世代を同居できる | schemaとqueryが複雑になる |
| D1 databaseを二重化する | DB単位で切り替えやすい | binding切替と運用が重い |
| metadataでactive generationを切り替える | アプリケーションレベルで疑似atomicにできる | すべてのqueryに世代条件が必要 |

現時点では、データ規模と運用頻度を考え、staging確認後にproductionへ投入する単純な方式を優先します。

## Fetch Throttling

DB更新ジョブは既定で同一ホストへのリクエスト間隔を `0.2` 秒空け、詳細取得の最大並列数を `8` にしています。HTTP 429 / 502 / 503 / 504 は `Retry-After` があればその値を使い、なければ指数バックオフで最大 `30` 秒まで待って再試行します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db --request-interval 0.5 --workers 4
```

公開運用では、初音ミク Wiki へのアクセスはこの更新ジョブだけに限定し、Worker の通常リクエストでは外部取得を行いません。

## Song Details

`/api/song-detail` は運用時に外部 Wiki を取得しません。曲詳細はDB構築CLIの中で全曲分取得し、`song_details` テーブルに保存します。詳細が揃っていないDBは `/health` で `database_ready: false` になります。

動画タイトルやニコニコの実サムネイルURLまで事前取得したい場合は、DB構築後に動画メタデータだけを更新します。既存DB内のユニークな動画IDだけを取得対象にするため、曲詳細ページを再取得せずに済みます。

動画メタデータをDB構築から分けている理由は、曲ページ取得と外部動画サービス取得で失敗条件と所要時間が違うためです。DB構築はWiki由来の検索データを完成させることを優先し、動画タイトルや実サムネイルは必要なときだけ後段で補完します。

```bash
uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.refresh_video_metadata --workers 32
```

## Performance Strategy

実装済み:

- 検索APIは `songs.title_length` と人気度用 index を使います。
- 詳細APIは JSON を SQLite から読み、HTML 解析をリクエスト時に行いません。
- 動画カードは `/api/song-detail` が返す詳細JSONだけで表示します。動画メタデータが未取得でも、IDベースのリンクとサムネイル候補で表示できます。

将来の候補:

| 対象 | 候補 |
| --- | --- |
| `/api/search` | 短時間cache。条件が多いためcache key設計が必要 |
| `/api/metadata` | 長めのcache。D1投入後に自然更新されればよい |
| `/api/popularity-labels` | 長めのcache。更新頻度が低い |
| `/api/stats` | 中程度のcache。統計ビュー表示時の負荷を下げられる |
| `/api/song-detail` | 曲URL単位のcache。詳細JSONはD1投入まで変わらない |

Fetch throttling の既定値は [cli-reference.md](cli-reference.md#build_db) を正本にします。

## Runtime Change Review

読み取り専用runtimeを破る変更を入れる場合は、次を確認します。

- Workerが外部Wikiや動画サービスへ通常リクエスト時にアクセスしないか
- WorkerがD1へ書き込む経路を増やしていないか
- cacheや書き込みを入れる場合、staging / productionで分離できるか
- 失敗時にユーザー操作のレスポンスが外部サービスへ依存しないか
- テストとドキュメントで新しい責務境界を説明できるか

## Operational Checks

```bash
tools/check_all.sh
```

```text
GET /health
```

`database_ready` が `true` なら、検索に必要な DB、metadata、曲詳細が揃っています。
