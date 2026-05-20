import tempfile
import unittest
from pathlib import Path

from app import scanner, tmdb
from app.scanner import (
    TmdbIdToken,
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
        self.assertEqual(self.calls, [("tmdb_id", 123456), ("bangumi", "Movie"), ("tmdb", "Movie")])

    async def test_no_tmdb_id_bangumi_success_skips_tmdb(self):
        async def tmdb_id(tmdb_id, media_type=None, movie=None, candidate_names=None):
            self.calls.append(("tmdb_id", tmdb_id))
            return None

        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return {"title": "Bangumi"}

        async def tmdb_search(name, code):
            self.calls.append(("tmdb", name))
            return {"title": "TMDB"}

        scanner.try_scrape_tmdb_id = tmdb_id
        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb = tmdb_search

        result = await scanner.try_scrape_auto("Movie", "Movie", ["Movie"])
        self.assertEqual(result["title"], "Bangumi")
        self.assertEqual(self.calls, [("bangumi", "Movie")])


class TypedTmdbScraperTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.orig_fetch = tmdb.fetch_tmdb_by_id
        self.orig_bangumi = scanner.try_scrape_bangumi
        self.orig_title = scanner.try_scrape_tmdb_title
        self.orig_api_key = scanner.settings.tmdb_api_key
        self.orig_token = scanner.settings.tmdb_access_token
        scanner.settings.tmdb_api_key = "test"
        scanner.settings.tmdb_access_token = ""
        self.calls = []

    async def asyncTearDown(self):
        tmdb.fetch_tmdb_by_id = self.orig_fetch
        scanner.try_scrape_bangumi = self.orig_bangumi
        scanner.try_scrape_tmdb_title = self.orig_title
        scanner.settings.tmdb_api_key = self.orig_api_key
        scanner.settings.tmdb_access_token = self.orig_token

    async def test_tmdb_movie_id_only_uses_movie_endpoint(self):
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(("id", media_type, tmdb_id))
            return {"title": "Movie", "media_type": media_type}

        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return None

        async def title(name, code, media_type=None):
            self.calls.append(("title", media_type, name))
            return None

        tmdb.fetch_tmdb_by_id = fetch
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
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(("id", media_type, tmdb_id))
            return {"title": "TV", "media_type": media_type}

        tmdb.fetch_tmdb_by_id = fetch
        result = await scanner.try_scrape_tmdb_tv(
            "Show [tmdbid=123456]",
            "Show",
            ["Show [tmdbid=123456]"],
        )
        self.assertEqual(result["tmdb_type"], "tv")
        self.assertEqual(self.calls, [("id", "tv", 123456)])

    async def test_typed_tmdb_id_failure_falls_back_bangumi_then_typed_title(self):
        async def fetch(tmdb_id, media_type, lang="zh-CN"):
            self.calls.append(("id", media_type))
            return None

        async def bangumi(name, code):
            self.calls.append(("bangumi", name))
            return None

        async def title(name, code, media_type=None):
            self.calls.append(("title", media_type, name))
            return {"title": "Fallback", "tmdb_type": media_type}

        tmdb.fetch_tmdb_by_id = fetch
        scanner.try_scrape_bangumi = bangumi
        scanner.try_scrape_tmdb_title = title

        result = await scanner.try_scrape_tmdb_tv(
            "Show [tmdbid=123456]",
            "Show",
            ["Show [tmdbid=123456]"],
        )
        self.assertEqual(result["title"], "Fallback")
        self.assertEqual(self.calls, [("id", "tv"), ("bangumi", "Show"), ("title", "tv", "Show")])

    def test_fallback_chain_normalizes_old_tmdb(self):
        self.assertEqual(scanner.build_fallback_chain("tmdb"), ["tmdb_movie"])
        self.assertEqual(scanner.build_fallback_chain("tmdb_movie"), ["tmdb_movie"])
        self.assertEqual(scanner.build_fallback_chain("tmdb_tv"), ["tmdb_tv"])
        self.assertEqual(scanner.build_fallback_chain("bangumi"), ["bangumi", "tmdb_tv_search"])


if __name__ == "__main__":
    unittest.main()
