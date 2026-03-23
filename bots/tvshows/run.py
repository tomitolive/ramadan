import sys
import os

# Add the project root to sys.path to allow imports from core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.scraper import BaseScraper

if __name__ == "__main__":
    CATEGORIES = ["https://web32218x.faselhdx.bid/tvshows"]
    bot = BaseScraper(
        name="TVShows",
        categories=CATEGORIES,
        output_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "data")),
    )
    bot.run()
