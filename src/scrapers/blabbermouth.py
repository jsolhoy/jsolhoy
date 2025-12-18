"""Scraper for Blabbermouth.net reviews."""

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
    Reviews are posted with titles like "ARTIST: 'Album' Album Review"
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
            # Skip non-review posts
            if not self._is_review(review.title, review.url):
                continue

            album = self.parse_review(review)
            if album:
                albums.append(album)

        console.print(
            f"[green]Found {len(albums)} albums meeting threshold "
            f"from {self.config.display_name}[/green]"
        )
        return albums

    def _is_review(self, title: str, url: str) -> bool:
        """Check if a post is a review."""
        title_lower = title.lower()
        url_lower = url.lower()

        # Check URL for review indicator
        if "/reviews/" in url_lower or "/cd-reviews/" in url_lower:
            return True

        # Check title for review indicator
        if "album review" in title_lower or "review:" in title_lower:
            return True
        if "' review" in title_lower or "\" review" in title_lower:
            return True

        return False

    def parse_review(self, review: ScrapedReview) -> Optional[Album]:
        """Parse review content and extract album info with score."""
        # Extract artist and album from title
        artist, album_title = self._parse_title(review.title)
        if not artist or not album_title:
            console.print(f"[yellow]Could not parse title: {review.title}[/yellow]")
            return None

        # Try to get score from RSS content first
        score = self._extract_score(review.content)

        # If no score in RSS, fetch the full page
        if score is None:
            score = self._fetch_score_from_page(review.url)

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

        # Check threshold
        if not self.meets_threshold(album.normalized_score, threshold=85):  # 8.5/10 = 85%
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

    def _parse_title(self, title: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse artist and album from review title.

        Common formats:
        - "ARTIST: 'Album Title' Album Review"
        - "ARTIST - 'Album Title' Review"
        - "ARTIST: \"Album Title\" Album Review"
        """
        # Pattern: ARTIST: 'Album' or ARTIST: "Album"
        match = re.match(
            r"^(.+?):\s*['\"](.+?)['\"](?:\s+Album)?\s+Review",
            title,
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip(), match.group(2).strip()

        # Pattern: ARTIST - 'Album' Review
        match = re.match(
            r"^(.+?)\s*[-–]\s*['\"](.+?)['\"](?:\s+Album)?\s+Review",
            title,
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip(), match.group(2).strip()

        # Fallback: use base class method
        return self.extract_artist_album(title)

    def _extract_score(self, content: str) -> Optional[float]:
        """Extract score from review content."""
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

    def _fetch_score_from_page(self, url: str) -> Optional[float]:
        """Fetch the full review page to extract the score."""
        soup = self.fetch_page(url)
        if not soup:
            return None

        # Look for score in review content
        content = soup.find(class_=re.compile(r"entry-content|post-content|review", re.I))
        if content:
            score = self._extract_score(content.get_text())
            if score:
                return score

        # Try the entire page
        return self._extract_score(soup.get_text())
