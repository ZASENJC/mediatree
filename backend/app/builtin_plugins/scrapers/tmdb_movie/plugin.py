from app.scrapers.tmdb_scraper import TMDBScraper


class BuiltinTMDBMovieScraper(TMDBScraper):
    def __init__(self):
        super().__init__("movie")
