# Documentation Quality

この文書は、README、`docs/`、`AGENTS.md` などのドキュメントを編集するときの品質基準です。エージェント固有のローカル設定に依存せず、リポジトリで管理する共通ルールとして扱います。

秘匿情報や実ドメインを書かないルールは [repository-privacy.md](repository-privacy.md) を参照してください。

## Goal

ドキュメントは人間の判断を助けるために書きます。コマンドや現在のファイル位置だけでなく、将来の保守者が「なぜこの構成なのか」「どの操作が何を変更するのか」を理解できる状態を目指します。

必要に応じて、次の情報を短く補います。

- Background: どの問題や運用上の痛みから現在の設計になったか
- Decision: 何を選び、どのコンポーネントが責務を持つか
- Rationale: なぜこのリポジトリではその方法を選ぶのか
- Alternatives: 再検討されやすい代替案と、採用しなかった短い理由
- Boundaries: そのコマンド、モジュール、サービスが何をしないか
- Safety notes: 本番、認証情報、外部サービス、長時間のネットワーク取得に触れる注意点

履歴をすべて残す必要はありません。短い「なぜ存在するか」や「運用境界」があるだけで十分なことが多いです。

## Context Density

短く書くことと、背景を残すことは対立しません。読者が判断を誤りやすい箇所だけ、短い背景を添えます。

| 状況 | 書く量 | 例 |
| --- | --- | --- |
| 単純なコマンド参照 | コマンドと目的だけ | `validate_db` はD1投入前のDB検査に使う |
| 破壊的・外部影響がある操作 | 変更対象、変更しない対象、確認方法を書く | D1投入はD1データを変えるがPages/Workerは変えない |
| 過去に混同が起きた概念 | 境界と採用理由を短く書く | Terraform import とD1投入は別操作 |
| 将来再検討されそうな設計 | 代替案と採用しない理由を1表にする | Worker通常リクエストで外部Wikiを取らない |

冗長な文章は削りますが、判断に必要な背景まで削らないようにします。特に個人運用、検索流入抑制、D1更新、Terraform、秘匿情報の扱いは、短い理由を残します。

## Quality Bar

高品質なドキュメントは、正しいだけでは足りません。読者が迷わず入口を選び、手順の影響範囲を理解し、失敗時に次の確認へ進める必要があります。

品質を次の段階で考えます。

| 段階 | 状態 | 対応 |
| --- | --- | --- |
| Incorrect | 内容が実装、運用、コマンド仕様と矛盾している | 必ず修正する |
| Incomplete | 重要な前提、影響範囲、確認方法が欠けている | 作業対象に含める |
| Usable | 手順は実行できるが、理由や境界が弱い | 関連する変更時に改善する |
| Maintainable | 置き場、用語、リンク、確認方法が一貫している | 目標水準 |
| Excellent | 代替案、判断理由、失敗時の見方まで簡潔に分かる | 重要な設計・運用文書で目指す |

すべての文書を同じ密度にしません。`operations.md`, `infrastructure.md`, `production.md`, `data-model.md`, `web-api.md` は影響範囲が広いため、`Maintainable` 以上を目指します。README や短い参照文書は、入口として迷わないことを優先します。

## Review Workflow

ドキュメントを直すときは、文章表現から入らず、次の順で確認します。

1. Accuracy: 現在のコード、スクリプト、運用方針と矛盾していないか
2. Placement: その情報は正しい文書にあるか
3. Structure: 読む順番、見出し、リンクの流れが自然か
4. Actionability: コマンド、確認方法、失敗時の次の行動があるか
5. Safety: production、D1、Terraform、認証情報への影響が明示されているか
6. Language: 日本語が自然で、用語が揺れていないか
7. Privacy: 実値や秘匿情報が混ざっていないか

表現だけを磨いても、置き場や前提が間違っている文書は高品質になりません。大きな修正では、最初に文書の責務と読者を確認してください。

## Placement

同じ手順を複数の文書へコピーせず、正規の置き場に書いてリンクします。

