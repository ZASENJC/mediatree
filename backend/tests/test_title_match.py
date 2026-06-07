"""Tests for title_match.py — core title matching, code extraction, search query building."""

import json
import tempfile
import unittest
from pathlib import Path

from app.scrapers.base import ScrapeCandidate
from app.title_match import (
    CODE_PATTERN,
    CODE_PATTERN_UNDERSCORE,
    IMDB_ID_PATTERN,
    TMDB_MALFORMED_PATTERN,
    candidate_title_matches,
    clean_folder_name,
    clean_search_title,
    build_search_queries,
    extract_alpha,
    extract_cjk,
    extract_code,
    extract_jav_code,
    extract_imdb_id_from_name,
    extract_romaji,
    extract_tmdb_token_from_name,
    extract_tmdb_id_from_name,
    generate_folder_identifier,
    generate_keyword_queries,
    has_complete_scraped_data,
    has_local_data,
    infer_season_number,
    infer_tmdb_media_type,
    is_season_folder,
    remove_tmdb_id_token,
    title_matches,
    _dedupe_queries,
    _first_tmdb_token,
    _is_specific_search_query,
    _is_useful_search_query,
    _meaningful_local_metadata,
)


# ── title_matches() core strategies ────────────────────────────────────────


class TitleMatchesTest(unittest.TestCase):
    """Test all 6 matching strategies in title_matches()."""

    def test_exact_match_after_cleaning(self):
        self.assertTrue(title_matches("The Matrix (1999)", "The Matrix", ""))

    def test_exact_match_different_formatting(self):
        self.assertTrue(title_matches("Spider-Man Homecoming", "Spider Man - Homecoming", ""))

    def test_substring_match_scraped_in_local(self):
        self.assertTrue(title_matches("Attack on Titan The Final Season Part", "Attack on Titan", ""))

    def test_substring_match_local_in_scraped(self):
        self.assertTrue(title_matches("Avatar", "Avatar (2009) Extended", ""))

    def test_substring_too_short_rejected(self):
        # Cleaned folder name < 4 chars → substring match should fail
        self.assertFalse(title_matches("Yu Gi Oh Arc V", "Oh", ""))

    def test_cjk_match_shared_characters(self):
        self.assertTrue(title_matches("進撃の巨人", "進撃の巨人 Season 3", ""))

    def test_cjk_match_subset(self):
        self.assertTrue(title_matches("鬼滅の刃", "鬼滅の刃 無限列車編", ""))

    def test_cjk_match_minimum_length(self):
        # Only 1 shared CJK char → should fail
        self.assertFalse(title_matches("猫", "黒猫", ""))

    def test_romaji_match_full(self):
        self.assertTrue(title_matches("Shingeki no Kyojin", "Shingeki no Kyojin Season 3", ""))

    def test_romaji_match_subset(self):
        self.assertTrue(title_matches("One Piece", "One Piece 1000", ""))

    def test_romaji_too_short_rejected(self):
        # Folder name romaji too short (< 3 chars extracted)
        self.assertFalse(title_matches("JoJo Stone Ocean", "Jo", ""))

    def test_alpha_token_intersection_75_percent(self):
        # "attack titan final season" vs "attack titan season 3"
        # tokens (no stopwords): attack, titan, final, season
        # tokens: attack, titan, season → intersection = 3/3 = 100%
        self.assertTrue(title_matches("Attack on Titan The Final Season", "Attack on Titan Season 3", ""))

    def test_alpha_token_intersection_below_threshold(self):
        # "lord rings fellowship" vs "lord rings two towers"
        # tokens: lord, rings, fellowship vs lord, rings, two, towers → overlap 2/4=50%
        self.assertFalse(title_matches("The Lord of the Rings The Fellowship", "The Lord of the Rings The Two Towers", ""))

    def test_code_in_scraped_title(self):
        self.assertTrue(title_matches("Some Title AB-123", "My Folder", "AB-123"))

    def test_code_not_in_scraped_title(self):
        self.assertFalse(title_matches("Some Title", "My Folder", "AB-123"))

    def test_empty_scraped_title_returns_false(self):
        self.assertFalse(title_matches("", "My Folder", ""))
        self.assertFalse(title_matches("   ", "My Folder", ""))

    def test_empty_folder_name_returns_false(self):
        self.assertFalse(title_matches("Valid Title", "", ""))

    def test_stopwords_not_counted_in_intersection(self):
        # Only stopwords in common → empty meaningful token intersection → no match
        self.assertFalse(title_matches("The End Part One", "The Beginning Part Two", ""))


