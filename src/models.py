"""Data models for the metal playlist generator."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Album(BaseModel):
    """Represents a reviewed album."""

    artist: str
    title: str
    source_site: str
    source_url: str
    review_date: Optional[datetime] = None
    raw_score: Optional[float] = None
    score_scale: Optional[float] = None
    normalized_score: Optional[float] = Field(
        default=None, description="Score normalized to 0-100 scale"
    )
    genres: list[str] = Field(default_factory=list)

    @property
    def search_query(self) -> str:
        """Generate a Spotify search query for this album."""
        return f"album:{self.title} artist:{self.artist}"

    @property
    def display_name(self) -> str:
        """Human-readable album identifier."""
        return f"{self.artist} - {self.title}"

    def normalize_score(self) -> Optional[float]:
        """Normalize the raw score to a 0-100 scale."""
        if self.raw_score is None or self.score_scale is None:
            return None
        self.normalized_score = (self.raw_score / self.score_scale) * 100
        return self.normalized_score


class SpotifyTrack(BaseModel):
    """Represents a Spotify track."""

    track_id: str
    name: str
    artist: str
    album: str
    uri: str
    popularity: int = 0


class SpotifyAlbum(BaseModel):
    """Represents a Spotify album."""

    album_id: str
    name: str
    artist: str
    uri: str
    tracks: list[SpotifyTrack] = Field(default_factory=list)


class ScrapedReview(BaseModel):
    """Raw scraped review data before processing."""

    title: str
    url: str
    content: str
    published_date: Optional[datetime] = None
    source_site: str
