# Development Backlog

未完了の実装タスクと直近の検証結果を管理します。文書だけの改善は [documentation-improvement-backlog.md](documentation-improvement-backlog.md) に置きます。

## Task Rules

タスクは1つの検証可能な成果に分け、ID、状態、担当、依存先、完了条件、検証方法を記載します。状態は `Open`、`Ready`、`Blocked`、`Done`。担当は `Agent`、`Human`、`Shared` とし、人間の判断が必要なら内容を具体的に書きます。

採番済み上限: **DEV-084 / HD-004 / PI-005**。削除済みIDを再利用せず、新規追加時に上限を更新します。

## Current Work

| ID | Status | Owner | Area | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEV-084 | Done | Agent | completion | none | 残件台帳と完了チェックを機械化し全欠損候補を精査 | 実台帳の未解決0件と最終証拠が揃うまで完了しない | 完了チェッカーの異常系・実行記録・全件原文照合 |
| DEV-083 | Done | Agent | verification | DEV-079 | 実D1の全ソートを独立した期待順序で検証 | 異なる文字数・年・人気度・同順位・年欠損の順序が仕様と一致する | 固定した期待URL順序と実Workerの比較 |
| DEV-082 | Done | Agent | ingestion | DEV-079 | HTTP成功でも空のタグページを取得失敗として扱う | エラーページ・ページ欠落を空の人気度や部分的な曲一覧として保存しない | 先頭/後続ページ異常と旧DB保持の回帰 |
| DEV-079 | Done | Agent | audit | none | 要件からの再監査と反証検証 | 全終了条件に最終状態の直接証拠があり未検証事項がない | 下記再監査表・全体検証・最終反証レビュー |
| DEV-080 | Done | Agent | quality | DEV-079 | 曲の検索用派生値と並び順の整合性を公開前に検査 | 件数を変えない破損を検出し公開SQL生成も拒否する | 破損DB回帰・実DB検査 |
| DEV-081 | Done | Agent | build | DEV-079 | 最終差し替え失敗後もチェックポイントから再開する | 旧DBと再開情報を保持し再取得なしで完了できる | 差し替え失敗注入・再開・公開成功の回帰 |
| DEV-078 | Done | Agent | extraction | none | 概要見出しの曲紹介を抽出する | 紹介文とクレジット・歌詞の境界を保つ | 合成HTML回帰と取得済み代表HTMLの再解析 |
| DEV-077 | Done | Agent | UI | none | 初期タグ取得中の誤った既定条件検索を防ぐ | タグ確定まで検索を抑止し初期取得失敗から再試行できる | 遅延・初期失敗のブラウザ回帰 |
| DEV-076 | Done | Agent | API | none | PythonとWorkerの作曲者名casefoldを揃える | Unicodeの大文字小文字・互換文字で同じ曲を検索できる | 正規化生成検査・実D1結合 |
| DEV-071 | Done | Agent | audit | DEV-068〜DEV-070 | 全領域の終了条件監査 | 範囲・重大問題・互換性・測定・最終検証・残課題の証拠を記録 | 下記監査表と全体検証 |
| DEV-072 | Done | Agent | data | none | 人気度タグ取得失敗をDB構築へ伝播する | 不完全な人気度情報で既存DBを置換しない | 取得失敗と既存DB保持の回帰 |
| DEV-073 | Done | Agent | operations | none | 差分SQLの途中失敗から復旧する | 索引変更を含む全境界の中断後に旧DBへ戻る | 差分prefix復旧テスト |
| DEV-074 | Done | Agent | quality | none | 詳細JSONと派生検索列の整合性を検証する | 画面で扱えない型と検索値の不一致を公開前に検出する | 品質・公開SQLテストと実DB検査 |
| DEV-075 | Done | Agent | HTTP | none | 取得処理の終了と再試行を保証する | redirect loopを制限し一時的な接続障害を回復する | HTTP例外・redirect・再試行上限テスト |
| DEV-068 | Done | Agent | API | none | HTTP・公開状態・検索条件・キャッシュの責務分割とページ選択後の付加情報取得 | API互換と検索順序を保持しローカルD1で読み取り量を比較 | Worker・SQL・結合E2E |
| DEV-069 | Done | Agent | frontend | none | 検索結果・詳細取得・通信寿命を独立させる | 既存UIを維持し中断・期限・詳細キャッシュ上限を保証 | build・E2E |
| DEV-070 | Done | Agent | operations | none | 成果物検証の共通化と順方向の検証 | SQL投入結果と固定snapshotの全行が一致し復旧可能 | 公開・更新回帰とcheck_all |
| DEV-067 | Done | Agent | frontend | none | 検索条件を上端固定しheaderを除去、表示切替を見出し行へ配置 | 両ビューとモバイルで固定・検索・スクロールが動作する | build、E2E、ローカル画面確認 |
| DEV-066 | Done | Agent | operations | DEV-062 | 無料枠での差分投入とデプロイ | 品質・全件結果一致・復旧を検証しstaging→productionへ公開する | 差分回帰、全体チェック、両環境smoke |
| DEV-062 | Done | Agent | performance | none | 公開状態と統計の事前計算 | 公開完了をSQL末尾で記録しAPIの全件検査・集計をなくす | SQL中断・復旧、Worker、実D1結合テスト |
| DEV-063 | Done | Agent | performance | DEV-062 | 検索の短期キャッシュ | 正規化条件とDB revisionで分離しエラーと更新途中を保存しない | キャッシュ・更新・期限テスト |
| DEV-064 | Done | Agent | tooling | none | 公開API計測の読み取り予算 | 公開先は各1回まで、失敗時停止、rows_readを記録する | profiler回帰テスト |
| DEV-065 | Done | Agent | performance | DEV-062 | ローカルD1で読み取り量を検証 | 代表SQLの結果一致と読み取り削減を確認する | 実D1測定、check_all、結合E2E |
| DEV-054 | Done | Agent | data | none | 前回DB比較と動画品質率の公開ゲート | 件数・被覆率・取得成功率の劣化を検出し、保持情報を区別する | 品質回帰テスト |
| DEV-055 | Done | Agent | tooling | none | 更新排他・固定成果物・公開manifest | 検査と投入が同一DB由来で、同時更新を拒否する | 更新スクリプトテスト |
| DEV-056 | Done | Agent | tooling | none | 復旧リハーサル | 新SQL投入後にrollbackを適用し旧データと一致する | 復旧テスト |
| DEV-057 | Done | Agent | ci | none | CIと実Worker結合E2E | 秘密情報なしで全チェックと画面→Worker→D1を検証する | ローカル結合E2E、workflow検査 |
| DEV-058 | Done | Agent | data | none | DB構築の中断再開と期限付き再利用 | 成功済み詳細を再取得せず、中断しても公開DBを保持する | 再開・鮮度・失敗テスト |
| DEV-059 | Done | Agent | performance | none | API性能の継続計測 | 中央値・p95・エラー率を成果物として定期取得する | 計測テスト、手動workflow |
| DEV-060 | Done | Agent | frontend | none | UI状態と動画表示を分離 | 検索・統計・動画表示の責務を切り分け挙動を維持する | build、E2E |
| DEV-061 | Done | Agent | data | none | 動画抽出処理を分離 | 詳細抽出の入出力を保ち動画処理を独立させる | 抽出回帰テスト |