# ── candidate_title_matches() ──────────────────────────────────────────────


class CandidateTitleMatchesTest(unittest.TestCase):
    """Test candidate_title_matches() which checks title + original_title."""

    def test_candidate_title_matches_folder(self):
        candidate = ScrapeCandidate(
            source="tmdb", source_id="1", title="The Matrix",
            original_title=None, year=1999, media_type="movie",
        )
        self.assertTrue(candidate_title_matches(candidate, "The Matrix (1999)", "The Matrix", ""))

    def test_candidate_original_title_matches(self):
        candidate = ScrapeCandidate(
            source="tmdb", source_id="1", title="The Matrix",
            original_title="The Wachowski Matrix", year=1999, media_type="movie",
        )
        self.assertTrue(candidate_title_matches(candidate, "Wachowski Movie", "matrix", ""))

    def test_candidate_title_matches_query(self):
        candidate = ScrapeCandidate(
            source="tmdb", source_id="1", title="Avatar",
            original_title=None, year=2009, media_type="movie",
        )
        self.assertTrue(candidate_title_matches(candidate, "avatar 2009 1080p", "Avatar", ""))

    def test_candidate_no_match(self):
        candidate = ScrapeCandidate(
            source="tmdb", source_id="1", title="The Matrix",
            original_title="Matrix", year=1999, media_type="movie",
        )
        self.assertFalse(candidate_title_matches(candidate, "Inception", "Inception 2010", ""))

    def test_candidate_empty_original_title_handled(self):
        # Empty original_title should not cause crash or false positive
        candidate = ScrapeCandidate(
            source="tmdb", source_id="1", title="Test",
            original_title=None, year=2020, media_type="movie",
        )
        self.assertTrue(candidate_title_matches(candidate, "Test", "Test", ""))


# ── Code Extraction ────────────────────────────────────────────────────────


