import tempfile
import unittest
from pathlib import Path

from app import scanner, tmdb
from app.title_match import (
    TmdbIdToken,
    build_search_queries,
    clean_search_title,
    extract_tmdb_id_from_name,
    extract_tmdb_token_from_name,
    infer_tmdb_media_type,
    remove_tmdb_id_token,
)
from app.scrapers.registry import get_scraper, _try_auto_tmdb_id


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
    """Tests _try_auto_tmdb_id used by AutoScraper.full_scrape()."""
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
        result = await _try_auto_tmdb_id(token, {}, ["Title"])
        self.assertEqual(result["tmdb_type"], "movie")
        self.assertEqual(self.calls, ["movie"])

    async def test_explicit_tv_only_requests_tv(self):
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(media_type)
            return {"title": "TV", "media_type": media_type}

        tmdb.fetch_tmdb_by_id = fetch
        token = TmdbIdToken(123456, "tv", "[tmdb-tv=123456]", "folder", "explicit")
        result = await _try_auto_tmdb_id(token, {}, ["Title"])
        self.assertEqual(result["tmdb_type"], "tv")
        self.assertEqual(self.calls, ["tv"])

    async def test_strong_tv_only_requests_tv(self):
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(media_type)
            return {"title": "TV", "media_type": media_type}

        tmdb.fetch_tmdb_by_id = fetch
        token = TmdbIdToken(123456, None, "[tmdbid=123456]", "folder", "unknown")
        result = await _try_auto_tmdb_id(token, {}, ["Show Season 01 S01E01"])
        self.assertEqual(result["tmdb_type"], "tv")
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
            result = await _try_auto_tmdb_id(token, {"path": str(video)}, ["Movie Name (2024)"])
        self.assertEqual(result["tmdb_type"], "movie")
        self.assertEqual(self.calls, ["movie"])

    async def test_unclear_requests_candidates(self):
        async def candidates(tmdb_id, lang="zh-CN"):
            self.calls.append("candidates")
            return {"movie": {"title": "Movie", "media_type": "movie"}, "tv": None}

        tmdb.fetch_tmdb_candidates_by_id = candidates
        token = TmdbIdToken(123456, None, "[tmdbid=123456]", "folder", "unknown")
        result = await _try_auto_tmdb_id(token, {"tmdb_type": "movie"}, ["Show S01E01"])
        self.assertEqual(result["tmdb_type"], "movie")
        self.assertEqual(self.calls, ["candidates"])

    async def test_both_exist_unclear_returns_none(self):
        async def candidates(tmdb_id, lang="zh-CN"):
            return {
                "movie": {"title": "Movie", "media_type": "movie"},
                "tv": {"title": "TV", "media_type": "tv"},
            }

        tmdb.fetch_tmdb_candidates_by_id = candidates
        token = TmdbIdToken(123456, None, "[tmdbid=123456]", "folder", "unknown")
        result = await _try_auto_tmdb_id(token, {"tmdb_type": "movie"}, ["Show S01E01"])
        self.assertIsNone(result)


