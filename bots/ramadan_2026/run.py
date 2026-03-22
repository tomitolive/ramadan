import sys
import os

# Add the project root to sys.path to allow imports from core
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.scraper import BaseScraper

if __name__ == "__main__":
    CATEGORIES = ["https://shahheid4u.net/category/مسلسلات-رمضان-2026"]
    bot = BaseScraper(
        name="Ramadan2026",
        categories=CATEGORIES,
        output_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), "data")),
        required_keywords=['رمضان 2026']
    )
    bot.run()