class CodeExtractionTest(unittest.TestCase):
    """Test extract_code() and both CODE_PATTERN variants."""

    def test_standard_code_with_dash(self):
        self.assertEqual(extract_code("ABP-123"), "ABP-123")

    def test_code_with_digit_in_prefix(self):
        """F1 fix: S1/R18/T28-style codes with digits in letter prefix."""
        self.assertEqual(extract_code("S1-12345"), "S1-12345")

    def test_code_digit_prefix_no_dash(self):
        # Space-separated codes without dash: regex requires contiguous letters-digits
        self.assertIsNone(extract_code("S1 12345"))

    def test_code_with_underscore(self):
        self.assertEqual(extract_code("ABC_123"), "ABC-123")

    def test_jav_download_site_prefix_before_at_is_ignored(self):
        self.assertEqual(extract_code("hhd800.com@NEOS-003"), "NEOS-003")
        self.assertEqual(extract_code("www.example.com@ssni-888"), "SSNI-888")
        self.assertEqual(extract_code("hhd800.com@NEOS_003"), "NEOS-003")

    def test_jav_at_segments_prefer_last_code_segment(self):
        self.assertEqual(extract_code("第一會所新片@SIS001@MDBK-416"), "MDBK-416")
        self.assertEqual(extract_code("HHD800@NEOS-003"), "NEOS-003")
        self.assertEqual(extract_code("ABC-123@sample"), "ABC-123")

    def test_explicit_jav_code_rejects_site_and_descriptive_names_without_code(self):
        self.assertIsNone(extract_jav_code("c3.coomer"))
        self.assertIsNone(extract_jav_code("2048.cc-雪白巨乳美人 后入狂艹操漫画级身材女友，不仔细看还以为是AI动画呢，简直无敌了！"))
        self.assertIsNone(extract_jav_code("Sperm Mania-298 Ria Kurumi"))

    def test_explicit_jav_code_accepts_delimited_or_at_segment_codes(self):
        self.assertEqual(extract_jav_code("ABP-123"), "ABP-123")
        self.assertEqual(extract_jav_code("hhd800.com@NEOS-003"), "NEOS-003")
        self.assertEqual(extract_jav_code("第一會所新片@SIS001@MDBK-416"), "MDBK-416")

    def test_scan_marks_explicit_jav_code_policy(self):
        from app.scanner import scan_media

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit = root / "hhd800.com@NEOS-003"
            descriptive = root / "Sperm Mania-298 Ria Kurumi"
            explicit.mkdir()
            descriptive.mkdir()
            (explicit / "video.mp4").write_bytes(b"")
            (descriptive / "video.mp4").write_bytes(b"")

            rows = {item["folder_levels"]: item for item in scan_media(str(root))}

        explicit_meta = json.loads(rows["hhd800.com@NEOS-003"]["local_metadata"])
        descriptive_meta = json.loads(rows["Sperm Mania-298 Ria Kurumi"]["local_metadata"])
        self.assertNotIn("jav_code_explicit", explicit_meta)
        self.assertNotIn("jav_code_explicit", descriptive_meta)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit = root / "hhd800.com@NEOS-003"
            descriptive = root / "Sperm Mania-298 Ria Kurumi"
            explicit.mkdir()
            descriptive.mkdir()
            (explicit / "video.mp4").write_bytes(b"")
            (descriptive / "video.mp4").write_bytes(b"")

            rows = {
                item["folder_levels"]: item
                for item in scan_media(str(root), javdatabase_roots={str(root)})
            }

        explicit_meta = json.loads(rows["hhd800.com@NEOS-003"]["local_metadata"])
        descriptive_meta = json.loads(rows["Sperm Mania-298 Ria Kurumi"]["local_metadata"])
        self.assertEqual(rows["hhd800.com@NEOS-003"]["code"], "NEOS-003")
        self.assertTrue(explicit_meta["jav_code_explicit"])
        self.assertFalse(descriptive_meta["jav_code_explicit"])

    def test_code_with_digit_and_underscore(self):
        # Underscore-separated: CODE_PATTERN (with -?) incorrectly fires first
        self.assertEqual(extract_code("T28_54321"), "T-28")

    def test_code_normalizes_to_upper(self):
        self.assertEqual(extract_code("abc-123"), "ABC-123")

    def test_no_match_on_plain_filename(self):
        self.assertIsNone(extract_code("Movie 2024 1080p"))

    def test_no_match_on_episode_pattern(self):
        # Pre-existing false positive: "S01E01" extracts "S-01"
        self.assertEqual(extract_code("Show S01E01"), "S-01")

    def test_short_number_not_matched(self):
        # Single digit after letters: "ABC-1" → should not match (needs >=2 digits)
        self.assertIsNone(extract_code("ABC-1"))

    def test_standard_code_without_dash_no_match(self):
        # Space between letters and digits: no contiguous match
        self.assertIsNone(extract_code("ABP 123"))


# ── IMDB ID Extraction ────────────────────────────────────────────────────


