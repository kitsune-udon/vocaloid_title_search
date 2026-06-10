# Detail Extraction Algorithm

この文書は、`vocaloid_title_search/detail.py` の詳細抽出ヒューリスティックを説明します。APIレスポンスの形や運用上の前提は [detail-extraction.md](detail-extraction.md) を参照してください。

## Reader Shortcuts

| 調べたいこと | 読むセクション |
| --- | --- |
| 失敗例から見る | Common Failure Patterns |
| 公開年がおかしい | Published Year |
| 作詞・作曲・動画などの基本情報がおかしい | Credits, Credits State Machine |
| 曲紹介や読みがおかしい | Reading, Introduction |
| 通常動画と関連動画の分離がおかしい | Videos, Video State Machine |
| 仕様上できないことを確認したい | Limitations |

新しい不具合を調べるときは、まず Common Failure Patterns で近い症状を探し、該当する抽出セクションと代表テストへ進みます。

## Test Map

代表的な回帰テストは `tests/test_detail_extraction.py` と `tests/test_video_metadata.py` に置きます。

| 領域 | 代表テスト |
| --- | --- |
| 公開年タグ | `test_extracts_published_year_from_wiki_tag_links` |
| 括弧内区切り文字 | `test_keeps_separators_inside_parentheses` |
| 複数行の括弧注記 | `test_joins_multiline_parenthetical_note` |
| リンク注記除去 | `test_drops_link_notes_but_keeps_meaningful_notes`, `test_drops_split_link_notes` |
| 参照注記・別版セクションの停止 | `test_stops_at_reference_note`, `test_stops_at_alternate_version_subsection`, `test_stops_at_reloaded_subsection` |
| `映像` / `Movie` などの動画ラベル | `test_treats_visual_label_as_video`, `test_does_not_treat_movie_editor_as_primary_video_credit` |
| 読み抽出 | `test_extracts_reading_from_title_with_parentheses`, `test_does_not_treat_title_parentheses_as_reading` |
| 通常動画と関連動画の分離 | `test_main_links_are_related_videos_not_primary_videos`, `test_excludes_english_version_section_from_primary_videos` |
| 動画メタデータ更新 | `test_collect_video_ids_deduplicates_ids`, `test_apply_video_metadata_updates_all_video_sections` |

新しいヒューリスティックを追加する場合は、実ページHTML全体ではなく、失敗を再現する最小HTMLでテストします。

## Common Failure Patterns

| 症状 | 主に見る処理 | 代表テスト |
| --- | --- | --- |
| `feat.` や `&` の前後が分割される | 値の結合 | `test_joins_credit_connector_lines`, `test_joins_feat_continuation_line` |
| `Movie Editor` など詳細職種を動画担当として拾いすぎる | 英字ラベル完全一致 | `test_does_not_treat_movie_editor_as_primary_video_credit` |
| `Twitter`, `HP`, `公式サイト` などが作者名に混ざる | リンク注記除去 | `test_drops_link_notes_but_keeps_meaningful_notes` |
| 英語版など別版動画が通常動画に混ざる | 動画対象セクション除外 | `test_excludes_english_version_section_from_primary_videos` |
| 読みではない括弧が読みとして表示される | 読み抽出 | `test_does_not_treat_title_parentheses_as_reading` |
| `映像` が動画クレジットとして拾われない | ラベル対応表 | `test_treats_visual_label_as_video` |
| 本文リンクが通常動画に混ざる | 通常動画と関連動画の分離 | `test_main_links_are_related_videos_not_primary_videos` |
| 別版やRemixの基本情報が本家曲に混ざる | 別版サブセクション停止 | `test_stops_at_alternate_version_subsection` |

実ページ由来の回帰例を追加する基準:

- 同じ症状を最小HTMLで再現できる
- ページ名に依存せず、構造や表記揺れの問題として説明できる
- 既存ヒューリスティックの副作用を確認できる
- 実ページの長いHTMLをfixtureにせず、必要な見出し、行、リンクだけを残す

## Page Title

`extract_page_title()` は HTML の `<title>` からページ名を取得します。

- 末尾の `- 初音ミク Wiki ...` は削除します。
- `<title>` がない場合は空文字列を返します。

