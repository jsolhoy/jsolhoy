"""Configuration management for the metal playlist generator."""

import json
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Spotify credentials
    spotify_client_id: str = Field(default="")
    spotify_client_secret: str = Field(default="")
    spotify_redirect_uri: str = Field(default="http://localhost:8888/callback")

    # Playlist settings
    spotify_playlist_name: str = Field(default="Weekly Metal Discoveries")
    spotify_playlist_description: str = Field(
        default="Auto-generated playlist from highly-rated metal reviews"
    )

    # Scraping settings
    score_threshold_percent: int = Field(default=70)
    max_tracks_per_album: int = Field(default=3)
    max_albums_per_week: int = Field(default=50)

    # State management
    state_file: str = Field(default="data/state.json")


class SiteConfig:
    """Configuration for a single review site."""

    def __init__(
        self,
        name: str,
        display_name: str,
        url: str,
        rss_url: Optional[str],
        score_scale: Optional[float],
        min_score_for_threshold: Optional[float],
        enabled: bool,
        scraper_type: str,
        **kwargs: dict,
    ):
        self.name = name
        self.display_name = display_name
        self.url = url
        self.rss_url = rss_url
        self.score_scale = score_scale
        self.min_score_for_threshold = min_score_for_threshold
        self.enabled = enabled
        self.scraper_type = scraper_type
        self.extra = kwargs

    @property
    def top_n(self) -> int:
        """For chart-based sites, how many top entries to include."""
        return self.extra.get("top_n", 20)


class SitesConfig:
    """Configuration for all review sites."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._sites: dict[str, SiteConfig] = {}
        self.score_threshold_percent: int = 70
        self._load()

    def _load(self) -> None:
        """Load site configurations from JSON file."""
        with open(self.config_path) as f:
            data = json.load(f)

        self.score_threshold_percent = data.get("score_threshold_percent", 70)

        for site_data in data.get("sites", []):
            site = SiteConfig(**site_data)
            self._sites[site.name] = site

    @property
    def enabled_sites(self) -> list[SiteConfig]:
        """Get all enabled sites."""
        return [s for s in self._sites.values() if s.enabled]

    def get_site(self, name: str) -> Optional[SiteConfig]:
        """Get a site by name."""
        return self._sites.get(name)


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


def get_sites_config(config_path: Optional[Path] = None) -> SitesConfig:
    """Get sites configuration."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "sites.json"
    return SitesConfig(config_path)