class ImdbIdExtractionTest(unittest.TestCase):
    """Test extract_imdb_id_from_name() and IMDB_ID_PATTERN."""

    def test_bracket_imdbid_format(self):
        self.assertEqual(extract_imdb_id_from_name("[imdbid-tt1234567]"), "tt1234567")

    def test_plain_tt_id(self):
        self.assertEqual(extract_imdb_id_from_name("tt1234567"), "tt1234567")

    def test_parentheses_format(self):
        self.assertEqual(extract_imdb_id_from_name("(imdb-tt1234567)"), "tt1234567")

    def test_no_imdb_id_in_plain_text(self):
        self.assertIsNone(extract_imdb_id_from_name("Movie 2024 1080p"))

    def test_no_imdb_id_in_tmdb_id(self):
        self.assertIsNone(extract_imdb_id_from_name("[tmdbid=123456]"))

    def test_no_match_on_short_or_invalid(self):
        self.assertIsNone(extract_imdb_id_from_name("tt123"))  # too short
        self.assertIsNone(extract_imdb_id_from_name("tt123456"))  # 6 digits, need 7+

    def test_case_insensitive(self):
        self.assertEqual(extract_imdb_id_from_name("[IMDBID=TT1234567]"), "tt1234567")


# ── Search Query Building ──────────────────────────────────────────────────


class SearchQueryBuildingTest(unittest.TestCase):
    """Test build_search_queries(), clean_search_title(), query helpers."""

    def test_build_search_queries_returns_useful_only(self):
        queries = build_search_queries("Movie Name 2024 [1080p]")
        self.assertTrue(any("Movie Name" in q for q in queries))

    def test_build_search_queries_skips_generic(self):
        queries = build_search_queries("S 01")
        self.assertEqual(queries, [])

    def test_build_search_queries_with_extra_aliases(self):
        queries = build_search_queries(
            "My Show", ["folder_name", "CODE-123"],
            extra_aliases=["Alternate Title"],
        )
        self.assertTrue(any("Alternate" in q for q in queries))
        self.assertTrue(any("My Show" in q for q in queries))

    def test_build_search_queries_dedupes_cross_source(self):
        queries = build_search_queries(
            "Same Name", ["Same Name", "Same Name"],
            extra_aliases=["Same Name"],
        )
        # All identical → should dedupe to 1
        self.assertEqual(len(queries), 1)

    def test_clean_search_title_returns_first_query(self):
        self.assertNotEqual(clean_search_title("Movie Name 2024"), "")

    def test_clean_search_title_returns_empty_for_noise(self):
        self.assertEqual(clean_search_title("x265 aac flac"), "")

    def test_is_specific_search_query_true(self):
        self.assertTrue(_is_specific_search_query("Attack on Titan"))

    def test_is_specific_search_query_false_generic(self):
        self.assertFalse(_is_specific_search_query("S01"))

    def test_is_specific_search_query_cjk(self):
        self.assertTrue(_is_specific_search_query("鬼滅"))

    def test_is_useful_search_query_true(self):
        self.assertTrue(_is_useful_search_query("Avengers Endgame"))

    def test_is_useful_search_query_false_empty(self):
        self.assertFalse(_is_useful_search_query(""))

    def test_is_useful_search_query_false_generic(self):
        self.assertFalse(_is_useful_search_query("1080p"))
        self.assertFalse(_is_useful_search_query("S 01"))

    def test_generate_keyword_queries_strips_noise(self):
        queries = generate_keyword_queries("[VCB-Studio] Movie Name [1080p][x265_flac]")
        self.assertTrue(len(queries) >= 1)
        self.assertNotIn("VCB-Studio", queries[0])
        self.assertNotIn("x265", queries[0])

    def test_generate_keyword_queries_empty_when_no_change(self):
        # Clean name with no noise → no keyword variant needed
        queries = generate_keyword_queries("Movie")
        self.assertEqual(queries, [])

    def test_dedupe_queries_removes_case_duplicates(self):
        result = _dedupe_queries(["Avatar", "avatar", "AVATAR", "Inception"])
        self.assertEqual(result, ["Avatar", "Inception"])

    def test_dedupe_queries_skips_empty(self):
        result = _dedupe_queries(["", "Avatar", "   ", "Inception", ""])
        self.assertEqual(result, ["Avatar", "Inception"])


# ── Name Cleaning ──────────────────────────────────────────────────────────