class AutoScraperOrderTest(unittest.IsolatedAsyncioTestCase):
    """Tests AutoScraper.full_scrape() fallback chain ordering."""

    @staticmethod
    def _patch_auto_steps(tmdb_id_fn, bangumi_fn, tmdb_title_fn):
        """Patch the three fallback steps used by AutoScraper.full_scrape()."""
        import app.scrapers.registry as reg
        from app.scrapers.bangumi_scraper import BangumiScraper

        orig_try = reg._try_auto_tmdb_id
        orig_bangumi = BangumiScraper.full_scrape
        # AutoScraper.full_scrape() uses registry.tmdb_title_search (imported at module level)
        orig_title = reg.tmdb_title_search

        reg._try_auto_tmdb_id = tmdb_id_fn
        BangumiScraper.full_scrape = bangumi_fn
        reg.tmdb_title_search = tmdb_title_fn

        return orig_try, orig_bangumi, orig_title

    @staticmethod
    def _restore_auto_steps(orig_try, orig_bangumi, orig_title):
        import app.scrapers.registry as reg
        from app.scrapers.bangumi_scraper import BangumiScraper

        reg._try_auto_tmdb_id = orig_try
        BangumiScraper.full_scrape = orig_bangumi
        reg.tmdb_title_search = orig_title

    async def test_tmdb_id_success_stops_chain(self):
        calls = []

        async def mock_tmdb_id(token, movie, candidate_names):
            calls.append(("tmdb_id", token.id, token.media_type))
            return {"title": "Exact", "_exact_match": True, "source": "tmdb"}

        # BangumiScraper.full_scrape is a class method: (self, search_name, *, code="", ...)
        async def mock_bangumi(self, search_name, *, code="", candidate_names=None, movie=None):
            calls.append(("bangumi", search_name))
            return None

        async def mock_tmdb_title(clean_title, folder_name, code, media_type=None):
            calls.append(("tmdb", clean_title))
            return None

        orig = self._patch_auto_steps(mock_tmdb_id, mock_bangumi, mock_tmdb_title)
        try:
            scraper = get_scraper("auto")
            result = await scraper.full_scrape("Movie [tmdb-tv=123456]", candidate_names=["Movie [tmdb-tv=123456]"])
            self.assertIsNotNone(result)
            self.assertEqual(result["title"], "Exact")
            self.assertEqual(calls, [("tmdb_id", 123456, "tv")])
        finally:
            self._restore_auto_steps(*orig)

    async def test_tmdb_id_failure_falls_back_to_bangumi_then_tmdb(self):
        calls = []

        async def mock_tmdb_id(token, movie, candidate_names):
            calls.append(("tmdb_id", token.id))
            return None

        async def mock_bangumi(self, search_name, *, code="", candidate_names=None, movie=None):
            calls.append(("bangumi", search_name))
            return None

        async def mock_tmdb_title(clean_title, folder_name, code, media_type=None):
            calls.append(("tmdb", clean_title))
            return {"title": "TMDB", "source": "tmdb", "_search_match_passed": True}

        orig = self._patch_auto_steps(mock_tmdb_id, mock_bangumi, mock_tmdb_title)
        try:
            scraper = get_scraper("auto")
            result = await scraper.full_scrape("Movie [tmdbid=123456]", candidate_names=["Movie [tmdbid=123456]"])
            self.assertIsNotNone(result)
            self.assertEqual(result["title"], "TMDB")
            self.assertEqual(calls[0], ("tmdb_id", 123456))
            self.assertIn(("bangumi", "Movie"), calls)
            self.assertIn(("tmdb", "Movie"), calls)
        finally:
            self._restore_auto_steps(*orig)

    async def test_no_tmdb_id_bangumi_success_skips_tmdb(self):
        calls = []

        async def mock_tmdb_id(token, movie, candidate_names):
            calls.append(("tmdb_id", token.id))
            return None

        async def mock_bangumi(self, search_name, *, code="", candidate_names=None, movie=None):
            calls.append(("bangumi", search_name))
            return {"title": "Bangumi", "source": "bangumi"}

        async def mock_tmdb_title(clean_title, folder_name, code, media_type=None):
            calls.append(("tmdb", clean_title))
            return None

        orig = self._patch_auto_steps(mock_tmdb_id, mock_bangumi, mock_tmdb_title)
        try:
            scraper = get_scraper("auto")
            result = await scraper.full_scrape("Movie", candidate_names=["Movie"])
            self.assertIsNotNone(result)
            self.assertEqual(result["title"], "Bangumi")
            self.assertIn(("bangumi", "Movie"), calls)
            self.assertNotIn(("tmdb", "Movie"), calls)
        finally:
            self._restore_auto_steps(*orig)


