# Development Backlog

未完了の実装タスクと直近の検証結果を管理します。文書だけの改善は [documentation-improvement-backlog.md](documentation-improvement-backlog.md) に置きます。

## Task Rules

タスクは1つの検証可能な成果に分け、ID、状態、担当、依存先、完了条件、検証方法を記載します。状態は `Open`、`Ready`、`Blocked`、`Done`。担当は `Agent`、`Human`、`Shared` とし、人間の判断が必要なら内容を具体的に書きます。

採番済み上限: **DEV-061 / HD-004 / PI-005**。削除済みIDを再利用せず、新規追加時に上限を更新します。

## Current Work

| ID | Status | Owner | Area | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
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
