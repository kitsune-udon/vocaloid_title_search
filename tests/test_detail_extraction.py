import unittest
from unittest.mock import patch

from vocaloid_title_search.detail import (
    clean_soup,
    extract_published_year,
    extract_reading_from_text,
    extract_credits,
    extract_videos,
    merge_video_maps,
    normalize_credit_values,
    remove_link_notes,
    remove_excluded_video_sections,
    split_video_sections,
    split_credit_text,
)


class CreditNormalizationTests(unittest.TestCase):
    def test_verified_unlinked_compound_name_preserves_its_internal_separator(self):
        soup = clean_soup('<p>作詞：<a>LOLI.COM</a>、タケ・ヨシキ、'
                          'DA-MAZING（米田紳一郎）</p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {
            'lyricist': ['LOLI.COM', 'タケ・ヨシキ', 'DA-MAZING（米田紳一郎）'],
        })

    def test_staff_table_heading_is_not_a_video_person(self):
        soup = clean_soup('<p>編曲：作者</p><table class="atwiki_plugin_region"><tr><td>+</td><td>動画</td>'
                          '<td><div>動画担当</div><div>監督：別担当<br>動画：担当A・担当B</div></td>'
                          '</tr></table><p>唄：音声A</p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {
            'arranger': ['作者'], 'video': ['担当A', '担当B'], 'vocalist': ['音声A'],
        })

    def test_personal_website_note_is_removed_without_dropping_identity_note(self):
        self.assertEqual(remove_link_notes('作者（X / 個人サイト）'), '作者')
        self.assertEqual(remove_link_notes('作者（公式HP）'), '作者')
        self.assertEqual(remove_link_notes('作者（サイト音楽研究所）'), '作者（サイト音楽研究所）')

    def test_spaced_ascii_role_colon_does_not_extend_previous_person(self):
        soup = clean_soup('<p>Illustration : <a>作者</a><br>'
                          'Movie Direction : 別担当<br>唄：音声A</p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {'illustrator': ['作者'], 'vocalist': ['音声A']})

    def test_named_reissue_credit_label_is_not_main_credit(self):
        soup = clean_soup('<p>作曲：作者<br>調声（Re:Test Song）：別版担当<br>'
                          '唄：音声A</p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {'composer': ['作者'], 'vocalist': ['音声A']})

    def test_song_vocal_label_does_not_match_lyric_translation_role(self):
        soup = clean_soup('<p>作曲：作者<br>歌詞英訳：翻訳者<br>'
                          '歌：<a>GUMI English</a></p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {'composer': ['作者'], 'vocalist': ['GUMI English']})

    def test_standalone_version_group_is_not_a_note_on_previous_person(self):
        soup = clean_soup('<p>編曲：作者A</p><div>(ニコニコ動画版)<br>'
                          '絵・動画：作者B</div><div>(YouTube版)<br>'
                          '絵：作者C<br>唄：音声A</div><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {
            'arranger': ['作者A'], 'illustrator': ['作者B', '作者C'],
            'video': ['作者B'], 'vocalist': ['音声A'],
        })

    def test_arbitrary_section_heading_ends_credits(self):
        soup = clean_soup('<p>唄：<a>音声A</a></p><h3>音楽配信</h3>'
                          '<table><tr><td>前作</td><td>次作</td></tr></table>'
                          '<h3>歌詞</h3>')
        self.assertEqual(extract_credits(soup), {'vocalist': ['音声A']})

    def test_ideographic_space_separates_inline_credit_roles(self):
        soup = clean_soup('<p>作詞：<a>Author Name</a>　英語翻訳：翻訳担当<br>'
                          '唄：<a>音声A</a></p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {'lyricist': ['Author Name'], 'vocalist': ['音声A']})

    def test_natural_language_credit_label_is_not_a_name(self):
        soup = clean_soup('<p>絵：背景担当<br>イラストと衣装デザインを <a>作者A</a>・作者B<br>'
                          '作画監督：別担当<br>唄：音声A</p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {
            'illustrator': ['背景担当', '作者A', '作者B'], 'vocalist': ['音声A'],
        })

    def test_named_edit_subsection_and_version_label_do_not_extend_main_credits(self):
        for html in ('<p>唄：音声A<br>唄（Re:boot）：音声B</p><h3>曲紹介</h3>',
                     '<p>唄：音声A<br>+<br>Festival 10th edit<br>'
                     '編曲：別版担当</p><h3>曲紹介</h3>'):
            with self.subTest(html=html):
                self.assertEqual(extract_credits(clean_soup(html)), {'vocalist': ['音声A']})

    def test_colon_in_role_annotation_is_not_the_value_delimiter(self):
        soup = clean_soup('<p>作曲：作者<br>絵(0:50頃)：<a>担当者</a><br>'
                          '動画（別版 1:20）：<a>映像担当</a></p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {
            'composer': ['作者'], 'illustrator': ['担当者'], 'video': ['映像担当'],
        })

    def test_linked_colon_name_is_not_an_unknown_role(self):
        soup = clean_soup('<p>絵：<a>７：２４</a>・<a>すたじお：検証</a></p>'
                          '<h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {'illustrator': ['７：２４', 'すたじお：検証']})

    def test_credit_tokens_cannot_collide_with_source_text(self):
        name = '\ue000credit0\ue001'
        soup = clean_soup(f'<p>作曲：{name}・<a>作者・別名</a></p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {'composer': [name, '作者・別名']})

    def test_inline_links_preserve_name_prefixes_and_internal_separators(self):
        soup = clean_soup('<div>作曲：<a>作者・別名</a><br>'
                          '唄：黒い<a>検証音声</a>、白い<a>検証音声</a>、'
                          'VOICEVOX<a>別音声</a>、<a>名前・後半</a></div><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {
            'composer': ['作者・別名'],
            'vocalist': ['黒い検証音声', '白い検証音声', 'VOICEVOX別音声', '名前・後半'],
        })

    def test_halfwidth_delimiters_split_people_but_preserve_parenthetical_lists(self):
        soup = clean_soup('<p>唄：<a>音声A</a>(方式A･方式B)､<a>音声B</a>･'
                          '<a>名前･後半</a></p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {
            'vocalist': ['音声A(方式A･方式B)', '音声B', '名前･後半'],
        })

    def test_unknown_inline_role_does_not_extend_preceding_credit(self):
        soup = clean_soup('<p>絵・動画：検証作者<br>'
                          'スペシャルサンクス：協力者<br>唄：検証音声</p><h3>曲紹介</h3>')
        self.assertEqual(extract_credits(soup), {
            'illustrator': ['検証作者'], 'video': ['検証作者'], 'vocalist': ['検証音声'],
        })

    def test_credits_stop_before_lyrics_and_comments_without_introduction(self):
        soup = clean_soup('<nav>歌詞<br>コメント</nav>'
                          '<p>作曲：検証作者<br>唄：検証音声</p>'
                          '<h3>歌詞</h3><p>歌詞本文</p>'
                          '<h3>コメント</h3><p>絵：コメント内の感想</p>')
        self.assertEqual(extract_credits(soup),
                         {'composer': ['検証作者'], 'vocalist': ['検証音声']})

    def test_video_urls_support_numeric_ids_and_query_order_without_false_hosts(self):
        html = ('<iframe src="https://ext.nicovideo.jp/thumb/1266843314"></iframe>'
                '<a href="https://www.youtube.com/watch?feature=share&amp;v=abcdefghijk">video</a>'
                '<a href="https://example.test/nicovideo.jp/watch/sm123">wrong host</a>'
                '<a href="https://www.nicovideo.jp/watch/sm123bad">wrong ID</a>')
        result = extract_videos(html)
        self.assertEqual([v['id'] for v in result['niconico']], ['1266843314'])
        self.assertEqual([v['id'] for v in result['youtube']], ['abcdefghijk'])

    def test_explicit_introduction_preserves_short_sentences(self):
        from vocaloid_title_search.detail import extract_introduction
        for text in ("捧ぐ", "息が止まる", "さよなら。"):
            with self.subTest(text=text):
                soup = clean_soup(f'<h3>曲紹介</h3><blockquote>{text}</blockquote>'
                                  '<p>曲名：『検証曲』</p><h3>歌詞</h3><p>歌詞を混ぜない。</p>')
                self.assertEqual(extract_introduction(soup), [text])

    def test_song_content_heading_preserves_description_and_boundaries(self):
        from vocaloid_title_search.detail import extract_introduction
        soup = clean_soup('<p>作曲：検証作者</p><h3>曲の内容</h3>'
                          '<p>曲名：『検証曲』</p><ul><li>逆再生で聞き取れる作品。</li></ul>'
                          '<h3>歌詞</h3><p>歌詞本文は含めない。</p>')
        self.assertEqual(extract_introduction(soup), ['逆再生で聞き取れる作品。'])
        self.assertEqual(extract_credits(soup), {'composer': ['検証作者']})

    def test_overview_heading_is_an_introduction_boundary(self):
        from vocaloid_title_search.detail import extract_introduction
        soup = clean_soup("""
            <div>作詞：<a>検証作者</a><br>作曲：<a>検証作曲者</a></div>
            <h3>概要</h3><div>曲名：『検証曲』</div>
            <ul><li>合成音声を使った検証用の楽曲。</li><li>二作目として公開された作品。</li></ul>
            <h3>歌詞</h3><p>紹介へ混ぜない歌詞の本文。</p>
        """)
        self.assertEqual(extract_credits(soup), {"lyricist": ["検証作者"], "composer": ["検証作曲者"]})
        self.assertEqual(extract_introduction(soup), ["合成音声を使った検証用の楽曲。", "二作目として公開された作品。"])

    def test_extracts_published_year_from_wiki_tag_links(self) -> None:
        html = """
        <html><body>
          <a href="/hmiku/tag/2012%E5%B9%B4">2012年</a>
          <a href="/hmiku/tag/%E6%AE%BF%E5%A0%82%E5%85%A5%E3%82%8A">殿堂入り</a>
          <a href="/other/tag/2011%E5%B9%B4">2011年</a>
        </body></html>
        """
        self.assertEqual(extract_published_year(clean_soup(html)), 2012)

    def test_keeps_separators_inside_parentheses(self) -> None:
        self.assertEqual(
            split_credit_text("稲葉曇（リズム、ベース、その他）・Neru（ギター、その他）"),
            ["稲葉曇（リズム、ベース、その他）", "Neru（ギター、その他）"],
        )

    def test_joins_multiline_parenthetical_note(self) -> None:
        self.assertEqual(
            normalize_credit_values(["初音ミク", "（新録、調声：", "胡虎あくび", "）"]),
            ["初音ミク（新録、調声：胡虎あくび）"],
        )

    def test_drops_link_notes_but_keeps_meaningful_notes(self) -> None:
        self.assertEqual(
            normalize_credit_values(
                [
                    "津田（TwitterInstagram）",
                    "可不",
                    "（CeVIO AI）",
                    "Naoki Itai",
                    "（Twitter）",
                    "(MUSIC FOR MUSIC)",
                ]
            ),
            ["津田", "可不（CeVIO AI）", "Naoki Itai(MUSIC FOR MUSIC)"],
        )

    def test_drops_compact_homepage_link_notes(self) -> None:
        self.assertEqual(
            normalize_credit_values(["BAKUI（X/ホームページ）"]),
            ["BAKUI"],
        )

    def test_drops_fanbox_and_hp_link_notes(self) -> None:
        self.assertEqual(
            normalize_credit_values(["ののこ（Twitter・pixiv・FANBOX・site）"]),
            ["ののこ"],
        )
        self.assertEqual(
            normalize_credit_values(["うぐいす工房（Twitter/YouTube/HP）"]),
            ["うぐいす工房"],
        )
        self.assertEqual(
            normalize_credit_values(["えるいー（ニコニコ）"]),
            ["えるいー"],
        )

    def test_drops_social_domain_link_notes(self) -> None:
        self.assertEqual(
            normalize_credit_values(["うわごと（Twitter.com）"]),
            ["うわごと"],
        )
        self.assertEqual(
            normalize_credit_values(["作者（x.com）"]),
            ["作者"],
        )

    def test_drops_nested_official_site_link_note(self) -> None:
        self.assertEqual(
            normalize_credit_values(
                ["初音ミク（コーラス：ラプラス・ダークネス (ホロライブ 公式サイト)）"]
            ),
            ["初音ミク（コーラス：ラプラス・ダークネス）"],
        )

    def test_drops_navigation_values(self) -> None:
        self.assertEqual(normalize_credit_values(["OTOIRO", "詳細"]), ["OTOIRO"])

    def test_drops_split_link_notes(self) -> None:
        self.assertEqual(
            normalize_credit_values(["暗闇まよい", "（", "X(Twitter)", "）"]),
            ["暗闇まよい"],
        )

    def test_keeps_artist_names_starting_with_parentheses(self) -> None:
        self.assertEqual(normalize_credit_values(["(仮)P"]), ["(仮)P"])
        self.assertEqual(normalize_credit_values(["(∵)キョトンP"]), ["(∵)キョトンP"])
        self.assertEqual(normalize_credit_values(["（*´∇｀*）ぽわっ"]), ["（*´∇｀*）ぽわっ"])

    def test_stops_at_reference_note(self) -> None:
        self.assertEqual(
            normalize_credit_values(
                [
                    "VOCALOID2 初音ミク",
                    "※ LONG VERSION は『初音ミクの暴走（LONG VERSION）』を参照",
                ]
            ),
            ["VOCALOID2 初音ミク"],
        )

    def test_stops_credit_values_at_staff_detail_marker(self) -> None:
        self.assertEqual(
            normalize_credit_values(["初音ミク", "+", "OTOIRO 制作メンバー"]),
            ["初音ミク"],
        )
        self.assertEqual(
            normalize_credit_values(["うぐいす工房", "+", "うぐいす工房より 制作メンバー"]),
            ["うぐいす工房"],
        )

    def test_joins_credit_connector_lines(self) -> None:
        self.assertEqual(
            normalize_credit_values(["BUMP OF CHICKEN", "&", "MOR"]),
            ["BUMP OF CHICKEN & MOR"],
        )

    def test_joins_feat_continuation_line(self) -> None:
        self.assertEqual(
            normalize_credit_values(["BUMP OF CHICKEN feat.", "HATSUNE MIKU"]),
            ["BUMP OF CHICKEN feat. HATSUNE MIKU"],
        )

    def test_keeps_unknown_label_like_text_inside_open_parenthetical(self) -> None:
        html = """
        <html><body>
          唄：<br>初音ミク<br>・<br>KAITO<br>
          （調声：<br>びび<br>/ ボーカルミックス：<br>藤浪潤一郎<br>）<br>
          +<br>セカイver.<br>
          曲紹介
        </body></html>
        """
        self.assertEqual(
            extract_credits(clean_soup(html))["vocalist"],
            ["初音ミク", "KAITO（調声：びびボーカルミックス：藤浪潤一郎）"],
        )

    def test_stops_at_alternate_version_subsection(self) -> None:
        html = """
        <html><body>
          作詞：<br>ryo<br>
          絵：<br>119<br>
          唄：<br>初音ミク<br>
          +<br>
          CPK! Remix<br>
          CPK! Remix<br>
          調声アシスタント：<br>BichonFrise<br>
          MVディレクター：<br>マチゲリータP<br>
          絵：<br>ななみ雪<br>
          曲紹介
        </body></html>
        """
        self.assertEqual(
            extract_credits(clean_soup(html)),
            {
                "lyricist": ["ryo"],
                "illustrator": ["119"],
                "vocalist": ["初音ミク"],
            },
        )

    def test_stops_at_reloaded_subsection(self) -> None:
        html = """
        <html><body>
          作詞：<br>DECO*27<br>
          作曲：<br>DECO*27<br>
          イラスト：<br>夢之式<br>
          唄：<br>初音ミク<br>
          +<br>
          Reloaded<br>
          Reloaded<br>
          編曲：<br>DECO*27<br>・<br>Hayato Yamamoto<br>
          動画：<br>OTOIRO<br>
          曲紹介
        </body></html>
        """
        self.assertEqual(
            extract_credits(clean_soup(html)),
            {
                "lyricist": ["DECO*27"],
                "composer": ["DECO*27"],
                "illustrator": ["夢之式"],
                "vocalist": ["初音ミク"],
            },
        )

    def test_keeps_colon_inside_multiline_credit_value(self) -> None:
        html = """
        <html><body>
          作詞：<br>Aliey:S<br>
          作曲：<br>Aliey:S<br>
          編曲：<br>Aliey:S<br>
          唄：<br>初音ミク<br>
          曲紹介
        </body></html>
        """
        self.assertEqual(
            extract_credits(clean_soup(html)),
            {
                "lyricist": ["Aliey:S"],
                "composer": ["Aliey:S"],
                "arranger": ["Aliey:S"],
                "vocalist": ["初音ミク"],
            },
        )

    def test_does_not_merge_multiline_variant_vocal_label_into_main_vocal(self) -> None:
        html = """
        <html><body>
          作詞：<br>wotaku<br>
          唄：<br>初音ミク<br>
          （調声：<br>ANGL<br>）<br>
          唄（アルバム『<br>アダム<br>』収録版）：<br>KAITO<br>
          曲紹介
        </body></html>
        """
        self.assertEqual(
            extract_credits(clean_soup(html))["vocalist"],
            ["初音ミク（調声：ANGL）"],
        )

    def test_standalone_credit_labels_split_fields(self) -> None:
        html = """
        <html><body>
          作詞：<br>のぼる↑<br>
          作曲：<br>のぼる↑<br>
          編曲：<br>のぼる↑<br>
          イラスト<br>鵜飼沙樹<br>・<br>晩杯あきら<br>
          （鎖の少女-Re Alive-ver）<br>
          動画<br>GlassCore<br>・<br>藍瀬まなみ<br>
          （鎖の少女-Re Alive-ver）<br>
          唄：<br>初音ミク<br>
          曲紹介
        </body></html>
        """
        credits = extract_credits(clean_soup(html))
        self.assertEqual(credits["arranger"], ["のぼる↑"])
        self.assertEqual(
            credits["illustrator"],
            ["鵜飼沙樹", "晩杯あきら（鎖の少女-Re Alive-ver）"],
        )
        self.assertEqual(
            credits["video"],
            ["GlassCore", "藍瀬まなみ（鎖の少女-Re Alive-ver）"],
        )

    def test_treats_visual_label_as_video(self) -> None:
        html = """
        <html><body>
          作詞：<br>作者<br>
          映像<br>映像担当<br>
          曲紹介
        </body></html>
        """
        self.assertEqual(extract_credits(clean_soup(html))["video"], ["映像担当"])

    def test_treats_common_visual_aliases_as_illustration_and_video(self) -> None:
        html = """
        <html><body>
          Music：<br>作者<br>
          Illustration・MV：<br>映像絵担当<br>
          Movie<br>動画担当<br>
          曲紹介
        </body></html>
        """
        credits = extract_credits(clean_soup(html))
        self.assertEqual(credits["illustrator"], ["映像絵担当"])
        self.assertEqual(credits["video"], ["映像絵担当", "動画担当"])

    def test_does_not_treat_movie_editor_as_primary_video_credit(self) -> None:
        html = """
        <html><body>
          作詞：<br>DECO*27<br>
          動画：<br>OTOIRO<br>
          Director・Logo Designer：<br>DMYM<br>
          Illustrator：<br>八三<br>
          Movie Editor：<br>Shimpei Oniki<br>
          唄：<br>初音ミク<br>
          曲紹介
        </body></html>
        """
        credits = extract_credits(clean_soup(html))
        self.assertEqual(credits["video"], ["OTOIRO"])
        self.assertEqual(credits["illustrator"], ["八三"])


class ReadingExtractionTests(unittest.TestCase):
    def test_extracts_reading_from_title_with_parentheses(self) -> None:
        text = "曲名：『下剋上(完)』（げこくじょう(かん)）"
        self.assertEqual(extract_reading_from_text(text), "げこくじょう(かん)")

    def test_extracts_reading_from_title_with_nested_quotes(self) -> None:
        text = "曲名：『絵本『人柱アリス』』（えほん『ひとばしらアリス』）"
        self.assertEqual(extract_reading_from_text(text), "えほん『ひとばしらアリス』")

    def test_does_not_treat_title_parentheses_as_reading(self) -> None:
        text = "曲名：『モニタリング (Best Friend Remix)』"
        self.assertEqual(extract_reading_from_text(text), "")


class VideoExtractionTests(unittest.TestCase):
    def test_split_video_sections_keeps_iframe_video_urls(self) -> None:
        html = """
        <html><body>
          <h3>曲紹介</h3>
          <iframe src="https://www.youtube.com/embed/19y8YTbvri8"></iframe>
          <h3>関連動画</h3>
          <iframe src="https://ext.nicovideo.jp/thumb/sm38833751"></iframe>
        </body></html>
        """
        video_html, related_html = split_video_sections(html)

        self.assertEqual(
            [video["id"] for video in extract_videos(video_html)["youtube"]],
            ["19y8YTbvri8"],
        )
        self.assertEqual(
            [video["id"] for video in extract_videos(related_html)["niconico"]],
            ["sm38833751"],
        )

    def test_split_video_sections_keeps_subheadings_inside_related_section(self) -> None:
        html = """
        <html><body>
          <h3>曲紹介</h3>
          <iframe src="https://www.youtube.com/embed/D6DVTLvOupE"></iframe>
          <h3>関連動画</h3>
          <h4>代表的なカバー動画</h4>
          <iframe src="https://ext.nicovideo.jp/thumb/sm41948216"></iframe>
          <h4>代表的なRemix動画</h4>
          <iframe src="https://www.youtube.com/embed/-FrO4Ws4a2A"></iframe>
          <h3>コメント</h3>
        </body></html>
        """
        video_html, related_html = split_video_sections(html)

        self.assertEqual(
            [video["id"] for video in extract_videos(video_html)["youtube"]],
            ["D6DVTLvOupE"],
        )
        self.assertEqual(
            [video["id"] for video in extract_videos(related_html)["niconico"]],
            ["sm41948216"],
        )
        self.assertEqual(
            [video["id"] for video in extract_videos(related_html)["youtube"]],
            ["-FrO4Ws4a2A"],
        )

    def test_main_links_are_related_videos_not_primary_videos(self) -> None:
        html = """
        <html><body>
          <iframe src="https://www.youtube.com/embed/gfFySpNE2r0"></iframe>
          <h3>曲紹介</h3>
          <ul>
            <li><a href="https://www.nicovideo.jp/watch/sm32825363">原曲</a></li>
            <li><a href="https://www.youtube.com/watch?v=6_LluxMasZE">別歌唱版</a></li>
          </ul>
          <h3>関連動画</h3>
          <iframe src="https://ext.nicovideo.jp/thumb/sm33050558"></iframe>
          <h3>コメント</h3>
        </body></html>
        """
        video_html, related_html = split_video_sections(html)
        primary = extract_videos(
            video_html,
            include_iframes=True,
            include_links=False,
        )
        related = merge_video_maps(
            extract_videos(video_html, include_iframes=False, include_links=True),
            extract_videos(related_html),
        )

        self.assertEqual(
            [video["id"] for video in primary["youtube"]],
            ["gfFySpNE2r0"],
        )
        self.assertEqual(
            [video["id"] for video in primary["niconico"]],
            [],
        )
        self.assertEqual(
            [video["id"] for video in related["niconico"]],
            ["sm32825363", "sm33050558"],
        )
        self.assertEqual(
            [video["id"] for video in related["youtube"]],
            ["6_LluxMasZE"],
        )

    def test_excludes_english_version_section_from_primary_videos(self) -> None:
        html = """
        <html><body>
          <iframe src="https://ext.nicovideo.jp/thumb/sm12825985"></iframe>
          <iframe src="https://www.youtube.com/embed/xOKplMgHxxA"></iframe>
          <h3>曲紹介</h3>
          <p>main song</p>
          <h3>英語版</h3>
          <iframe src="https://www.youtube.com/embed/VXrptLI1lck"></iframe>
          <h4>曲紹介</h4>
          <p>english version</p>
          <h3>関連動画</h3>
        </body></html>
        """
        video_html, _ = split_video_sections(html)
        cleaned_html = remove_excluded_video_sections(video_html)
        primary = extract_videos(
            cleaned_html,
            include_iframes=True,
            include_links=False,
        )

        self.assertEqual(
            [video["id"] for video in primary["niconico"]],
            ["sm12825985"],
        )
        self.assertEqual(
            [video["id"] for video in primary["youtube"]],
            ["xOKplMgHxxA"],
        )

    def test_video_extraction_uses_fallback_metadata(self) -> None:
        html = """
        <html><body>
          <iframe src="https://ext.nicovideo.jp/thumb/sm12345"></iframe>
          <iframe src="https://www.youtube.com/embed/19y8YTbvri8"></iframe>
        </body></html>
        """
        videos = extract_videos(html)

        self.assertEqual(videos["niconico"][0]["title"], "ニコニコ動画 sm12345")
        self.assertEqual(
            videos["niconico"][0]["thumbnail_url"],
            "https://nicovideo.cdn.nimg.jp/thumbnails/12345/12345.L",
        )
        self.assertEqual(
            videos["niconico"][0]["thumbnail_urls"],
            [
                "https://nicovideo.cdn.nimg.jp/thumbnails/12345/12345.L",
                "https://nicovideo.cdn.nimg.jp/thumbnails/12345/12345.M",
                "https://nicovideo.cdn.nimg.jp/thumbnails/12345/12345",
            ],
        )
        self.assertEqual(videos["youtube"][0]["title"], "YouTube 19y8YTbvri8")


if __name__ == "__main__":
    unittest.main()
