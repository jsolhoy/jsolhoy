"""Scraper for Blabbermouth.net reviews."""

import json
import re
from datetime import datetime, timedelta
from typing import Optional

from rich.console import Console

from src.config import SiteConfig
from src.models import Album, ScrapedReview
from src.scrapers.base import BaseScraper

console = Console()


class BlabbermouthScraper(BaseScraper):
    """
    Scraper for blabbermouth.net reviews.

    Blabbermouth uses a 10-point scale for album reviews.
    RSS feed titles are just album names - we need to fetch the page
    to get the artist name and score.
    """

    # Patterns to match score in review content
    SCORE_PATTERNS = [
        r"(\d+(?:\.\d+)?)\s*/\s*10",
        r"Rating:\s*(\d+(?:\.\d+)?)",
        r"Score:\s*(\d+(?:\.\d+)?)\s*/\s*10",
    ]

    def __init__(self, config: SiteConfig):
        super().__init__(config)
        self.score_scale = config.score_scale or 10.0
        self.min_score = config.min_score_for_threshold or 8.5

    def scrape_reviews(self, since: Optional[datetime] = None) -> list[Album]:
        """Scrape reviews from RSS feed and filter by score."""
        if since is None:
            since = datetime.now() - timedelta(days=7)

        reviews = self.fetch_rss(since)
        albums = []

        for review in reviews:
            # Skip non-review posts (check URL for /reviews/)
            if "/reviews/" not in review.url.lower():
                continue

            console.print(f"[blue]Checking: {review.title}[/blue]")
            album = self.parse_review(review)
            if album:
                albums.append(album)

        console.print(
            f"[green]Found {len(albums)} albums meeting threshold "
            f"from {self.config.display_name}[/green]"
        )
        return albums

    def parse_review(self, review: ScrapedReview) -> Optional[Album]:
        """Parse review by fetching the full page."""
        # Fetch the full page to get artist, album, and score
        soup = self.fetch_page(review.url)
        if not soup:
            return None

        # Extract artist and album from page
        artist, album_title = self._extract_artist_album_from_page(soup, review.title)
        if not artist or not album_title:
            console.print(f"[yellow]Could not find artist for: {review.title}[/yellow]")
            return None

        # Extract score from page
        score = self._extract_score_from_page(soup)
        if score is None:
            console.print(f"[yellow]No score found for: {review.title}[/yellow]")
            return None

        # Create album and normalize score
        album = Album(
            artist=artist,
            title=album_title,
            source_site=self.config.name,
            source_url=review.url,
            review_date=review.published_date,
            raw_score=score,
            score_scale=self.score_scale,
        )
        album.normalize_score()

        # Check threshold (8.5/10 = 85%)
        if not self.meets_threshold(album.normalized_score, threshold=85):
            console.print(
                f"[dim]Below threshold ({score}/{self.score_scale}): "
                f"{album.display_name}[/dim]"
            )
            return None

        console.print(
            f"[green]✓ {album.display_name} - {score}/{self.score_scale} "
            f"({album.normalized_score:.0f}%)[/green]"
        )
        return album

    def _extract_artist_album_from_page(
        self, soup, fallback_title: str
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Extract artist and album name from the review page.

        Blabbermouth structure:
        - Page title: "Reviews - [Album Title] - BLABBERMOUTH.NET"
        - H1 tag: Artist name
        """
        album_title = fallback_title

        # Try to get album from page title (format: "Reviews - Album Title - BLABBERMOUTH.NET")
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text()
            # Extract album from "Reviews - Album Title - BLABBERMOUTH.NET"
            match = re.match(
                r"^Reviews?\s*[-–]\s*(.+?)\s*[-–]\s*BLABBERMOUTH",
                title_text,
                re.IGNORECASE
            )
            if match:
                album_title = match.group(1).strip()

        # Artist is in the H1 tag on Blabbermouth
        h1 = soup.find("h1")
        if h1:
            artist = h1.get_text().strip()
            if artist:
                return artist, album_title

        # Fallback: Try to find artist from JSON-LD structured data
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if "about" in data and isinstance(data["about"], dict):
                        if "name" in data["about"]:
                            return data["about"]["name"], album_title
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        return None, album_title

    def _parse_page_title(self, title: str) -> tuple[Optional[str], Optional[str]]:
        """Parse artist and album from page title."""
        # Remove site name suffix
        title = re.sub(r"\s*[-|]\s*BLABBERMOUTH\.NET.*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*[-|]\s*blabbermouth.*$", "", title, flags=re.IGNORECASE)

        # Pattern: ARTIST - 'Album' or ARTIST - "Album"
        match = re.match(
            r"^(.+?)\s*[-–]\s*['\"](.+?)['\"]",
            title
        )
        if match:
            return match.group(1).strip(), match.group(2).strip()

        # Pattern: ARTIST: 'Album'
        match = re.match(
            r"^(.+?):\s*['\"](.+?)['\"]",
            title
        )
        if match:
            return match.group(1).strip(), match.group(2).strip()

        # Pattern: 'Album' by ARTIST
        match = re.match(
            r"^['\"](.+?)['\"]\s+(?:by|from)\s+(.+?)(?:\s+Review)?$",
            title,
            re.IGNORECASE
        )
        if match:
            return match.group(2).strip(), match.group(1).strip()

        return None, None

    def _extract_score_from_page(self, soup) -> Optional[float]:
        """Extract score from the review page."""
        # Look for score in review content
        content = soup.find(class_=re.compile(r"entry-content|post-content|review", re.I))
        if content:
            score = self._extract_score(content.get_text())
            if score:
                return score

        # Try the entire page
        return self._extract_score(soup.get_text())

    def _extract_score(self, content: str) -> Optional[float]:
        """Extract score from text content."""
        for pattern in self.SCORE_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    if 0 <= score <= 10:
                        return score
                except ValueError:
                    continue
        return None
