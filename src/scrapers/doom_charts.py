"""Scraper for Doom Charts monthly rankings."""

import re
from datetime import datetime, timedelta
from typing import Optional

from rich.console import Console

from src.config import SiteConfig
from src.models import Album, ScrapedReview
from src.scrapers.base import BaseScraper

console = Console()


class DoomChartsScraper(BaseScraper):
    """
    Scraper for doomcharts.com monthly charts.

    Doom Charts is a community-driven site where ~80 contributors vote
    on the best doom/sludge/stoner albums each month. Albums are ranked
    by aggregate votes rather than individual scores.

    The monthly chart is published on the first Friday of each month.
    We treat "being on the chart" as meeting the quality threshold,
    with optional filtering by chart position (top N).
    """

    # Patterns to identify chart posts
    CHART_TITLE_PATTERNS = [
        r"DOOM CHARTS?\s*[–-]\s*(\w+)\s*(\d{4})",
        r"Doom Charts?\s+(\w+)\s+(\d{4})",
    ]

    # Pattern to match chart entries: "1. Artist – Album"
    ENTRY_PATTERN = r"(\d+)\.\s*(.+?)\s*[–-]\s*(.+?)(?:\s*\(|$)"

    def __init__(self, config: SiteConfig):
        super().__init__(config)
        self.top_n = config.top_n

    def scrape_reviews(self, since: Optional[datetime] = None) -> list[Album]:
        """Scrape the latest chart from RSS feed."""
        if since is None:
            since = datetime.now() - timedelta(days=35)  # ~1 month + buffer

        reviews = self.fetch_rss(since)
        albums = []

        for review in reviews:
            # Only process chart posts, not "Peroration" or other content
            if not self._is_chart_post(review.title):
                continue

            console.print(f"[blue]Processing chart: {review.title}[/blue]")
            chart_albums = self.parse_review(review)
            if chart_albums:
                albums.extend(chart_albums if isinstance(chart_albums, list) else [chart_albums])

        console.print(
            f"[green]Found {len(albums)} albums from {self.config.display_name}[/green]"
        )
        return albums

    def _is_chart_post(self, title: str) -> bool:
        """Check if this is a main chart post (not Peroration, etc)."""
        title_upper = title.upper()

        # Exclude supplementary posts
        if "PERORATION" in title_upper:
            return False

        # Check for chart title patterns
        for pattern in self.CHART_TITLE_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                return True

        return False

    def parse_review(self, review: ScrapedReview) -> Optional[list[Album]]:
        """Parse chart post and extract ranked albums."""
        # We need to fetch the full page since RSS often has truncated content
        soup = self.fetch_page(review.url)
        if not soup:
            return None

        albums = []
        content = soup.find(class_=re.compile(r"entry-content|post-content", re.I))
        if not content:
            content = soup

        # Extract chart entries
        text = content.get_text()
        entries = self._extract_chart_entries(text)

        for position, artist, album_title in entries:
            # Only include top N entries
            if position > self.top_n:
                continue

            album = Album(
                artist=artist.strip(),
                title=album_title.strip(),
                source_site=self.config.name,
                source_url=review.url,
                review_date=review.published_date,
                raw_score=float(self.top_n - position + 1),  # Invert: #1 gets highest score
                score_scale=float(self.top_n),
                normalized_score=100.0,  # All charted albums "pass"
            )

            console.print(f"[green]#{position} {album.display_name}[/green]")
            albums.append(album)

        return albums if albums else None

    def _extract_chart_entries(self, text: str) -> list[tuple[int, str, str]]:
        """
        Extract chart entries from text.

        Returns list of (position, artist, album) tuples.
        """
        entries = []

        # Try structured pattern first
        for match in re.finditer(self.ENTRY_PATTERN, text):
            position = int(match.group(1))
            artist = match.group(2).strip()
            album = match.group(3).strip()

            # Clean up common artifacts
            album = re.sub(r"\s*\(.*$", "", album)  # Remove parentheticals
            artist = artist.strip("*")  # Remove asterisks

            if artist and album and position <= 100:
                entries.append((position, artist, album))

        # Sort by position
        entries.sort(key=lambda x: x[0])

        return entries

    def _extract_from_list_items(self, soup) -> list[tuple[int, str, str]]:
        """Extract entries from HTML list items as fallback."""
        entries = []

        for li in soup.find_all("li"):
            text = li.get_text()
            match = re.match(self.ENTRY_PATTERN, text.strip())
            if match:
                position = int(match.group(1))
                artist = match.group(2).strip()
                album = match.group(3).strip()
                entries.append((position, artist, album))

        return entries
