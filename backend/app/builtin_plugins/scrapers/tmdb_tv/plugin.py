from app.scrapers.tmdb_scraper import TMDBScraper


class BuiltinTMDBTVScraper(TMDBScraper):
    def __init__(self):
        super().__init__("tv")
