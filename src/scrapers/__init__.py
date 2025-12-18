"""Scrapers for metal review sites."""

from src.scrapers.base import BaseScraper
from src.scrapers.angry_metal_guy import AngryMetalGuyScraper
from src.scrapers.blabbermouth import BlabbermouthScraper
from src.scrapers.doom_charts import DoomChartsScraper
from src.scrapers.registry import ScraperRegistry, get_scraper

__all__ = [
    "BaseScraper",
    "AngryMetalGuyScraper",
    "BlabbermouthScraper",
    "DoomChartsScraper",
    "ScraperRegistry",
    "get_scraper",
]