| 内容 | 置く文書 |
| --- | --- |
| 全体の入口、読む順番 | top-level `README.md`, [docs/README.md](README.md) |
| SQLite / D1 / deploy / Terraform import の関係、用語 | [concepts.md](concepts.md) |
| ローカル開発、ローカルDB、ローカルD1、開発サーバー | [usage.md](usage.md) |
| CLIのオプション、既定値、実行例 | [cli-reference.md](cli-reference.md) |
| 日常運用、staging / production deploy、D1投入、ログ、rollback | [operations.md](operations.md) |
| Terraform、Cloudflare resource、API token、import / apply | [infrastructure.md](infrastructure.md) |
| Worker API contract | [web-api.md](web-api.md) |
| Web UI の画面仕様、レスポンシブ方針 | [frontend-ui.md](frontend-ui.md) |
| テスト実行、smoke test、テスト責務 | [testing.md](testing.md) |
| 本番設計、読み取り専用運用、性能方針 | [production.md](production.md) |
| SQLite / D1 schema、保存データの意味 | [data-model.md](data-model.md) |
| 詳細情報抽出の入出力と保存方針 | [detail-extraction.md](detail-extraction.md) |
| 詳細情報抽出アルゴリズム | [detail-extraction-algorithm.md](detail-extraction-algorithm.md) |
| 個人情報や実値を入れないルール | [repository-privacy.md](repository-privacy.md) |
| 開発タスク、依存関係、担当、プロセス改善 | [development-backlog.md](development-backlog.md) |
| ドキュメント改善タスク、依存関係、担当 | [documentation-improvement-backlog.md](documentation-improvement-backlog.md) |

README は入口に留めます。詳細手順や長い runbook は `docs/` に置き、README からリンクします。

## Docs Site

`docs-site/` は、`docs/` のMarkdownをVitePressで読むためのローカルプレビューです。公開サイトとして検索流入を増やす目的では使いません。ブラウザで、サイドバー、ページ間リンク、見出し階層、表の折り返しを確認したいときに使います。

```bash
(cd docs-site && yarn install)
(cd docs-site && yarn dev)
```

ビルド確認:

```bash
(cd docs-site && yarn build)
```

Docs siteで読みやすくするための基準:

- 各文書の最初の `#` は、ファイル名から予測できる短いタイトルにする
- 冒頭の1段落で、その文書を読むべき人と扱う範囲を示す
- `##` と `###` を基本にし、深すぎる見出し階層を作らない
- サイドバーへ載せる文書は、[README.md](README.md) の読む順番と矛盾させない
- Markdownリンクは可能な限り `docs/` 内の正本文書へ向ける
- リポジトリ直下のファイルや生成物をリンクしたい場合は、リンク切れを避けるため、必要ならコード表記で示す
- 長い表は、モバイル幅で読めるように列数を増やしすぎない
- VitePress固有の表示調整を理由に、Markdown単体の読みやすさを壊さない

