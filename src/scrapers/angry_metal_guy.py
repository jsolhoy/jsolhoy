"""Scraper for Angry Metal Guy reviews."""

import re
from datetime import datetime, timedelta
from typing import Optional

from rich.console import Console

from src.config import SiteConfig
from src.models import Album, ScrapedReview
from src.scrapers.base import BaseScraper

console = Console()


class AngryMetalGuyScraper(BaseScraper):
    """
    Scraper for angrymetalguy.com reviews.

    Angry Metal Guy uses a 0.5 - 5.0 scoring scale:
    - 5.0: Iconic
    - 4.5: Excellent
    - 4.0: Great
    - 3.5: Very Good
    - 3.0: Good
    - 2.5: Mixed
    - 2.0: Disappointing
    - 1.5: Bad
    - 1.0: Embarrassing
    - 0.5: Unlistenable

    Review titles follow format: "Artist – Album Review"
    Score is typically shown as "Rating: X.X/5.0" in the review.
    """

    # Pattern to match numeric score in review content
    SCORE_PATTERNS = [
        r"Rating:\s*(\d+(?:\.\d+)?)\s*/\s*5(?:\.0)?",
        r"(\d+(?:\.\d+)?)\s*/\s*5\.0\s*$",
        r"Score:\s*(\d+(?:\.\d+)?)\s*/\s*5",
        r"(\d+(?:\.\d+)?)/5\.0",
    ]

    # Map text ratings to numeric scores (AMG uses text like "Rating: Great")
    TEXT_RATING_MAP = {
        "iconic": 5.0,
        "excellent": 4.5,
        "great": 4.0,
        "very good": 3.5,
        "good": 3.0,
        "mixed": 2.5,
        "disappointing": 2.0,
        "bad": 1.5,
        "embarrassing": 1.0,
        "unlistenable": 0.5,
    }

    def __init__(self, config: SiteConfig):
        super().__init__(config)
        self.score_scale = config.score_scale or 5.0
        self.min_score = config.min_score_for_threshold or 3.5

    def scrape_reviews(self, since: Optional[datetime] = None) -> list[Album]:
        """Scrape reviews from RSS feed and filter by score."""
        if since is None:
            since = datetime.now() - timedelta(days=7)

        reviews = self.fetch_rss(since)
        albums = []

        for review in reviews:
            # Skip non-review posts
            if not self._is_review(review.title):
                continue

            album = self.parse_review(review)
            if album:
                albums.append(album)

        console.print(
            f"[green]Found {len(albums)} albums meeting threshold "
            f"from {self.config.display_name}[/green]"
        )
        return albums

    def _is_review(self, title: str) -> bool:
        """Check if a post title looks like a review."""
        title_lower = title.lower()
        # Must contain "review" or typical review format
        if "review" in title_lower:
            return True
        # Check for "Artist - Album" format with dash
        if re.search(r".+\s*[–-]\s*.+", title):
            return True
        return False

    def parse_review(self, review: ScrapedReview) -> Optional[Album]:
        """Parse review content and extract album info with score."""
        # Extract artist and album from title
        artist, album_title = self._parse_title(review.title)
        if not artist or not album_title:
            console.print(f"[yellow]Could not parse title: {review.title}[/yellow]")
            return None

        # Extract score from content
        score = self._extract_score(review.content)

        # If no score in RSS content, try fetching the full page
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

        # Check threshold (3.5/5.0 = 70%)
        if not self.meets_threshold(album.normalized_score):
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
        """Parse artist and album from review title."""
        # Remove "Review" suffix
        title = re.sub(r"\s+Review\s*$", "", title, flags=re.IGNORECASE)

        # Split on em-dash or regular dash
        parts = re.split(r"\s*[–-]\s*", title, maxsplit=1)

        if len(parts) == 2:
            artist = parts[0].strip()
            album = parts[1].strip()

            # Clean up album name (remove quotes if present)
            album = album.strip('"\'""''')

            if artist and album:
                return artist, album

        return None, None

    def _extract_score(self, content: str) -> Optional[float]:
        """Extract score from review content (numeric or text rating)."""
        # Try numeric patterns first
        for pattern in self.SCORE_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    score = float(match.group(1))
                    if 0 <= score <= 5:
                        return score
                except ValueError:
                    continue

        # Try text rating pattern (e.g., "Rating: Great")
        text_pattern = r"Rating:\s*([A-Za-z\s]+?)(?:\n|DR:|$)"
        match = re.search(text_pattern, content, re.IGNORECASE)
        if match:
            rating_text = match.group(1).strip().lower()
            if rating_text in self.TEXT_RATING_MAP:
                return self.TEXT_RATING_MAP[rating_text]

        return None

    def _fetch_score_from_page(self, url: str) -> Optional[float]:
        """Fetch the full review page to extract the score."""
        soup = self.fetch_page(url)
        if not soup:
            return None

        # Look for score in various places
        # Try the review metadata section
        rating_elem = soup.find(class_=re.compile(r"rating|score", re.I))
        if rating_elem:
            score = self._extract_score(rating_elem.get_text())
            if score:
                return score

        # Try the main content
        content = soup.find(class_=re.compile(r"entry-content|post-content", re.I))
        if content:
            score = self._extract_score(content.get_text())
            if score:
                return score

        # Try the entire page text
        return self._extract_score(soup.get_text())
