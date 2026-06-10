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
    remove_excluded_video_sections,
    split_video_sections,
    split_credit_text,
)


class CreditNormalizationTests(unittest.TestCase):
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