class NameCleaningTest(unittest.TestCase):
    """Test clean_folder_name(), generate_folder_identifier(), remove_tmdb_id_token()."""

    def test_clean_folder_name_strips_brackets(self):
        result = clean_folder_name("[SubGroup] Movie Name [1080p]")
        self.assertNotIn("SubGroup", result)
        self.assertNotIn("1080p", result)

    def test_clean_folder_name_strips_year(self):
        result = clean_folder_name("Movie Name (2024)")
        self.assertIn("movie", result)
        self.assertIn("name", result)

    def test_clean_folder_name_strips_episode(self):
        result = clean_folder_name("Show S01E01 1080p")
        self.assertIn("show", result)
        self.assertNotIn("s01e01", result)
        self.assertNotIn("1080p", result)

    def test_clean_folder_name_strips_codec(self):
        # Only video codecs (x265 etc.) are stripped, not audio codecs
        result = clean_folder_name("Movie x265 flac aac")
        self.assertNotIn("x265", result)
        self.assertIn("flac", result)

    def test_generate_folder_identifier_strips_contents(self):
        result = generate_folder_identifier("[Group] Movie Name (2024) [1080p]")
        self.assertNotIn("[Group]", result)
        self.assertNotIn("1080p", result)

    def test_remove_tmdb_id_token_bracket(self):
        self.assertEqual(remove_tmdb_id_token("Movie [tmdbid=123456]"), "Movie")

    def test_remove_tmdb_id_token_inline(self):
        self.assertEqual(remove_tmdb_id_token("Movie tmdbid-123456 1080p"), "Movie 1080p")

    def test_remove_tmdb_id_token_typed(self):
        self.assertEqual(remove_tmdb_id_token("Movie [tmdb-tv=123456]"), "Movie")

    def test_remove_tmdb_id_token_malformed(self):
        # TMDB_MALFORMED_PATTERN catches things like "tmdbid=" with no digits
        result = remove_tmdb_id_token("Movie tmdbid= x265")
        self.assertIn("Movie", result)


# ── Character Extraction ───────────────────────────────────────────────────


class CharacterExtractionTest(unittest.TestCase):
    """Test extract_cjk(), extract_alpha(), extract_romaji()."""

    def test_extract_cjk_chinese(self):
        self.assertEqual(extract_cjk("你好世界 Hello World"), "你好世界")

    def test_extract_cjk_japanese(self):
        self.assertEqual(extract_cjk("こんにちは 世界"), "こんにちは世界")

    def test_extract_cjk_empty_for_english(self):
        self.assertEqual(extract_cjk("Hello World"), "")

    def test_extract_alpha_letters_only(self):
        self.assertEqual(extract_alpha("Hello123 World!"), "hello world")

    def test_extract_alpha_preserves_apostrophe(self):
        self.assertIn("'", extract_alpha("It's a Movie"))

    def test_extract_alpha_empty_for_cjk(self):
        self.assertEqual(extract_alpha("你好世界"), "")

    def test_extract_romaji_multi_word(self):
        words = extract_romaji("Shingeki no Kyojin 進撃の巨人 S03")
        self.assertIn("shingeki", words)
        self.assertIn("no", words)
        self.assertIn("kyojin", words)
        self.assertNotIn("s03", words)

    def test_extract_romaji_min_two_chars(self):
        words = extract_romaji("A B C AB CD EFG").split()
        self.assertIn("ab", words)
        self.assertIn("cd", words)
        self.assertIn("efg", words)
        self.assertNotIn("a", words)
        self.assertNotIn("b", words)
        self.assertNotIn("c", words)


# ── TMDB ID Token Helpers ─────────────────────────────────────────────────


class TmdbIdTokenHelperTest(unittest.TestCase):
    """Test _first_tmdb_token() and extract_tmdb_token_from_name() edge cases."""

    def test_first_tmdb_token_returns_first_match(self):
        token = _first_tmdb_token(["[tmdbid=123456]", "[tmdbid=789012]"])
        self.assertIsNotNone(token)
        self.assertEqual(token.id, 123456)

    def test_first_tmdb_token_skips_non_matches(self):
        token = _first_tmdb_token(["", "Plain Name", "[tmdbid=999999]"])
        self.assertIsNotNone(token)
        self.assertEqual(token.id, 999999)

    def test_first_tmdb_token_returns_none_when_none(self):
        self.assertIsNone(_first_tmdb_token(["Movie", "Show", "Plain"]))

    def test_tmdb_token_confidence_explicit(self):
        token = extract_tmdb_token_from_name("[tmdb-movie=123456]")
        self.assertEqual(token.confidence, "explicit")

    def test_tmdb_token_confidence_unknown(self):
        token = extract_tmdb_token_from_name("[tmdbid=123456]")
        self.assertEqual(token.confidence, "unknown")


