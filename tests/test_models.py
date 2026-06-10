import unittest

from vocaloid_title_search.models import (
    SongEntry,
    count_title_chars,
    grapheme_clusters,
    split_title_artist,
)


class TitleCountingTests(unittest.TestCase):
    def test_counts_combining_voiced_mark_as_composed_character(self) -> None:
        self.assertEqual(count_title_chars("このツンデレ！"), 7)
        self.assertEqual(count_title_chars("このツンデレ！"), 7)

    def test_counts_emoji_sequence_as_single_visible_character(self) -> None:
        self.assertEqual(count_title_chars("愛❤️"), 2)
        self.assertEqual(count_title_chars("家族👨‍👩‍👧‍👦"), 3)

    def test_counts_variation_selector_with_base_character(self) -> None:
        self.assertEqual(count_title_chars("辻󠄀"), 1)
        self.assertEqual(count_title_chars("✌️"), 1)

    def test_ignores_whitespace_and_standalone_blank_like_characters(self) -> None:
        self.assertEqual(count_title_chars("A B　C\tD"), 4)
        self.assertEqual(count_title_chars("A\u200bB\u2060C\ufeff"), 3)
        self.assertEqual(count_title_chars("A\u2800B"), 2)

    def test_ignores_braille_pattern_blank_in_title_count(self) -> None:
        title = "ネ⠀土⠀会⠀ェ⠀貝⠀南⠀犬⠀☆⠀カ⠀ゞ⠀ん⠀I⠀よ⠀″⠀る⠀ノ⠀D⠀A⠀!!｡"
        self.assertEqual(count_title_chars(title), 21)

    def test_grapheme_clusters_keep_zwj_emoji_together(self) -> None:
        self.assertEqual(grapheme_clusters("👨‍👩‍👧‍👦"), ["👨‍👩‍👧‍👦"])

    def test_song_entry_normalizes_split_title(self) -> None:
        song = SongEntry.from_raw("このツンデレ！")
        self.assertEqual(song.title, "このツンデレ！")
        self.assertEqual(song.title_length, 7)

    def test_split_title_artist_normalizes_title(self) -> None:
        title, artist, artist_note = split_title_artist("このツンデレ！/Naka-Dai")
        self.assertEqual(title, "このツンデレ！")
        self.assertEqual(artist, "Naka-Dai")
        self.assertEqual(artist_note, "")


if __name__ == "__main__":
    unittest.main()
