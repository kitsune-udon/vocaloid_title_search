# Documentation Improvement Backlog

文書だけで完了する改善を管理します。実装を伴う改善は [development-backlog.md](development-backlog.md)、書き方の基準は [documentation-quality.md](documentation-quality.md) を参照してください。

## Task Rules

読者が行う判断・作業ごとに改善を分け、担当、依存先、完了条件と検証方法を記録します。状態と担当の意味は開発backlogと共通です。操作できない・誤操作する問題を優先し、次に不足や重複、最後に表現を直します。

採番済み上限: **DOC-068 / DH-005 / DPI-005**。削除済みIDは再利用しません。

## Current Work

| ID | Status | Owner | Depends on | Task | Acceptance | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-068 | Done | Agent | DEV-054〜DEV-061 | 品質・再開・公開記録・CIの手順を文書化し完了履歴を整理する | 正本から手順、限界、未設定事項を追える | docsチェック、VitePress build |

## Review And Cleanup

週次または大きな変更後に、古い手順・重複・未完了事項を確認します。正本は [Documentation Guide](README.md#document-boundaries) で決め、他文書からリンクします。人間の判断が必要な項目は、その判断と作業への影響を明記します。

DOC-001〜DOC-067の完了履歴を整理しました。READMEは開発者・個人運用者向けの入口、公開運用はstaging確認と復旧を重視する方針を維持します。判断理由は [production.md](production.md)、[operations.md](operations.md)、[repository-privacy.md](repository-privacy.md) が正本です。

完了項目は、仕様や判断が正本文書へ移り、関連テスト・手順から検証でき、未完了タスクの依存先でなくなれば削除できます。採番上限は残します。