## Reading

`extract_reading()` は最後に出現する `曲紹介` 見出しの直後から、`曲名：` を含むテキストを探します。

対応している主な形式:

```text
曲名：『下剋上(完)』（げこくじょう(かん)）
曲名：『絵本『人柱アリス』』（えほん『ひとばしらアリス』）
曲名：メルト（めると）
```

`曲名：『モニタリング (Best Friend Remix)』` のように、曲名内の括弧だけで読みが書かれていない場合は読みとして扱いません。

## Published Year

`extract_published_year()` は曲詳細ページ内のタグリンクから公開年を取得します。

- リンク文字列が `YYYY年` に完全一致するものだけを候補にします。
- リンク先 href に `/hmiku/tag/` を含むものだけを対象にします。
- 年は `2004` から `2100` の範囲だけを採用します。
- 複数の年タグがある場合は最も古い年を返します。

DB構築時に `YYYY年` タグページを全巡回する方式は、対象外の曲まで大量に取得してしまうため使いません。曲詳細ページHTMLを取得したついでに公開年を保存します。

## Credits

`extract_credits()` はページ本文を行単位に正規化し、基本情報らしい範囲から `credits` を作ります。

抽出範囲:

- 先頭は、最初に見つかった基本情報ラベル行です。
- 末尾は、基本情報ラベルを見た後に出てくる `曲紹介` 行です。
- `曲紹介` が見つからない場合は、ページ末尾までを候補にします。

対応ラベル:

| Wiki label | JSON key |
| --- | --- |
| `作詞` | `lyricist` |
| `作曲` | `composer` |
| `編曲` | `arranger` |
| `唄` | `vocalist` |
| `絵`, `イラスト`, `Illust`, `Illustration`, `Illustrator` | `illustrator` |
| `動画`, `動画制作`, `映像`, `映像制作`, `MV`, `PV`, `Movie` | `video` |
| `調声` | `tuning` |

ラベルは `:` または `：` で値と分けます。`作詞・作曲：...` のような複合ラベルは、該当する複数の JSON key に同じ値を登録します。
`イラスト`, `動画`, `映像`, `Movie` のような一部のラベルは、コロンなしの単独行でも項目境界として扱います。

ラベルを追加する判断基準:

- 複数ページで同じ意味として使われている
- 既存ラベルでは取りこぼすが、詳細職種名を拾いすぎない
- 英字ラベルは原則として完全一致にする
- 追加時は、拾える例と拾わない例を両方テストする

## Credits State Machine

基本情報抽出は、HTML の表ではなく、正規化済みテキスト行に対する状態機械として動きます。

```text
lines = useful_lines(soup.get_text("\n"))
end = first "曲紹介" after at least one credit label
start = first credit label before end
section_lines = lines[start:end]

index = 0
while index < len(section_lines):
    label, inline_value = split at first ":" or "："
    fields = map label to JSON keys
    if fields is empty:
        index += 1
        continue

    values = split_credit_text(inline_value)
    index += 1

    while index is inside section_lines:
        if current line is another label and current values do not have an open parenthesis:
            break
        if current line is "曲紹介", "歌詞", "関連動画", "コメント":
            break
        values += split_credit_text(current line)
        index += 1

    normalized = normalize_credit_values(values)
    append normalized values to every field in fields
```

ラベル判定:

- `split_credit_label()` は最初の `:` または `：` だけで分割します。
- `credit_field_names()` はラベル内の括弧注記を削ってから、`・`, `、`, `,`, `/`, `／` で分割します。
- 分割後の各要素が対応ラベル表のいずれかで始まれば、その JSON key に対応させます。
- コロンなし単独行の場合は、`イラスト`, `動画`, `映像`, `Movie` など、対応ラベルそのものと一致する場合だけ項目境界として扱います。
- `Movie`, `MV`, `PV`, `Illust`, `Illustration`, `Illustrator` などの英字ラベルは完全一致した場合だけ対応ラベルとして扱います。
- `Movie Editor` や `Logo Designer` のような詳細スタッフ職種は、基本情報の `video` / `illustrator` には含めません。
- `作詞・作曲：Naka-Dai` は `lyricist` と `composer` の両方に `Naka-Dai` を入れます。
- `Illustration・MV：担当者` は `illustrator` と `video` の両方に `担当者` を入れます。
- `Animation Coordinator：...` のように `Animation` が複合職種名の一部として出るケースは、誤分類を避けるため `video` ラベルとしては扱いません。