## Decisions And Completed Work

公開サイト運用とWeb UIを重視し、検索流入は抑制します。Cloudflare負荷対策は標準レベルとし、強いrate limitやTurnstileは問題発生時に検討します。判断の正本は [production.md](production.md)、公開前検査は [quality-gates.md](quality-gates.md)、日常運用は [operations.md](operations.md) です。

DEV-001〜DEV-053の完了履歴を整理しました。現在の実装・テストと正本文書から仕様を確認してください。古いタスク表を現行仕様として扱いません。

## Review And Cleanup

週次または大きな変更後に、未完了事項と依存先を確認します。`Done` は正本文書・テストへ理由と検証方法が移り、未完了タスクの依存先でなくなったら削除できます。未達の外部設定・実環境確認は完了結果と分けて記録します。

## Activation Status

実装とローカル検証は完了しています。GitHub Actions上の実行は変更のpush後に確認します。週次の公開API計測にはリポジトリsecret `PROFILE_BASE_URL` の設定が必要です。設定方法と未設定時の動作は [testing.md](testing.md#api-performance-history) を参照してください。

DEV-062〜DEV-065はローカル検証済みです。全体チェック、公開SQL中断・復旧、Workerテスト、7,868曲のローカルD1比較、結合E2E 4件、UI E2E 6件を確認しました。公開形式version 1はDEV-066でstaging・productionへ投入済みです。再投入時は [移行手順](operations.md#publication-format-migration) に従い、D1投入とWorker deployをstagingから順に行います。

DEV-066は両環境のバックアップ・全件結果一致・差分復旧を検証し、D1→Pages / Workerの順で公開しました。両環境でAPI smokeと実ブラウザの検索・統計・両サービスのサムネイルを確認しました。差分投入は各23,635行を書き込み、統計とキャッシュ済み検索は各1行を読み取りました。公開記録・復旧SQLはignore対象のreleaseディレクトリへ保存します。

DEV-068〜DEV-070はローカル実装・検証済みです。Python 134件、Worker 23件、UI E2E 14件、実Worker結合E2E 4件と文書buildを確認しました。実データのコピーで通常・差分SQLの投入結果と復旧を照合しています。公開環境への適用は別のデプロイ作業です。

## Completion Audit

現在の終了判断は [機械可読台帳](completion/ledger.json) と [登録履歴](completion/registry.json) を正本とします。過去のDone表記や探索的測定だけでは今回の完了を証明できません。未解決・必須未検証がともに0件となり、最終コードの証拠と文書を照合して完了チェックが成功するまでDEV-084を閉じません。

対象は現行機能・合意済みの固定検索UI・無料運用を維持したプロジェクト全体です。コミット・push・本番変更は別途明示されるまで実施しません。既知の候補を独断で延期・対象外にせず、修正後の成功、項目ごとの直接証拠による修正不要、ユーザーの明示的承認のいずれかで解決します。

| 領域 | 受入条件 | 証拠の確認先 |
| --- | --- | --- |
| UI | PC・モバイルの検索・統計・詳細・動画・ページ操作と失敗回復 | REQ-UI、UI E2E、実D1結合、候補DBブラウザ検証 |
| API | 独立期待値との一致、入力境界、公開revision、キャッシュ、CORS | REQ-API、Workerテスト、実D1比較 |
| 取得・品質 | 部分取得を拒否し、既知の欠損候補を全件原文照合する | REQ-DATA、個別レビュー、全タグ取得、メタデータ診断 |
| DB構築 | 中断・再開・再利用・競合時に旧DBと回復手段を保持する | REQ-DATABASE、異常系、候補DBの品質・全行一致 |
| 公開・復旧 | 検査したsnapshotを投入し通常・差分・途中失敗から復旧できる | REQ-OPERATIONS、成果物照合、独立クライアントのD1排他 |
| CI・文書 | 固定依存と実装・CI・操作説明が一致する | REQ-CI_DOCS、check_all、文書build、内容レビュー |
| 効率 | 同一条件の結果を維持し時間・資源・配信サイズを基準と比較する | REQ-PERFORMANCE、[測定前に固定した基準](completion/performance-criteria.json) |
| 終了判定 | 未解決・証拠不足・陳腐化・不正な参照や定義を拒否する | REQ-GATE、完了チェッカーの異常系と実台帳の照合 |

### Design Decisions

SQLiteを構築元、D1を公開用コピーとする構成を維持します。読み取り専用APIへ外部取得・検査・更新の複雑さを持ち込まず、追加の有料サービスを必要としないためです。Workerは公開状態・検索・キャッシュ、frontendは入力条件・適用済み結果・詳細通信の寿命を分離します。

データの推定補完は避け、原文で確認できた役割・名前・紹介文を保存します。既知候補の判断は `detail-reviews.json` と `credit-reviews.json`、候補DBへの適用と派生索引の保持は登録済み検証へ対応付けます。複数ホスト更新はD1上の所有者ロックで排他し、失敗後は所有者と公開状態を確認して復旧します。

### Verification Limits

ローカルSQLite、隔離Miniflare D1、PC・モバイルのChromiumエミュレーション、公開先への読み取り確認を区別します。候補DBのローカル確認は本番反映の証明ではありません。元SQLiteと本番環境は変更せず、GitHub上のCI実行や本番の課金・遅延はローカル結果から推定しません。

原文の真偽や未掲載情報、未知の不具合が絶対にないことは保証できません。ただし、既知の問題・未確定候補・必須未検証をこの限界に含めて終了することはできません。検証コマンドと記録の読み方は [機械検証](testing.md#mechanical-completion-gate) を参照してください。