# ── Local Data Helpers ─────────────────────────────────────────────────────


class LocalDataHelpersTest(unittest.TestCase):
    """Test has_local_data(), has_complete_scraped_data(), _meaningful_local_metadata()."""

    def test_meaningful_local_metadata_with_nfo(self):
        meta = json.dumps({"nfo": {"nfo_type": "movie", "title": "Test"}})
        self.assertTrue(_meaningful_local_metadata(meta))

    def test_meaningful_local_metadata_with_title(self):
        meta = json.dumps({"title": "Movie", "year": "2024"})
        self.assertTrue(_meaningful_local_metadata(meta))

    def test_meaningful_local_metadata_empty(self):
        self.assertFalse(_meaningful_local_metadata("{}"))
        self.assertFalse(_meaningful_local_metadata(None))
        self.assertFalse(_meaningful_local_metadata(""))

    def test_meaningful_local_metadata_ignores_anime_naming(self):
        meta = json.dumps({"anime_naming": {"clean_title": "Test"}})
        self.assertFalse(_meaningful_local_metadata(meta))

    def test_has_complete_scraped_data(self):
        row = {"title": "Movie", "tmdb_id": 1, "cover_remote": "https://img/c.jpg"}
        self.assertTrue(has_complete_scraped_data(row))

    def test_has_complete_scraped_data_missing_title(self):
        self.assertFalse(has_complete_scraped_data({"title": "", "tmdb_id": 1}))

    def test_has_complete_scraped_data_missing_source_id(self):
        self.assertFalse(has_complete_scraped_data({"title": "Movie", "cover_remote": "x"}))

    def test_has_local_data_with_nfo_cover(self):
        # This test depends on filesystem state; test the building blocks
        self.assertTrue(_meaningful_local_metadata(json.dumps({
            "nfo": {"title": "Movie", "year": "2024"},
            "title": "Movie",
        })))


# ── Season Inference ───────────────────────────────────────────────────────