値分割:

- `、`, `,`, `・`, `/`, `／` で分割します。
- ただし、括弧内の区切り文字は分割しません。
- 例: `稲葉曇（リズム、ベース、その他）・Neru（ギター、その他）` は 2 人として扱います。

値分割の括弧深度:

```text
buffer = ""
paren_depth = 0
for char in value:
    if char is "(" or "（":
        paren_depth += 1
    if char is ")" or "）" and paren_depth > 0:
        paren_depth -= 1
    if paren_depth == 0 and char is a separator:
        emit buffer
        clear buffer
    else:
        append char to buffer
emit remaining buffer
```

値の結合:

- `GYARI（`, `ココアシガレットP`, `）` のように括弧付き注記が複数行に割れた場合は結合します。
- `BUMP OF CHICKEN`, `&`, `MOR` のように `&` / `＆` が独立行になった場合は前後を結合します。
- `BUMP OF CHICKEN feat.`, `HATSUNE MIKU` のように `feat.` / `featuring` の後続が改行された場合は結合します。
- `GUMI（調声：スズム(*1)）` のような意味のある括弧注記は保持します。

除去する値:

- 空値
- `・`
- `原曲`
- `関連動画`
- `詳細`
- `Best Friend Remix`
- `... Remix` で終わる単独値
- 日付だけの値
- `※` で始まる参照注記以降の値
- `+` または `＋` が出た場合は、詳細スタッフ欄の開始とみなし、その項目の値取り込みをそこで止める
- `+` または `＋` の直後が `Remix`, `RMX`, `Reloaded`, `ver.`, `Ver.`, `版` で終わる見出しの場合は、別版サブセクションの開始とみなし、以降の基本情報を取り込まない

除去するリンク注記:

- `(Twitter)`, `（Twitter）`
- `(X)`, `X(Twitter)`
- `(Instagram)`, `(TwitterInstagram)`
- `(ホームページ)`, `(HP)`, `(公式サイト)`, `(site)`
- `(YouTube)`, `(ニコニコ動画)`, `(ニコニコ)`, `(piapro)`, `(pixiv)`, `(FANBOX)`, `(skeb)`

リンク注記だけが括弧で後続行に分かれている場合も捨てます。たとえば `暗闇まよい`, `（`, `X(Twitter)`, `）` は `暗闇まよい` になります。
`ののこ（TwitterpixivFANBOXsite）` や `うぐいす工房（TwitterYouTubeHP）` のように、複数リンク名が詰まっている場合もリンク注記として除去します。

一方で、以下は意味のある注記として保持します。

```text
GUMI（調声：スズム(*1)）
KIKKUN-MK-Ⅱ（M.S.S Project）
よだ（與田）
Naoki Itai(MUSIC FOR MUSIC)
```

別版サブセクション:

- `+ CPK! Remix`, `+ セカイver.`, `+ Reloaded` のような別版サブセクションは、本家曲の基本情報に混ぜないため、基本情報抽出全体をそこで終了します。
- `英語版` のような別版セクション内の動画は、本家曲の通常動画に混ぜないため動画抽出対象から除外します。
- OTOIRO などのサブセクションの詳細スタッフは、基本情報の `credits` には含めません。

## Introduction

`extract_introduction()` は `曲紹介` セクションから本文を抽出します。

- HTML 見出しとして `曲紹介` が見つかる場合は、その次の `ul`, `ol`, `blockquote`, `div`, `p` を候補にします。
- 次の見出しが出たらセクション終了とみなします。
- 見出し構造で取れない場合は、行単位のフォールバック抽出を使います。
- `曲名：`, `作詞：`, `作曲：`, `唄：`, `歌詞`, `関連動画`, `コメント` などの断片は本文から除外します。
- 最大 8 件まで返します。

## Videos

`extract_videos()` は HTML 内のニコニコ動画 ID と YouTube ID を抽出します。

ニコニコ動画:

