import tempfile
import unittest
from pathlib import Path

from app import scanner, tmdb
from app.scanner import (
    TmdbIdToken,
    build_search_queries,
    clean_search_title,
    extract_tmdb_id_from_name,
    extract_tmdb_token_from_name,
    infer_tmdb_media_type,
    remove_tmdb_id_token,
)


class TmdbIdParsingTest(unittest.TestCase):
    def test_extract_tmdb_token(self):
        cases = {
            "[tmdb-movie=123456]": ("movie", 123456),
            "[tmdb-tv=123456]": ("tv", 123456),
            "[tmdbid=movie:123456]": ("movie", 123456),
            "[tmdbid=tv:123456]": ("tv", 123456),
            "[tmdbid=m:123456]": ("movie", 123456),
            "[tmdbid=t:123456]": ("tv", 123456),
            "[tmdb:m:123456]": ("movie", 123456),
            "[tmdbid=123456]": (None, 123456),
            "Movie tmdb 123456": (None, 123456),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                token = extract_tmdb_token_from_name(text)
                self.assertIsNotNone(token)
                self.assertEqual((token.media_type, token.id), expected)

    def test_extract_tmdb_id_rejects_plain_numbers(self):
        for text in ["Movie 2024", "S01E02", "EP12", "第01集", "123456"]:
            with self.subTest(text=text):
                self.assertIsNone(extract_tmdb_id_from_name(text))

    def test_remove_tmdb_id_token(self):
        cases = {
            "Movie [tmdbid=123456]": "Movie",
            "Movie tmdbid-123456": "Movie",
            "Movie (tmdbid=123456)": "Movie",
            "Movie [tmdb-tv=123456]": "Movie",
            "Movie [tmdbid=movie:123456]": "Movie",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(remove_tmdb_id_token(text), expected)


class SearchTitleCleaningTest(unittest.TestCase):
    def test_clean_search_title_removes_malformed_tmdb_token_and_release_group(self):
        self.assertEqual(
            clean_search_title("和青梅竹马之间不会有恋爱喜剧 tmdbid= -LoliHouse"),
            "和青梅竹马之间不会有恋爱喜剧",
        )

    def test_clean_search_title_removes_episode_and_subtitle_language_tags(self):
        self.assertEqual(
            clean_search_title("Seihantai na Kimi to Boku - 01 - CHS&CHT"),
            "Seihantai na Kimi to Boku",
        )
        self.assertEqual(
            clean_search_title("Violet Evergarden - 01 zh-Hans"),
            "Violet Evergarden",
        )

    def test_clean_search_title_removes_codec_audio_tags(self):
        self.assertEqual(
            clean_search_title("Shinigami Bocchan to Kuro Maid x265 flac aac"),
            "Shinigami Bocchan to Kuro Maid",
        )
        self.assertEqual(
            clean_search_title("No Game No Life x264 2flac"),
            "No Game No Life",
        )

    def test_build_search_queries_skips_generic_season_query(self):
        queries = build_search_queries("S 01", ["S01", "01", "1080p"])
        self.assertEqual(queries, [])


class TmdbTypeInferenceTest(unittest.TestCase):
    def test_episode_patterns_infer_tv(self):
        for text in ["Show S01E01", "Show 1x01", "Show EP01", "Show E01", "Show 第01集"]:
            with self.subTest(text=text):
                inferred, _scores = infer_tmdb_media_type({"path": ""}, [text])
                self.assertEqual(inferred, "tv")

    def test_season_infers_tv(self):
        inferred, _scores = infer_tmdb_media_type({"path": ""}, ["Show Season 01"])
        self.assertEqual(inferred, "tv")

    def test_existing_tv_fields_infer_tv(self):
        inferred, _scores = infer_tmdb_media_type({"tmdb_type": "tv"}, ["Title"])
        self.assertEqual(inferred, "tv")
        inferred, _scores = infer_tmdb_media_type({"tmdb_season": 1, "tmdb_episode": 2}, ["Title"])
        self.assertEqual(inferred, "tv")

    def test_single_file_year_infers_movie(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "Movie Name (2024).mkv"
            video.write_text("")
            inferred, _scores = infer_tmdb_media_type({"path": str(video)}, ["Movie Name (2024)"])
            self.assertEqual(inferred, "movie")

    def test_nfo_movie_infers_movie(self):
        inferred, _scores = infer_tmdb_media_type(
            {"local_metadata": '{"nfo":{"nfo_type":"movie"}}'},
            ["Movie Name"],
        )
        self.assertEqual(inferred, "movie")

    def test_close_scores_return_none(self):
        inferred, scores = infer_tmdb_media_type({"tmdb_type": "movie"}, ["Show S01E01"])
        self.assertIsNone(inferred)
        self.assertEqual(scores["movie_score"], scores["tv_score"])


class TmdbCandidateSelectionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_fetch = tmdb.fetch_tmdb_by_id
        self.orig_candidates = tmdb.fetch_tmdb_candidates_by_id
        self.calls = []

    async def asyncTearDown(self):
        tmdb.fetch_tmdb_by_id = self.orig_fetch
        tmdb.fetch_tmdb_candidates_by_id = self.orig_candidates

    async def test_explicit_movie_only_requests_movie(self):
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(media_type)
            return {"title": "Movie", "media_type": media_type}

        tmdb.fetch_tmdb_by_id = fetch
        token = TmdbIdToken(123456, "movie", "[tmdb-movie=123456]", "folder", "explicit")
        result = await scanner.resolve_tmdb_id_candidate(token, {}, ["Title"])
        self.assertEqual(result["media_type"], "movie")
        self.assertEqual(self.calls, ["movie"])

    async def test_explicit_tv_only_requests_tv(self):
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(media_type)
            return {"title": "TV", "media_type": media_type}

        tmdb.fetch_tmdb_by_id = fetch
        token = TmdbIdToken(123456, "tv", "[tmdb-tv=123456]", "folder", "explicit")
        result = await scanner.resolve_tmdb_id_candidate(token, {}, ["Title"])
        self.assertEqual(result["media_type"], "tv")
        self.assertEqual(self.calls, ["tv"])

    async def test_strong_tv_only_requests_tv(self):
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(media_type)
            return {"title": "TV", "media_type": media_type}

        tmdb.fetch_tmdb_by_id = fetch
        token = TmdbIdToken(123456, None, "[tmdbid=123456]", "folder", "unknown")
        result = await scanner.resolve_tmdb_id_candidate(token, {}, ["Show Season 01 S01E01"])
        self.assertEqual(result["media_type"], "tv")
        self.assertEqual(self.calls, ["tv"])

    async def test_strong_movie_only_requests_movie(self):
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(media_type)
            return {"title": "Movie", "media_type": media_type}

        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "Movie Name (2024).mkv"
            video.write_text("")
            tmdb.fetch_tmdb_by_id = fetch
            token = TmdbIdToken(123456, None, "[tmdbid=123456]", "folder", "unknown")
            result = await scanner.resolve_tmdb_id_candidate(token, {"path": str(video)}, ["Movie Name (2024)"])
        self.assertEqual(result["media_type"], "movie")
        self.assertEqual(self.calls, ["movie"])

    async def test_unclear_requests_candidates(self):
        async def candidates(tmdb_id, lang="zh-CN"):
            self.calls.append("candidates")
            return {"movie": {"title": "Movie", "media_type": "movie"}, "tv": None}

        tmdb.fetch_tmdb_candidates_by_id = candidates
        token = TmdbIdToken(123456, None, "[tmdbid=123456]", "folder", "unknown")
        result = await scanner.resolve_tmdb_id_candidate(token, {"tmdb_type": "movie"}, ["Show S01E01"])
        self.assertEqual(result["media_type"], "movie")
        self.assertEqual(self.calls, ["candidates"])

    async def test_both_exist_unclear_returns_none(self):
        async def candidates(tmdb_id, lang="zh-CN"):
            return {
                "movie": {"title": "Movie", "media_type": "movie"},
                "tv": {"title": "TV", "media_type": "tv"},
            }

        tmdb.fetch_tmdb_candidates_by_id = candidates
        token = TmdbIdToken(123456, None, "[tmdbid=123456]", "folder", "unknown")
        result = await scanner.resolve_tmdb_id_candidate(token, {"tmdb_type": "movie"}, ["Show S01E01"])
        self.assertIsNone(result)


class AutoScraperOrderTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_tmdb_id = scanner.try_scrape_tmdb_id
        self.orig_bangumi = scanner.try_scrape_bangumi
        self.orig_tmdb = scanner.try_scrape_tmdb
        self.calls = []

    async def asyncTearDown(self):
        scanner.try_scrape_tmdb_id = self.orig_tmdb_id
        scanner.try_scrape_bangumi = self.orig_bangumi
        scanner.try_scrape_tmdb = self.orig_tmdb

    async def test_tmdb_id_success_stops_chain(self):
        async def tmdb_id(tmdb_id, media_type=None, movie=None, candidate_names=None):
            self.calls.append(("tmdb_id", tmdb_id, media_type))
            return {"title": "Exact", "_exact_match": True}

        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return {"title": "Bangumi"}

        async def tmdb_search(name, code):
            self.calls.append(("tmdb", name))
            return {"title": "TMDB"}

        scanner.try_scrape_tmdb_id = tmdb_id
        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb = tmdb_search

        result = await scanner.try_scrape_auto("Movie [tmdb-tv=123456]", "Movie", ["Movie [tmdb-tv=123456]"])
        self.assertEqual(result["title"], "Exact")
        self.assertEqual(self.calls, [("tmdb_id", 123456, "tv")])

    async def test_tmdb_id_failure_falls_back_to_bangumi_then_tmdb(self):
        async def tmdb_id(tmdb_id, media_type=None, movie=None, candidate_names=None):
            self.calls.append(("tmdb_id", tmdb_id))
            return None

        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return None

        async def tmdb_search(name, code):
            self.calls.append(("tmdb", name))
            return {"title": "TMDB"}

        scanner.try_scrape_tmdb_id = tmdb_id
        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb = tmdb_search

        result = await scanner.try_scrape_auto("Movie [tmdbid=123456]", "Movie", ["Movie [tmdbid=123456]"])
        self.assertEqual(result["title"], "TMDB")
        self.assertEqual(self.calls[0], ("tmdb_id", 123456))
        self.assertIn(("bangumi", "Movie"), self.calls)
        self.assertIn(("tmdb", "Movie"), self.calls)

    async def test_no_tmdb_id_bangumi_success_skips_tmdb(self):
        async def tmdb_id(tmdb_id, media_type=None, movie=None, candidate_names=None):
            self.calls.append(("tmdb_id", tmdb_id))
            return None

        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return {"title": "Bangumi"}

        async def tmdb_search(name, code):
            self.calls.append(("tmdb", name))
            return None  # Fail to ensure Bangumi wins

        scanner.try_scrape_tmdb_id = tmdb_id
        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb = tmdb_search

        result = await scanner.try_scrape_auto("Movie", "Movie", ["Movie"])
        self.assertEqual(result["title"], "Bangumi")
        self.assertIn(("bangumi", "Movie"), self.calls)
        self.assertNotIn(("tmdb", "Movie"), self.calls)


class TypedTmdbScraperTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_fetch = tmdb.fetch_tmdb_by_id
        self.orig_detail = scanner._fetch_detail_legacy
        self.orig_bangumi = scanner.try_scrape_bangumi
        self.orig_title = scanner.try_scrape_tmdb_title
        self.orig_api_key = scanner.settings.tmdb_api_key
        self.orig_token = scanner.settings.tmdb_access_token
        scanner.settings.tmdb_api_key = "test"
        scanner.settings.tmdb_access_token = ""
        self.calls = []

    async def asyncTearDown(self):
        tmdb.fetch_tmdb_by_id = self.orig_fetch
        scanner._fetch_detail_legacy = self.orig_detail
        scanner.try_scrape_bangumi = self.orig_bangumi
        scanner.try_scrape_tmdb_title = self.orig_title
        scanner.settings.tmdb_api_key = self.orig_api_key
        scanner.settings.tmdb_access_token = self.orig_token

    async def test_tmdb_movie_id_only_uses_movie_endpoint(self):
        async def detail(source, source_id, media_type=None, exact=True):
            self.calls.append(("id", media_type, int(source_id)))
            return {"title": "Movie", "tmdb_type": media_type}

        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return None

        async def title(name, code, media_type=None):
            self.calls.append(("title", media_type, name))
            return None

        scanner._fetch_detail_legacy = detail
        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb_title = title

        result = await scanner.try_scrape_tmdb_movie(
            "Movie [tmdbid=123456]",
            "Movie",
            ["Movie [tmdbid=123456]"],
        )
        self.assertEqual(result["tmdb_type"], "movie")
        self.assertEqual(self.calls, [("id", "movie", 123456)])

    async def test_tmdb_tv_id_only_uses_tv_endpoint(self):
        async def detail(source, source_id, media_type=None, exact=True):
            self.calls.append(("id", media_type, int(source_id)))
            return {"title": "TV", "tmdb_type": media_type}

        scanner._fetch_detail_legacy = detail
        result = await scanner.try_scrape_tmdb_tv(
            "Show [tmdbid=123456]",
            "Show",
            ["Show [tmdbid=123456]"],
        )
        self.assertEqual(result["tmdb_type"], "tv")
        self.assertEqual(self.calls, [("id", "tv", 123456)])

    async def test_typed_tmdb_id_failure_falls_back_bangumi_then_typed_title(self):
        async def detail(source, source_id, media_type=None, exact=True):
            self.calls.append(("id", media_type))
            return None

        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return None

        async def title(name, code, media_type=None):
            self.calls.append(("title", media_type, name))
            return {"title": "Fallback", "tmdb_type": media_type}

        scanner._fetch_detail_legacy = detail
        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb_title = title

        result = await scanner.try_scrape_tmdb_tv(
            "Show [tmdbid=123456]",
            "Show",
            ["Show [tmdbid=123456]"],
        )
        self.assertEqual(result["title"], "Fallback")
        self.assertEqual(self.calls[0], ("id", "tv"))
        self.assertIn(("bangumi", "Show"), self.calls)
        self.assertIn(("title", "tv", "Show"), self.calls)

    def test_fallback_chain_normalizes_old_tmdb(self):
        self.assertEqual(scanner.build_fallback_chain("tmdb"), ["tmdb_movie"])
        self.assertEqual(scanner.build_fallback_chain("tmdb_movie"), ["tmdb_movie"])
        self.assertEqual(scanner.build_fallback_chain("tmdb_tv"), ["tmdb_tv"])
        self.assertEqual(scanner.build_fallback_chain("bangumi"), ["bangumi", "tmdb_tv_search", "tmdb_movie_search"])
        self.assertEqual(scanner.build_fallback_chain("javdatabase"), ["javdatabase"])
        self.assertNotIn("javdatabase", scanner.build_fallback_chain("auto"))

    async def test_no_tmdb_id_movie_uses_clean_title_bangumi_then_movie_search(self):
        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return None

        async def title(name, code, media_type=None):
            self.calls.append(("title", media_type, name))
            return {"title": "Fallback", "tmdb_type": media_type}

        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb_title = title

        result = await scanner.try_scrape_tmdb_movie(
            "Movie.Name.2024.1080p",
            "Movie Name",
            ["Movie.Name.2024.1080p"],
        )
        self.assertEqual(result["title"], "Fallback")
        self.assertIn(("bangumi", "Movie Name 2024"), self.calls)
        self.assertIn(("title", "movie", "Movie Name 2024"), self.calls)

    async def test_no_tmdb_id_tv_uses_clean_title_bangumi_then_tv_search(self):
        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return None

        async def title(name, code, media_type=None):
            self.calls.append(("title", media_type, name))
            return {"title": "Fallback", "tmdb_type": media_type}

        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb_title = title

        result = await scanner.try_scrape_tmdb_tv(
            "Show.S01E01.1080p",
            "Show",
            ["Show.S01E01.1080p"],
        )
        self.assertEqual(result["title"], "Fallback")
        self.assertIn(("bangumi", "Show"), self.calls)
        self.assertIn(("title", "tv", "Show"), self.calls)


if __name__ == "__main__":
    unittest.main()
