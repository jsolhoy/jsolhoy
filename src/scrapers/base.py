"""Base scraper class for metal review sites."""

import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from rich.console import Console

from src.config import SiteConfig
from src.models import Album, ScrapedReview

console = Console()


class BaseScraper(ABC):
    """Abstract base class for review site scrapers."""

    def __init__(self, config: SiteConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )

    @abstractmethod
    def scrape_reviews(self, since: Optional[datetime] = None) -> list[Album]:
        """
        Scrape reviews from the site.

        Args:
            since: Only return reviews published after this date.
                   Defaults to 7 days ago.

        Returns:
            List of Album objects that meet the score threshold.
        """
        pass

    @abstractmethod
    def parse_review(self, review: ScrapedReview) -> Optional[Album]:
        """
        Parse a scraped review into an Album object.

        Args:
            review: The raw scraped review data.

        Returns:
            Album object if parsing succeeded and score meets threshold,
            None otherwise.
        """
        pass

    def fetch_rss(self, since: Optional[datetime] = None) -> list[ScrapedReview]:
        """
        Fetch and parse the RSS feed.

        Args:
            since: Only return entries published after this date.

        Returns:
            List of ScrapedReview objects.
        """
        if not self.config.rss_url:
            return []

        if since is None:
            since = datetime.now() - timedelta(days=7)

        console.print(f"[blue]Fetching RSS from {self.config.display_name}...[/blue]")

        feed = feedparser.parse(self.config.rss_url)
        reviews = []

        for entry in feed.entries:
            # Parse published date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6])

            # Skip if older than since date
            if published and published < since:
                continue

            # Get content
            content = ""
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].value
            elif hasattr(entry, "summary"):
                content = entry.summary

            reviews.append(
                ScrapedReview(
                    title=entry.title,
                    url=entry.link,
                    content=content,
                    published_date=published,
                    source_site=self.config.name,
                )
            )

        console.print(f"[green]Found {len(reviews)} entries from RSS[/green]")
        return reviews

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch a page and return parsed HTML.

        Args:
            url: The URL to fetch.

        Returns:
            BeautifulSoup object or None if request failed.
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            time.sleep(1)  # Be polite
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            console.print(f"[red]Error fetching {url}: {e}[/red]")
            return None

    def extract_artist_album(self, title: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract artist and album name from a review title.

        Common formats:
        - "Artist - Album Review"
        - "Artist – Album Review"
        - "Review: Artist - Album"

        Returns:
            Tuple of (artist, album) or (None, None) if parsing failed.
        """
        # Remove common suffixes
        title = re.sub(r"\s*[–-]\s*Review$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*Review:?\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*\[.*?\]\s*$", "", title)

        # Split on dash variants
        parts = re.split(r"\s*[–-]\s*", title, maxsplit=1)

        if len(parts) == 2:
            artist = parts[0].strip()
            album = parts[1].strip()
            if artist and album:
                return artist, album

        return None, None

    def meets_threshold(self, normalized_score: Optional[float], threshold: int = 70) -> bool:
        """Check if a normalized score meets the threshold."""
        if normalized_score is None:
            return False
        return normalized_score >= threshold