Docs siteの設定を変えた場合は、[project-structure.md](project-structure.md#docs-site) と [testing.md](testing.md#documentation-checks) も確認します。

## Document Types

文書の種類ごとに、期待される構成は異なります。種類が混ざる場合は、主目的を1つ決め、他の内容はリンクに逃がします。

| 種類 | 目的 | 必ず含めるもの | 置かないもの |
| --- | --- | --- | --- |
| Overview | 全体像をつかむ | 主要コンポーネント、読む順番、責務境界 | 詳細なコマンド列 |
| Concept | 用語と考え方を共有する | source of truth、データフロー、使い分け | 日常手順の全文 |
| Runbook | 操作する | 前提、コマンド、影響範囲、確認、rollbackや切り分け | 長い設計史 |
| Reference | 仕様を確認する | パラメータ、既定値、レスポンス、validation | 運用判断の説明 |
| Design | 判断理由を残す | 背景、選択、理由、境界、代替案 | コピペ用の長い手順 |
| Policy | 守るべきルールを示す | 禁止事項、許可される例、確認方法 | 個別作業の手順 |

例えば、`operations.md` は runbook なので「どう実行し、どう確認するか」を中心にします。なぜ Cloudflare 構成なのかは `production.md` や `cloudflare-serverless.md` へ置きます。

## File Organization Review

新しい文書を追加する前に、既存文書へ統合できないか確認します。文書を増やすのは、読者の入口が明確になり、既存文書へ追記すると責務がぼやける場合だけにします。

ファイル配置を見直すときは、次を確認します。

- Ownership: その文書が扱う責務は1つに絞られているか
- Audience: 主な読者が、開発者、運用者、設計確認者、エージェントのどれか分かるか
- Entry Point: README または [docs/README.md](README.md) から自然に辿れるか
- Boundary: 置くものと置かないものが説明できるか
- Canonical Source: 同じ手順や説明が複数箇所に重複していないか
- Lifecycle: 頻繁に変わる手順と、長く残る設計判断が同じ文書で混ざっていないか
- Locality: コードに近い短い補足で済む内容を、過度に遠い文書へ分離していないか
- Discoverability: ファイル名から内容を予測できるか

ファイル名は、対象と目的が分かる具体名にします。`notes.md`, `misc.md`, `memo.md`, `howto.md` のような広すぎる名前は避けます。既存文書を分割する場合は、分割後の各文書の役割を [docs/README.md](README.md) の `Document Boundaries` に追加します。

## Document Structure

各文書は、読者が上から順に読んだときに判断できる順序にします。

基本形:

1. この文書が扱う範囲
2. 前提条件や対象読者
3. 背景または設計判断
4. 実行手順、仕様、または詳細説明
5. 確認方法
6. 失敗時の見方や関連文書

すべての文書にこの形を強制する必要はありません。ただし、手順文書では「何を変更するか」と「成功確認」を早めに示し、設計文書では「なぜその設計か」を手順より前に置きます。

構造を見直すときは、次を確認します。

- 最初の数段落で、その文書を読むべきか判断できる
- 手順と設計理由が混ざりすぎていない
- 重要な注意点が手順の後ろに埋もれていない
- 表や箇条書きが、比較や選択を助けている
- 長いコマンド列の前後に、目的と期待結果がある
- 関連文書へのリンクが、読む順番を示している

## Section Design

セクションは、読者の作業単位または判断単位で分けます。単に文章量が増えたから見出しを足すのではなく、読者が「ここだけ読めばよい」と判断できる単位にします。

セクションを作るときは、次を確認します。

- Heading: 見出しだけで内容と目的が分かる
- Scope: セクション内の内容が見出しから外れていない
- Order: 前提、手順、確認、補足の順序が自然である
- Depth: 見出し階層が深くなりすぎていない。原則として `##` と `###` で足りる
- Length: 長すぎるセクションは、作業単位で分けるか表にする
- Cross Links: 別文書の正本がある内容は、要約してリンクする
- Stability: 頻繁に変わる値やコマンドを、設計判断の文章に埋め込んでいない

削除や統合も品質改善です。次の状態なら、セクションを減らすことを検討します。

- 見出しが違うだけで同じ内容を説明している
- セクション単体では判断や作業に使えない
- 直前または直後のセクションと境界を説明できない
- 箇条書きが増えた結果、優先順位や流れが読めなくなっている

## Content Fitness

内容は、正確さだけでなく、その文書の目的に合っているかで評価します。

追加する前に確認すること:

- Necessity: その情報は読者の判断や作業に必要か
- Specificity: 一般論ではなく、このプロジェクトの事実や判断に結びついているか
- Freshness: バージョン、外部サービス仕様、コマンド出力など、変わりやすい情報を固定しすぎていないか
- Verification: 読者が成功・失敗を確認できるか
- Risk: 本番、認証情報、外部API、長時間処理に関わる注意があるか
- Maintenance Cost: 将来変更されたとき、更新箇所が多すぎないか
- Human Readability: 文章が自然で、読む順番が明確か

削るべき内容:

- 既存文書へのリンクで足りる重複説明
- 現在の実装と関係しない過去の作業ログ
- 個人の環境に依存する値や手順
- 「念のため」に増えたが、読者の行動を変えない注意書き
- 古い構成や後方互換の説明で、現在の運用判断に不要なもの

## Evidence And Verification

重要な記述には、読者が確認できる根拠か検証方法を添えます。根拠は長く引用する必要はありません。コード上のモジュール、CLI、テスト、API、運用スクリプトのどれに対応するかが分かれば十分です。

確認方法の例:

- CLI仕様: `--help`、該当テスト、`docs/cli-reference.md`
- API仕様: Worker test、`docs/web-api.md`、代表 `curl`
- DB schema: migration / schema 定義、`docs/data-model.md`
- Cloudflare構成: Terraform plan、Wrangler output、Dashboardで見る場所
- UI仕様: frontend build、画面上の操作、`docs/frontend-ui.md`

外部サービスの仕様、バージョン、価格、Dashboard UI の場所など変わりやすい情報を書く場合は、最終確認日や「変更される可能性がある」ことを必要に応じて明記します。

## Examples

弱い記述:

```text
D1に反映する。
```

改善例:

```text
既存SQLiteからD1用SQLを生成し、staging D1へ投入します。この操作はproduction D1を変更しません。
```

弱い記述:

```text
エラーが出たら設定を確認する。
```

改善例:

```text
`database_ready:false` の場合は、D1投入失敗、metadata不足、schema version不一致、またはWorkerのD1 binding違いを疑います。まず `/health` と代表検索を確認し、次にWorker logsとD1 metricsを見ます。
```

弱い記述:

```text
必要ならこのファイルを編集する。
```

改善例:

```text
`cloudflare/worker/wrangler.toml` はignore対象の実設定です。Terraform state がある場合は手編集せず、`python3 tools/generate_wrangler_toml.py` で再生成します。
```

## Data Flow

複数のデータストアや環境が出てくる手順では、source of truth とデータの流れを明示します。

このプロジェクトでは、生成済み曲データの source of truth はローカル SQLite です。local D1 はローカル Worker の検証用、staging D1 と production D1 は公開環境へ配布されたコピーです。

手順を書くときは、操作対象を曖昧にしないでください。

- local SQLite を生成する
- local D1 に投入する
- staging D1 に投入する
- production D1 に投入する
- Worker / Pages を deploy する
- Terraform state に import する
- 変更せずに検証だけ行う

## Commands

コマンドは、原則としてリポジトリルートから実行できる形で書きます。別ディレクトリで実行する必要がある場合は、作業ディレクトリが残らない subshell を使います。

```bash
(cd frontend && yarn build)
```

長時間常駐するコマンドは、どのターミナルを開いたままにするかを明記します。状態を変更するコマンドの前には、何を変更し、何を変更しないかを書きます。

セットアップ、deploy、D1投入、Terraform apply の後には、最小限の確認コマンドと期待する結果を書きます。

Node.js ツールは、リポジトリで固定した依存関係を使う書き方を優先します。`npx wrangler` のように実行時にnpm側の解決へ寄る書き方は、意図しないバージョンやネットワーク取得につながるため避けます。

Wrangler を直接呼ぶ必要がある場合は、`cloudflare/worker` に入ってから `./node_modules/.bin/wrangler` を使うか、既存の `tools/deploy_cloudflare.sh` / `tools/update_d1.sh` を使います。日常手順では、まず wrapper script を案内し、低レベルな Wrangler コマンドは手動復旧や確認が必要な箇所だけに置きます。

## Terminology

用語は文書間で揺らさないでください。

| 使う語 | 意味 |
| --- | --- |
| `投入` | 生成済み曲データをD1へ流し込むこと |
| `Terraform import` | 既存Cloudflare resourceをTerraform stateへ取り込むこと |
| `deploy` | Worker script や Pages artifact をCloudflareへ公開すること |
| `生成` | D1 SQL や `wrangler.toml` などの派生ローカルファイルを書き出すこと |
| `staging D1`, `production D1`, `Cloudflare上のD1` | 対象環境が分かるD1の呼び方 |

避ける表現:

- `remote D1`: 対象が staging か production か分からない
- `D1 import`: Terraform import と混同しやすい。D1へデータを入れる場合は `投入` と書く
- `反映`: 便利だが曖昧。deploy、投入、生成、apply のどれかを選ぶ

## Section Names

見出しは、読者が内容を予測できる具体的な名前にします。

避けたい例:

- Notes
- Checks
- Boundary
- Other

好ましい例:

- Operational Notes
- Health Checks
- Terraform Scope
- Document Boundaries
- Runtime Read-Only Access
- Local Dev Server
- D1 Update Workflow

見出しを変えた場合は、古いアンカーへのリンクが残っていないか確認します。

## Japanese Writing Style

ユーザー向け・保守者向けの文書は、自然で平易な日本語で書きます。英語を直訳したような文ではなく、日本語として読みやすい文に直します。

- 一般的で誤解の少ない日本語がある場合は、それを優先する
- `Worker`, `D1`, `binding`, `deploy`, `staging`, `production` など、製品名やコマンド概念は無理に訳さない
- 主語と対象を明確にする。特に状態を変えるコマンドでは、何が何を更新するのかを書く
- 長い説明は短い段落に分ける
- 「なぜ」「手順」「注意点」「確認」など、読み手の行動に沿った見出しを使う
- 「投入」「生成」「deploy」「Terraform import」など、意味の違う語を混ぜない
- 長く残る文書ではくだけすぎた表現を避ける
- 不自然な日本語は、元の文に引きずられず書き直す

推敲例:

| 避ける表現 | 改善例 | 理由 |
| --- | --- | --- |
| `DBのimportを行う` | `SQLiteから生成したSQLをD1へ投入する` | import と投入を混ぜない |
| `これを実行すると反映されます` | `このコマンドはstaging D1のデータを更新します` | 何が変わるかを書く |
| `適切に設定してください` | `CNAME target が staging branch alias を指すことを確認します` | 読者の行動にする |
| `必要に応じて確認します` | `productionへ進む前に /health と代表検索を確認します` | 条件と確認対象を明確にする |
| `エラーになります` | `APIは 503 を返し、画面ではDB未準備として扱います` | 結果と影響を書く |

見出し例:

| 避ける見出し | 改善例 |
| --- | --- |
| `Notes` | `Operational Notes` |
| `Other` | `Manual Recovery` |
| `Settings` | `Cloudflare DNS Records` |
| `Deploy` | `Application Deploy` |
| `DB` | `Database Update` |
| `Check` | `Health Checks` |

このプロジェクトで迷いやすい見出し:

| 避ける見出し | 改善例 | 理由 |
| --- | --- | --- |
| `Cloudflare` | `Cloudflare DNS And Routes` | Pages、Worker、D1、DNSのどれか分からない |
| `D1` | `D1 Update Verification` | schema、投入、検証のどれか分からない |
| `Local` | `Local Dev Server` | DB構築、local D1、Vite起動が混ざる |
| `Metadata` | `Video Metadata Refresh` または `GET /api/metadata` | 動画メタデータとDB metadataを区別する |
| `Production` | `Production Readiness Checklist` | 設計判断か操作前確認か分からない |

## Red Flags

次の兆候がある場合は、文章の微修正ではなく構成を見直します。

- README が詳細手順で長くなり、入口として読みにくい
- 同じコマンド列が複数文書にある
- `staging` と `production` の影響範囲が同じ段落で曖昧になっている
- `import`, `export`, `反映`, `更新` が混在し、実際の操作が分からない
- 見出しが `Notes`, `Other`, `Misc` のように内容を示していない
- 手順に成功確認がない
- 失敗時に見るべきログ、API、テスト、Dashboardが書かれていない
- 個人環境の値や実ドメインが例として残っている
- 古い実装や削除済み機能の説明が、現在の推奨手順と同じ重みで残っている
- 文書の読者が途中で変わる。例: 初心者向け手順の途中にTerraform設計判断が入る

## Backlog Item Size

backlog項目は、1回の小さな編集で完了できる粒度にします。

| 粒度 | 例 | 判断 |
| --- | --- | --- |
| 大きすぎる | `ドキュメントを全部改善する` | 領域別に分割する |
| ちょうどよい | `operations.md にproduction前チェックリストを追加する` | そのまま扱う |
| 小さすぎる | `読点を1つ直す` | 近い文書改善にまとめる |

よいbacklog項目は、ID、Owner、対象文書、依存関係、改善内容、完了条件、検証方法が分かります。

ドキュメントだけで完結する改善は [documentation-improvement-backlog.md](documentation-improvement-backlog.md) に置きます。コード、API、UI、運用ツールの変更を伴うものは [development-backlog.md](development-backlog.md) に置きます。

完了した項目は `Done` にします。変更内容が安定し、正本文書から追えるようになったら削除して構いません。

## Privacy

ドキュメントには、実在の個人情報、運用情報、認証情報を書きません。例ではプレースホルダーを使います。

| 種類 | 表記例 |
| --- | --- |
| ドメイン | `staging.vocaloid-title-search.example.com`, `vocaloid-title-search.example.com` |
| origin IP | `203.0.113.10` |
| メールアドレス | `user@example.com` |
| Cloudflare ID | `replace-with-...` |

`example.com` と `203.0.113.0/24` はドキュメント用に予約された値です。

## Final Review

ドキュメント変更の最後に確認します。

短い確認:

- 正しい文書に書いた
- 影響範囲と確認方法がある
- 実値やsecretがない
- 用語が揺れていない
- リンクが壊れていない

詳細確認:

- 現在のコード、CLI、API、運用スクリプトと矛盾していない
- 新しいコマンドに、実行場所と変更対象が書かれている
- staging / production 操作に確認手順がある
- local-only 操作が production に影響するように読めない
- 見出し名から内容を予測できる
- ファイル配置、文書構造、セクション分割が [docs/README.md](README.md) の境界と矛盾していない
- 新しい文書やセクションが、既存文書への統合ではなく分離すべき理由を説明できる
- 手順、設計判断、API仕様、運用runbookが不自然に混ざっていない
- 重要な記述に、確認方法または対応するコード・テスト・運用手順への導線がある
- 同じ手順を複数文書へ重複して書いていない
- 古いアンカーや移動前のリンクが残っていない
- 個人情報、実ドメイン、実IP、Cloudflare ID、API token が入っていない
- 用語揺れがない

用語揺れは次のように確認できます。`docs/documentation-quality.md` には避ける表現の例が含まれるため、検索対象から外します。

```bash
rg -n "remote D1|D1 import|D1 export|反映" README.md docs AGENTS.md \
  --glob '!docs/documentation-quality.md'
```

秘匿情報の混入は次のスクリプトで確認します。

```bash
python3 tools/check_sensitive_values.py
```
