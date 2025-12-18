"""Registry for managing scrapers."""

from typing import Optional, Type

from src.config import SiteConfig
from src.scrapers.base import BaseScraper


class ScraperRegistry:
    """Registry for scraper classes."""

    _scrapers: dict[str, Type[BaseScraper]] = {}

    @classmethod
    def register(cls, scraper_type: str):
        """Decorator to register a scraper class."""

        def decorator(scraper_class: Type[BaseScraper]):
            cls._scrapers[scraper_type] = scraper_class
            return scraper_class

        return decorator

    @classmethod
    def get(cls, scraper_type: str) -> Optional[Type[BaseScraper]]:
        """Get a scraper class by type."""
        return cls._scrapers.get(scraper_type)

    @classmethod
    def create(cls, config: SiteConfig) -> Optional[BaseScraper]:
        """Create a scraper instance from site config."""
        scraper_class = cls.get(config.scraper_type)
        if scraper_class:
            return scraper_class(config)
        return None


def get_scraper(config: SiteConfig) -> Optional[BaseScraper]:
    """
    Get the appropriate scraper for a site configuration.

    This is the main factory function for creating scrapers.
    """
    # Import here to ensure scrapers are registered
    from src.scrapers.angry_metal_guy import AngryMetalGuyScraper
    from src.scrapers.blabbermouth import BlabbermouthScraper
    from src.scrapers.doom_charts import DoomChartsScraper

    # Map scraper types to classes
    scraper_map: dict[str, Type[BaseScraper]] = {
        "rss_with_score": AngryMetalGuyScraper,
        "rss_with_score_10": BlabbermouthScraper,
        "chart_ranking": DoomChartsScraper,
    }

    scraper_class = scraper_map.get(config.scraper_type)
    if scraper_class:
        return scraper_class(config)

    return None
