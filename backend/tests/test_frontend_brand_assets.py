import unittest
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


class FrontendBrandAssetsTest(unittest.TestCase):
    def test_login_and_site_logos_are_distinct_local_assets(self):
        login = (FRONTEND / "src" / "pages" / "Login.tsx").read_text(encoding="utf-8")
        html = (FRONTEND / "index.html").read_text(encoding="utf-8")

        self.assertIn('src="/login-logo.png"', login)
        self.assertIn('href="/site-logo.png"', html)
        self.assertNotIn('src="/logo.png"', login)
        self.assertNotIn('href="/logo.png"', html)

    def test_brand_assets_exist_and_are_reasonably_sized(self):
        assets = {
            "login-logo.png": 500_000,
            "site-logo.png": 150_000,
        }

        for name, max_size in assets.items():
            path = FRONTEND / "public" / name
            with self.subTest(name=name):
                self.assertTrue(path.is_file(), f"missing {name}")
                self.assertGreater(path.stat().st_size, 1000)
                self.assertLess(path.stat().st_size, max_size)

    def test_brand_asset_paths_are_public_backend_assets(self):
        from app import main

        self.assertIn("/login-logo.png", main.PUBLIC_FRONTEND_PATHS)
        self.assertIn("/site-logo.png", main.PUBLIC_FRONTEND_PATHS)

    def test_built_brand_assets_are_served_without_auth(self):
        if not (FRONTEND / "dist" / "login-logo.png").is_file():
            self.skipTest("frontend/dist has not been built")

        from app.main import app

        with TestClient(app) as client:
            for path in ("/login-logo.png", "/site-logo.png"):
                with self.subTest(path=path):
                    response = client.get(path)

                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers["content-type"], "image/png")
                    self.assertTrue(response.content.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
