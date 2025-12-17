"""Scrapers for metal review sites."""

from src.scrapers.base import BaseScraper
from src.scrapers.angry_metal_guy import AngryMetalGuyScraper
from src.scrapers.doom_charts import DoomChartsScraper
from src.scrapers.registry import ScraperRegistry, get_scraper

__all__ = [
    "BaseScraper",
    "AngryMetalGuyScraper",
    "DoomChartsScraper",
    "ScraperRegistry",
    "get_scraper",
]