- `nicovideo.jp/watch/sm123`
- `ext.nicovideo.jp/thumb/sm123`
- `sm`, `nm`, `so` で始まる ID に対応します。
- 詳細抽出時は外部メタデータを取得せず、タイトルは `ニコニコ動画 <id>`、サムネイルはIDから作れる候補URLを入れます。
- ニコニコ動画は動画によってサムネイルURL形式が揺れるため、`thumbnail_urls` に `.L`, `.M`, suffixなしの候補を入れます。フロントエンドは読み込み失敗時に次の候補へ切り替えます。

YouTube:

- `youtube.com/watch?v=...`
- `youtube.com/embed/...`
- `youtu.be/...`
- 11 文字の動画 ID に対応します。
- 既定ではタイトルを `YouTube <id>` とし、サムネイル URL を `https://img.youtube.com/vi/<id>/mqdefault.jpg` にします。

`videos` と `related_videos` の分離:

- `videos` は `関連動画` 見出しより前にある埋め込み `iframe` の動画です。
- `related_videos` は本文中の動画リンクと、`関連動画` セクション内の動画です。
- ID は重複排除し、ページ内で先に見つかった順を保ちます。

## Video State Machine

動画抽出は HTML 構造解析と正規表現を組み合わせます。

```text
soup = clean_soup(page_html, remove_media=False)
related_heading = last heading whose text is "関連動画"

if related_heading exists:
    related_html = HTML of siblings after related_heading until next same-or-higher-level heading
    remove related_heading and related nodes from soup
    main_html = str(soup)
else:
    main_html = page_html
    related_html = ""

videos = extract iframe videos from main_html
related_videos = extract link videos from main_html + extract all videos from related_html
```

`remove_media=False` にしている理由は、Wiki の動画埋め込みが `iframe` に入っていることがあるためです。通常の本文抽出では `iframe` はノイズとして消しますが、動画抽出時だけは URL を保持します。

通常動画は Wiki 上で動画プレイヤーとして表示される埋め込み `iframe` に限定します。`曲紹介` など本文中の動画リンクは、ページ上ではプレイヤーとして表示されないため `related_videos` に入れます。
`関連動画` が `h3` で、その下に `h4` の小見出しがある場合、`h4` は関連動画セクション内の小見出しとして扱います。次の `h3` や `h2` など、同じ階層以上の見出しが出たところで関連動画セクションを終了します。

ID 抽出:

- ニコニコ動画は `nicovideo.jp/watch/` または `ext.nicovideo.jp/thumb/` の後ろにある `sm123`, `nm123`, `so123` を拾います。
- YouTube は `watch?v=`, `embed/`, `youtu.be/` の後ろにある 11 文字 ID を拾います。
- 同じ ID が複数回出ても `unique()` で 1 回だけ返します。

メタデータ取得:

- DB構築時の詳細抽出では動画メタデータを取得しません。
- 必要な場合は `python -m vocaloid_title_search.cli.refresh_video_metadata` が既存DB内のユニークな動画IDを集め、ニコニコ `getthumbinfo` XML と YouTube oEmbed JSON から `title` と `thumbnail_url` を読み、`song_details.payload_json` に書き戻します。
- メタデータ取得関数は `lru_cache(maxsize=512)` でプロセス内メモ化します。

## Limitations

この抽出は初音ミク Wiki の実ページ構造に合わせたヒューリスティックです。

- Wiki ページの表記揺れが大きい場合、基本情報の境界を誤る可能性があります。
- 作者名そのものに `/`, `・`, `、` などがトップレベルで含まれる場合は分割される可能性があります。
- 読みは `曲紹介` 内の `曲名：...` 形式を優先します。別形式の読みは取得しないことがあります。
- 動画タイトルとサムネイルは動画メタデータ更新CLI実行時の外部 API 取得に依存するため、その時点のネットワーク失敗時はフォールバック値のままDBに残ります。

直すべきでない可能性がある揺れ:

- Wiki本文の自由記述をすべて構造化しようとすること
- 1ページだけの特殊表記を広すぎる正規表現で拾うこと
- 作者名の一部である記号を一般の区切り文字として扱うこと
- 関連動画リンクを通常動画へ昇格させること