class TypedTmdbScraperTest(unittest.IsolatedAsyncioTestCase):
    """Tests TMDBScraper.full_scrape() for tmdb_movie and tmdb_tv chains."""

    async def asyncSetUp(self):
        self.orig_fetch = tmdb.fetch_tmdb_by_id
        self.orig_detail = tmdb.fetch_tmdb_detail
        self.orig_api_key = scanner.settings.tmdb_api_key
        self.orig_token = scanner.settings.tmdb_access_token
        scanner.settings.tmdb_api_key = "test"
        scanner.settings.tmdb_access_token = ""
        self.calls = []

    async def asyncTearDown(self):
        tmdb.fetch_tmdb_by_id = self.orig_fetch
        tmdb.fetch_tmdb_detail = self.orig_detail
        scanner.settings.tmdb_api_key = self.orig_api_key
        scanner.settings.tmdb_access_token = self.orig_token

    @staticmethod
    def _patch_tmdb_steps(detail_fn, bangumi_fn, title_fn):
        """Patch the three fallback steps used by TMDBScraper.full_scrape()."""
        import app.scrapers.tmdb_scraper as tms
        from app.scrapers.bangumi_scraper import BangumiScraper

        orig_detail = tmdb.fetch_tmdb_detail
        orig_bangumi = BangumiScraper.full_scrape
        orig_title = tms.tmdb_title_search

        tmdb.fetch_tmdb_detail = detail_fn
        BangumiScraper.full_scrape = bangumi_fn
        tms.tmdb_title_search = title_fn

        return orig_detail, orig_bangumi, orig_title

    @staticmethod
    def _restore_tmdb_steps(orig_detail, orig_bangumi, orig_title):
        import app.scrapers.tmdb_scraper as tms
        from app.scrapers.bangumi_scraper import BangumiScraper

        tmdb.fetch_tmdb_detail = orig_detail
        BangumiScraper.full_scrape = orig_bangumi
        tms.tmdb_title_search = orig_title

    async def test_tmdb_movie_id_exact_match_uses_movie_endpoint(self):
        """With tmdbid token, TMDB movie scraper uses /movie/{id} first."""
        async def mock_detail(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(("id", media_type, int(tmdb_id)))
            return {"title": "Movie", "media_type": media_type}

        async def mock_bangumi(_inst, search_name, *, code="", candidate_names=None, movie=None):
            self.calls.append(("bangumi", search_name))
            return None

        async def mock_title(clean_title, folder_name, code, media_type=None):
            self.calls.append(("title", media_type, clean_title))
            return None

        orig = self._patch_tmdb_steps(mock_detail, mock_bangumi, mock_title)
        try:
            scraper = get_scraper("tmdb_movie")
            result = await scraper.full_scrape(
                "Movie [tmdbid=123456]", code="Movie",
                candidate_names=["Movie [tmdbid=123456]"]
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["tmdb_type"], "movie")
            self.assertEqual(self.calls, [("id", "movie", 123456)])
        finally:
            self._restore_tmdb_steps(*orig)

    async def test_tmdb_tv_id_exact_match_uses_tv_endpoint(self):
        """With tmdbid token, TMDB tv scraper uses /tv/{id} first."""
        async def mock_detail(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(("id", media_type, int(tmdb_id)))
            return {"title": "TV", "media_type": media_type}

        async def mock_bangumi(_inst, search_name, *, code="", candidate_names=None, movie=None):
            self.calls.append(("bangumi", search_name))
            return None

        async def mock_title(clean_title, folder_name, code, media_type=None):
            self.calls.append(("title", media_type, clean_title))
            return None

        orig = self._patch_tmdb_steps(mock_detail, mock_bangumi, mock_title)
        try:
            scraper = get_scraper("tmdb_tv")
            result = await scraper.full_scrape(
                "Show [tmdbid=123456]", code="Show",
                candidate_names=["Show [tmdbid=123456]"]
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["tmdb_type"], "tv")
            self.assertEqual(self.calls, [("id", "tv", 123456)])
        finally:
            self._restore_tmdb_steps(*orig)

    async def test_typed_tmdb_id_failure_falls_back_bangumi_then_typed_title(self):
        """TMDB ID fails → Bangumi fallback → typed TMDB title search."""
        async def mock_detail(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(("id", media_type))
            return None

        async def mock_bangumi(_inst, search_name, *, code="", candidate_names=None, movie=None):
            self.calls.append(("bangumi", search_name))
            return None

        async def mock_title(clean_title, folder_name, code, media_type=None):
            self.calls.append(("title", media_type, clean_title))
            return {"title": "Fallback", "tmdb_type": media_type, "source": "tmdb", "_search_match_passed": True}

        orig = self._patch_tmdb_steps(mock_detail, mock_bangumi, mock_title)
        try:
            scraper = get_scraper("tmdb_tv")
            result = await scraper.full_scrape(
                "Show [tmdbid=123456]", code="Show",
                candidate_names=["Show [tmdbid=123456]"]
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["title"], "Fallback")
            self.assertEqual(self.calls[0], ("id", "tv"))
            self.assertIn(("bangumi", "Show"), self.calls)
            self.assertIn(("title", "tv", "Show"), self.calls)
        finally:
            self._restore_tmdb_steps(*orig)

    def test_fallback_chain_normalizes_old_tmdb(self):
        self.assertEqual(scanner.build_fallback_chain("tmdb"), ["tmdb_movie"])
        self.assertEqual(scanner.build_fallback_chain("tmdb_movie"), ["tmdb_movie"])
        self.assertEqual(scanner.build_fallback_chain("tmdb_tv"), ["tmdb_tv"])
        self.assertEqual(scanner.build_fallback_chain("bangumi"), ["bangumi", "tmdb_tv_search", "tmdb_movie_search"])
        self.assertEqual(scanner.build_fallback_chain("javdatabase"), ["javdatabase"])
        self.assertNotIn("javdatabase", scanner.build_fallback_chain("auto"))

    async def test_no_tmdb_id_movie_uses_clean_title_bangumi_then_movie_search(self):
        """Without tmdbid, TMDB movie: clean title → Bangumi → movie title search."""
        async def mock_bangumi(_inst, search_name, *, code="", candidate_names=None, movie=None):
            self.calls.append(("bangumi", search_name))
            return None

        async def mock_title(clean_title, folder_name, code, media_type=None):
            self.calls.append(("title", media_type, clean_title))
            return {"title": "Fallback", "tmdb_type": media_type, "source": "tmdb", "_search_match_passed": True}

        import app.scrapers.tmdb_scraper as tms
        from app.scrapers.bangumi_scraper import BangumiScraper

        orig_bangumi = BangumiScraper.full_scrape
        orig_title = tms.tmdb_title_search
        BangumiScraper.full_scrape = mock_bangumi
        tms.tmdb_title_search = mock_title

        try:
            scraper = get_scraper("tmdb_movie")
            result = await scraper.full_scrape(
                "Movie.Name.2024.1080p", code="Movie Name",
                candidate_names=["Movie.Name.2024.1080p"]
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["title"], "Fallback")
            self.assertIn(("bangumi", "Movie Name 2024"), self.calls)
            self.assertIn(("title", "movie", "Movie Name 2024"), self.calls)
        finally:
            BangumiScraper.full_scrape = orig_bangumi
            tms.tmdb_title_search = orig_title

    async def test_no_tmdb_id_tv_uses_clean_title_bangumi_then_tv_search(self):
        """Without tmdbid, TMDB tv: clean title → Bangumi → tv title search."""
        async def mock_bangumi(_inst, search_name, *, code="", candidate_names=None, movie=None):
            self.calls.append(("bangumi", search_name))
            return None

        async def mock_title(clean_title, folder_name, code, media_type=None):
            self.calls.append(("title", media_type, clean_title))
            return {"title": "Fallback", "tmdb_type": media_type, "source": "tmdb", "_search_match_passed": True}

        import app.scrapers.tmdb_scraper as tms
        from app.scrapers.bangumi_scraper import BangumiScraper

        orig_bangumi = BangumiScraper.full_scrape
        orig_title = tms.tmdb_title_search
        BangumiScraper.full_scrape = mock_bangumi
        tms.tmdb_title_search = mock_title

        try:
            scraper = get_scraper("tmdb_tv")
            result = await scraper.full_scrape(
                "Show.S01E01.1080p", code="Show",
                candidate_names=["Show.S01E01.1080p"]
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["title"], "Fallback")
            self.assertIn(("bangumi", "Show"), self.calls)
            self.assertIn(("title", "tv", "Show"), self.calls)
        finally:
            BangumiScraper.full_scrape = orig_bangumi
            tms.tmdb_title_search = orig_title


if __name__ == "__main__":
    unittest.main()