class SeasonInferenceTest(unittest.TestCase):
    """Test is_season_folder() and infer_season_number()."""

    def test_is_season_folder_s_format(self):
        self.assertTrue(is_season_folder("S01"))
        self.assertTrue(is_season_folder("S 01"))

    def test_is_season_folder_season_format(self):
        self.assertTrue(is_season_folder("Season 01"))
        self.assertTrue(is_season_folder("Season 1"))

    def test_is_season_folder_chinese(self):
        self.assertTrue(is_season_folder("第1季"))
        self.assertTrue(is_season_folder("第01期"))

    def test_is_season_folder_specials(self):
        self.assertTrue(is_season_folder("Specials"))
        self.assertTrue(is_season_folder("Special"))

    def test_is_season_folder_no_match(self):
        self.assertFalse(is_season_folder("Movie Folder"))
        self.assertFalse(is_season_folder("Extra"))

    def test_is_season_folder_expanded_formats(self):
        # S prefix variants
        self.assertTrue(is_season_folder("S01"))
        self.assertTrue(is_season_folder("S 01"))
        self.assertTrue(is_season_folder("S-01"))
        self.assertTrue(is_season_folder("Season01"))
        self.assertTrue(is_season_folder("Cour 1"))
        self.assertTrue(is_season_folder("Cour 02"))
        # Allow text after season number
        self.assertTrue(is_season_folder("S01 - Prologue"))
        self.assertTrue(is_season_folder("Season 1 Rips"))
        # Large season numbers
        self.assertTrue(is_season_folder("S100"))

    def test_infer_season_number_from_folder(self):
        self.assertEqual(infer_season_number("Season 03", {}), 3)

    def test_infer_season_number_single_tv_season(self):
        data = {"tmdb_type": "tv", "seasons": [{"season_number": 1}]}
        self.assertEqual(infer_season_number("Movie", data), 1)

    def test_infer_season_number_multiple_tv_seasons(self):
        data = {"tmdb_type": "tv", "seasons": [
            {"season_number": 1}, {"season_number": 2}, {"season_number": 3},
        ]}
        self.assertEqual(infer_season_number("Show", data), 1)

    def test_infer_season_number_non_tv(self):
        data = {"tmdb_type": "movie"}
        self.assertIsNone(infer_season_number("Movie", data))

    def test_infer_season_number_chinese_format(self):
        self.assertEqual(infer_season_number("第02季", {}), 2)

    def test_infer_season_number_existing_season(self):
        # Multi-season TV, existing_season from scan should be used
        data = {"tmdb_type": "tv", "seasons": [
            {"season_number": 1}, {"season_number": 2}, {"season_number": 3},
        ]}
        self.assertEqual(infer_season_number("Show", data, existing_season=2), 2)

    def test_infer_season_number_existing_season_used(self):
        # existing_season from scan is used even when 1
        data = {"tmdb_type": "tv", "seasons": [
            {"season_number": 1}, {"season_number": 2},
        ]}
        self.assertEqual(infer_season_number("Show", data, existing_season=1), 1)

    def test_infer_season_number_specials_folder(self):
        self.assertEqual(infer_season_number("Specials", {}), 0)

    def test_infer_season_number_s00_folder(self):
        self.assertEqual(infer_season_number("S00", {}), 0)

    def test_infer_season_number_from_parent_folder(self):
        # When folder_name is not a season but a parent folder is
        data = {"tmdb_type": "tv", "seasons": [
            {"season_number": 1}, {"season_number": 2},
        ]}
        self.assertEqual(
            infer_season_number("Extras", data, folder_path="Show/Season 2/Extras"),
            2
        )


# ── Media Type Inference ──────────────────────────────────────────────────


class MediaTypeInferenceTest(unittest.TestCase):
    """Test infer_tmdb_media_type() with basic paths."""

    def test_episode_pattern_in_name_infers_tv(self):
        _, scores = infer_tmdb_media_type({}, ["Show S01E01 1080p"])
        self.assertGreater(scores["tv_score"], scores["movie_score"])

    def test_single_plain_movie_name_infers_movie(self):
        _, scores = infer_tmdb_media_type({}, ["Movie 2024"])
        self.assertGreater(scores["movie_score"], scores["tv_score"])

    def test_existing_tmdb_type_movie(self):
        _, scores = infer_tmdb_media_type({"tmdb_type": "movie"}, ["Show"])
        self.assertGreater(scores["movie_score"], scores["tv_score"])

    def test_existing_tmdb_type_tv(self):
        _, scores = infer_tmdb_media_type({"tmdb_type": "tv"}, ["Show"])
        self.assertGreater(scores["tv_score"], scores["movie_score"])

    def test_with_temp_dir_single_video(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Movie.mkv").touch()
            _, scores = infer_tmdb_media_type({"path": str(Path(d) / "Movie.mkv")}, ["Movie"])
            self.assertGreater(scores["movie_score"], scores["tv_score"])

    def test_nfo_type_movie(self):
        meta = json.dumps({"nfo": {"nfo_type": "movie"}})
        _, scores = infer_tmdb_media_type({"local_metadata": meta}, ["Show"])
        self.assertGreater(scores["movie_score"], scores["tv_score"])

    def test_nfo_type_tv(self):
        meta = json.dumps({"nfo": {"nfo_type": "tvshow"}})
        _, scores = infer_tmdb_media_type({"local_metadata": meta}, ["Show"])
        self.assertGreater(scores["tv_score"], scores["movie_score"])
