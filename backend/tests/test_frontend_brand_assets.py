import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
