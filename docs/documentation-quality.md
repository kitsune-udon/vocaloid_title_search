# Documentation Quality

README、`docs/`、`AGENTS.md` を編集する際の基準です。実装と一致する説明を、読者が必要な場所で見つけられることを優先します。

## Placement

文書の責務は [Documentation Guide](README.md#document-boundaries) を正本とします。同じ手順は一か所に置き、ほかの文書からリンクします。新規ファイルは、既存文書へ統合すると読者や目的が混ざる場合に追加します。

- READMEは作業の入口、参照文書は仕様、runbookは実行と復旧の手順を扱います。
- 設計判断には、選んだ理由と再検討に必要な制約を短く残します。
- 過去の作業ログ、一般論、読者の行動を変えない注意書きは削除できます。
- 文書だけの改善は [documentation-improvement-backlog.md](documentation-improvement-backlog.md)、実装を伴う改善は [development-backlog.md](development-backlog.md) で管理します。完了条件と検証方法を記載し、完了後は正本やテストから追える状態にします。

## Commands And Operational Scope

コマンドはリポジトリルートから実行できる形にします。別ディレクトリで実行する場合は `(cd frontend && yarn build)` のようにsubshellを使います。常駐プロセスは、開いたままにするターミナルを示します。

状態を変える操作には、実行前に対象環境とリソース、実行後に確認方法と期待結果を示します。失敗時は、確認するログや復旧手順へ案内します。productionへの操作は [operations.md](operations.md) の承認・staging検証・復旧手順に従います。

このプロジェクトで混同しやすい操作を区別します。

| 用語 | 対象 |
| --- | --- |
| DB構築 | source of truthとなるローカルSQLiteを生成する |
| D1投入 | SQLiteから生成した曲データをlocal / staging / production D1へ配布する |
| deploy | Worker scriptやPages artifactを公開する |
| Terraform import | 既存Cloudflare resourceをTerraform stateへ取り込む |
| 生成 | SQLや`wrangler.toml`などの派生ファイルを書き出す |

「反映」「D1 import」「remote D1」だけでは操作や環境が分かりません。具体的な対象と動詞を使います。データの流れは [concepts.md](concepts.md) を参照してください。

ランタイムと依存関係はリポジトリの固定バージョンを使います。日常運用はwrapper scriptを案内し、Wranglerを直接実行する場合は `cloudflare/worker` の `./node_modules/.bin/wrangler` を使います。

## Evidence And Writing

- 冒頭で文書の対象と範囲を示し、前提、操作や仕様、確認方法の順に説明します。全ページに同じテンプレートを強制する必要はありません。
- 仕様はコード、CLIの`--help`、テストと照合します。性能値には測定対象・条件・限界を添えます。外部仕様に依存する記述は確認日や根拠を必要に応じて残します。
- 見出しは内容を予測できる名前にし、通常は `##` と `###` を使います。変更した見出しへの既存リンクも更新します。
- 平易な日本語で、操作する主体と対象を明確に書きます。製品名やコマンド名は無理に訳しません。
- 表は比較や選択に使い、狭い画面で読めない列数にしません。箇条書きで同じ意味を繰り返さないようにします。

## Docs Site

`docs-site/` は既存Markdownを読むためのローカルVitePressプレビューです。公開して検索流入を増やす用途ではありません。

```bash
(cd docs-site && yarn install)
(cd docs-site && yarn dev)
```

`yarn dev` のターミナルを開いたまま、表示されたローカルURLでページを確認します。ビルド確認は次のコマンドです。

```bash
(cd docs-site && yarn build)
```

サイドバーと [Documentation Guide](README.md) の導線を揃え、ページタイトル、見出し、ページ間リンク、表の折り返しを確認します。VitePress用の調整でもMarkdown単体の可読性を保ちます。設定変更時は [project-structure.md](project-structure.md#docs-site) と [testing.md](testing.md#documentation-checks) も更新します。

## Privacy

実在するユーザー名、メール、運用ドメイン、IP、Cloudflare ID、認証情報は書きません。例は `user@example.com`、`vocaloid-title-search.example.com`、`203.0.113.10`、`replace-with-...` などのプレースホルダーにします。詳細は [repository-privacy.md](repository-privacy.md) が正本です。

## Final Review

変更範囲について次を確認します。

1. 現在の実装と一致し、正本文書に記載されている。
2. 操作の前提・対象環境・成功確認・失敗時の確認先が分かる。
3. 読む順番、見出し、用語が自然で、重複手順や不要な履歴がない。
4. 秘匿情報や個人環境の実値がない。
5. 追加・変更したリンクとアンカーが有効で、必要な文書へ入口から辿れる。

```bash
tools/check_docs.sh
git diff --check
```

`check_docs.sh` は秘匿情報と文書構造・リンクを検査します。内容の正確性や手順の妥当性は別途レビューします。文書構成やDocsサイトの設定を変更した場合は、VitePress buildも実行します。
