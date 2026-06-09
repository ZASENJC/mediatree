import tempfile
import unittest
from pathlib import Path

from app import database
from app.config import settings
from app.scanner import _apply_scraped_data, rescrape_movie, scan_media


class SpecialScanTest(unittest.TestCase):
    def test_scan_marks_nested_sp_as_special_and_skips_root_sp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            show = root / "Show"
            special = show / "SP"
            orphan = root / "sp"
            special.mkdir(parents=True)
            orphan.mkdir(parents=True)
            (show / "main.mkv").write_bytes(b"")
            (special / "behind.mkv").write_bytes(b"")
            (orphan / "orphan.mkv").write_bytes(b"")

            rows = {Path(item["path"]).name: item for item in scan_media(str(root))}

        self.assertIn("main.mkv", rows)
        self.assertIn("behind.mkv", rows)
        self.assertNotIn("orphan.mkv", rows)
        self.assertEqual(rows["main.mkv"].get("content_role"), "main")
        self.assertEqual(rows["behind.mkv"].get("content_role"), "special")
        self.assertEqual(rows["behind.mkv"].get("special_parent_levels"), "Show")

    def test_scan_treats_sps_folder_as_special_alias(self):
        aliases = ["SPs", "Specials", "Extras", "Bonus", "Featurettes", "Behind The Scenes", "NCOP", "PV", "Menu"]
        for alias in aliases:
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                special = root / "Show" / "S01" / alias
                special.mkdir(parents=True)
                (special / "menu.mkv").write_bytes(b"")

                rows = {Path(item["path"]).name: item for item in scan_media(str(root))}

                self.assertEqual(rows["menu.mkv"].get("content_role"), "special")
                self.assertEqual(rows["menu.mkv"].get("special_parent_levels"), "Show/S01")
                self.assertEqual(rows["menu.mkv"].get("title"), "menu")
                self.assertEqual(rows["menu.mkv"].get("display_title"), "menu")
                self.assertIsNone(rows["menu.mkv"].get("tmdb_type"))
                self.assertIsNone(rows["menu.mkv"].get("tmdb_episode"))

    def test_scan_does_not_treat_ambiguous_episode_dirs_as_special(self):
        aliases = ["S00", "OVA", "OAD", "specials2"]
        for alias in aliases:
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                folder = root / "Show" / alias
                folder.mkdir(parents=True)
                (folder / "episode.mkv").write_bytes(b"")

                rows = {Path(item["path"]).name: item for item in scan_media(str(root))}

                self.assertEqual(rows["episode.mkv"].get("content_role"), "main")
                self.assertIsNone(rows["episode.mkv"].get("special_parent_levels"))


class SpecialDatabaseTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.old_data_dir = settings.data_dir
        settings.data_dir = str(self.tmp_path / "data")
        await database.close_db_pool()
        await database.init_db()
        self.media_root = str(self.tmp_path / "media")
        Path(self.media_root).mkdir(parents=True)

    async def asyncTearDown(self):
        await database.close_db_pool()
        settings.data_dir = self.old_data_dir
        self.tmp.cleanup()

    async def _movie(self, name: str, **overrides) -> int:
        data = {
            "path": f"{self.media_root}/{name}.mkv",
            "code": name,
            "title": name,
            "duration": 1200,
            "folder_levels": "Show",
            "media_root": self.media_root,
            "content_role": "main",
            "created_at": "2026-01-01 00:00:00",
        }
        data.update(overrides)
        return await database.upsert_movie(data)

    async def test_default_queries_exclude_specials(self):
        main_id = await self._movie("main")
        special_id = await self._movie(
            "bonus",
            path=f"{self.media_root}/Show/sp/bonus.mkv",
            title="Bonus Feature",
            folder_levels="Show/sp",
            content_role="special",
            special_parent_levels="Show",
        )
        await database.add_tag(special_id, "favorite")
        await database.save_progress(special_id, position=120, duration=1200)

        folder_result = await database.get_movies(folder="Show", media_root=self.media_root, limit=20)
        search_result = await database.search_movies("Bonus", media_root=self.media_root)
        favorite_result = await database.get_movies(tag="favorite", media_root=self.media_root, limit=20)
        recent_result = await database.get_recent_watched(media_root=self.media_root)

        self.assertEqual([movie["id"] for movie in folder_result["movies"]], [main_id])
        self.assertEqual(folder_result["total"], 1)
        self.assertEqual(search_result["total"], 0)
        self.assertEqual(favorite_result["total"], 0)
        self.assertEqual(recent_result["total"], 0)

    async def test_special_progress_is_not_saved_for_continue_watching(self):
        special_id = await self._movie(
            "bonus",
            path=f"{self.media_root}/Show/sp/bonus.mkv",
            folder_levels="Show/sp",
            content_role="special",
            special_parent_levels="Show",
        )

        result = await database.save_progress(special_id, position=120, duration=1200)
        progress = await database.get_progress(special_id)
        recent_result = await database.get_recent_watched(media_root=self.media_root)
        db = await database.get_db()
        cur = await db.execute(
            "SELECT COUNT(*) FROM user_data WHERE item_id=?",
            (str(special_id),),
        )
        row_count = (await cur.fetchone())[0]

        self.assertTrue(result["ok"])
        self.assertTrue(result["ignored"])
        self.assertEqual(progress["position"], 0)
        self.assertFalse(progress["played"])
        self.assertEqual(recent_result["total"], 0)
        self.assertEqual(row_count, 0)

    async def test_folder_tree_counts_main_and_specials_separately(self):
        await self._movie("main")
        await self._movie(
            "bonus",
            path=f"{self.media_root}/Show/sp/bonus.mkv",
            title="Bonus Feature",
            folder_levels="Show/sp",
            content_role="special",
            special_parent_levels="Show",
        )

        tree = await database.get_folder_tree_from_db(media_root=self.media_root)

        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["path"], "Show")
        self.assertEqual(tree[0]["movie_count"], 1)
        self.assertEqual(tree[0]["special_count"], 1)
        self.assertFalse(tree[0]["show_specials"])

    async def test_get_folder_specials_respects_visibility_setting(self):
        special_id = await self._movie(
            "bonus",
            path=f"{self.media_root}/Show/sp/bonus.mkv",
            title="Bonus Feature",
            folder_levels="Show/sp",
            content_role="special",
            special_parent_levels="Show",
        )

        hidden = await database.get_folder_specials("Show", self.media_root)
        await database.set_folder_specials_visibility("Show", self.media_root, True)
        visible = await database.get_folder_specials("Show", self.media_root)

        self.assertFalse(hidden["show_specials"])
        self.assertEqual(hidden["special_count"], 1)
        self.assertEqual(hidden["movies"], [])
        self.assertTrue(visible["show_specials"])
        self.assertEqual(visible["special_count"], 1)
        self.assertEqual([movie["id"] for movie in visible["movies"]], [special_id])

    async def test_get_folder_specials_can_include_movies_without_visibility_setting(self):
        special_id = await self._movie(
            "bonus",
            path=f"{self.media_root}/Show/sp/bonus.mkv",
            title="Bonus Feature",
            folder_levels="Show/sp",
            content_role="special",
            special_parent_levels="Show",
        )

        data = await database.get_folder_specials("Show", self.media_root, include_movies=True)

        self.assertFalse(data["show_specials"])
        self.assertEqual(data["special_count"], 1)
        self.assertEqual([movie["id"] for movie in data["movies"]], [special_id])

    async def test_specials_read_as_file_titles_even_with_legacy_scraped_metadata(self):
        path = f"{self.media_root}/Show/sp/bonus-trailer.mkv"
        special_id = await self._movie(
            "bonus-trailer",
            path=path,
            folder_levels="Show/sp",
        )
        db = await database.get_db()
        await db.execute(
            """UPDATE movies SET
               content_role='special',
               special_parent_levels='Show',
               title='Scraped Episode Title',
               original_title='Scraped Original',
               overview='Scraped overview',
               actress='Scraped Actor',
               tmdb_id=12345,
               tmdb_type='tv',
               tmdb_season=1,
               tmdb_episode=99,
               episode_title='Scraped Episode',
               display_title='EP99 Scraped Episode',
               clean_title='Scraped Clean',
               "cast"='[{"name":"Scraped Cast"}]',
               crew='[{"name":"Scraped Crew"}]',
               source_id='12345',
               scraper_source='tmdb'
               WHERE id=?""",
            (special_id,),
        )
        await db.commit()
        await database.set_folder_specials_visibility("Show", self.media_root, True)

        detail = await database.get_movie_detail(special_id)
        specials = await database.get_folder_specials("Show", self.media_root)
        listed = specials["movies"][0]

        for movie in (detail, listed):
            self.assertEqual(movie["title"], "bonus-trailer")
            self.assertEqual(movie["display_title"], "bonus-trailer")
            self.assertEqual(movie["clean_title"], "bonus-trailer")
            self.assertIsNone(movie["original_title"])
            self.assertIsNone(movie["overview"])
            self.assertIsNone(movie["actress"])
            self.assertIsNone(movie["tmdb_id"])
            self.assertIsNone(movie["tmdb_type"])
            self.assertIsNone(movie["tmdb_episode"])
            self.assertIsNone(movie["episode_title"])
            self.assertEqual(movie["cast"], [])
            self.assertEqual(movie["crew"], [])

    async def test_folder_prefix_queries_escape_like_wildcards(self):
        main_id = await self._movie(
            "main-under",
            path=f"{self.media_root}/Show_One/main.mkv",
            folder_levels="Show_One",
        )
        await self._movie(
            "main-x",
            path=f"{self.media_root}/ShowXOne/main.mkv",
            folder_levels="ShowXOne",
        )
        special_id = await self._movie(
            "bonus-under",
            path=f"{self.media_root}/Show_One/sp/bonus.mkv",
            folder_levels="Show_One/sp",
            content_role="special",
            special_parent_levels="Show_One",
        )
        await self._movie(
            "bonus-x",
            path=f"{self.media_root}/ShowXOne/sp/bonus.mkv",
            folder_levels="ShowXOne/sp",
            content_role="special",
            special_parent_levels="ShowXOne",
        )

        folder_result = await database.get_movies(folder="Show_One", media_root=self.media_root, limit=20)
        await database.set_folder_specials_visibility("Show_One", self.media_root, True)
        specials = await database.get_folder_specials("Show_One", self.media_root)

        self.assertEqual([movie["id"] for movie in folder_result["movies"]], [main_id])
        self.assertEqual(specials["special_count"], 1)
        self.assertEqual([movie["id"] for movie in specials["movies"]], [special_id])

    async def test_rescanning_special_clears_scraped_metadata_and_uses_file_title(self):
        path = f"{self.media_root}/Show/SPs/menu.mkv"
        special_id = await self._movie(
            "menu",
            path=path,
            title="Scraped Parent Title",
            original_title="Scraped Original",
            overview="Scraped overview",
            folder_levels="Show/SPs",
            content_role="main",
            special_parent_levels=None,
            tmdb_id=12345,
            tmdb_type="tv",
            tmdb_season=1,
            tmdb_episode=1,
            episode_title="Scraped Episode",
            episode_still="/still.jpg",
            display_title="Scraped Display",
        )
        await database.upsert_movie({
            "path": path,
            "code": "menu",
            "title": "menu",
            "duration": 1200,
            "folder_levels": "Show/SPs",
            "media_root": self.media_root,
            "content_role": "special",
            "special_parent_levels": "Show",
            "clean_title": "menu",
            "display_title": "menu",
            "external_audio_tracks": "[]",
        })

        movie = await database.get_movie_detail(special_id)

        self.assertEqual(movie["content_role"], "special")
        self.assertEqual(movie["title"], "menu")
        self.assertEqual(movie["display_title"], "menu")
        self.assertEqual(movie["clean_title"], "menu")
        self.assertIsNone(movie["original_title"])
        self.assertIsNone(movie["overview"])
        self.assertIsNone(movie["tmdb_id"])
        self.assertIsNone(movie["tmdb_type"])
        self.assertIsNone(movie["tmdb_episode"])
        self.assertIsNone(movie["episode_title"])
        self.assertIsNone(movie["episode_still"])

    async def test_special_movie_rejects_rescrape(self):
        special_id = await self._movie(
            "bonus",
            path=f"{self.media_root}/Show/sp/bonus.mkv",
            folder_levels="Show/sp",
            content_role="special",
            special_parent_levels="Show",
        )

        result = await rescrape_movie(special_id)

        self.assertFalse(result["ok"])
        self.assertIn("Special content", result["error"])

    async def test_folder_scraped_data_does_not_update_specials(self):
        main_id = await self._movie("main")
        special_id = await self._movie(
            "bonus",
            path=f"{self.media_root}/Show/sp/bonus.mkv",
            title="bonus",
            folder_levels="Show/sp",
            content_role="special",
            special_parent_levels="Show",
        )

        affected = await _apply_scraped_data(
            "Show",
            {
                "title": "Scraped Show",
                "original_title": "Scraped Original",
                "overview": "Scraped overview",
                "tmdb_id": 12345,
                "tmdb_type": "tv",
                "source": "tmdb",
                "source_id": "12345",
            },
            self.media_root,
            replace=True,
        )
        main = await database.get_movie_detail(main_id)
        special = await database.get_movie_detail(special_id)

        self.assertEqual(affected, 1)
        self.assertEqual(main["title"], "Scraped Show")
        self.assertEqual(main["tmdb_id"], 12345)
        self.assertEqual(special["title"], "bonus")
        self.assertIsNone(special["tmdb_id"])
        self.assertIsNone(special["source_id"])
