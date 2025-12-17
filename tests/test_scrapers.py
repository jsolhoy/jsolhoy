"""Tests for scrapers."""

import pytest

from src.config import SiteConfig
from src.scrapers.angry_metal_guy import AngryMetalGuyScraper
from src.scrapers.base import BaseScraper


class TestBaseScraper:
    """Tests for the base scraper functionality."""

    @pytest.fixture
    def config(self):
        return SiteConfig(
            name="test_site",
            display_name="Test Site",
            url="https://example.com",
            rss_url="https://example.com/feed",
            score_scale=5.0,
            min_score_for_threshold=3.5,
            enabled=True,
            scraper_type="rss_with_score",
        )

    def test_extract_artist_album_standard(self, config):
        """Test standard 'Artist - Album' format."""
        scraper = AngryMetalGuyScraper(config)
        artist, album = scraper.extract_artist_album("Cult of Luna - The Long Road North Review")
        assert artist == "Cult of Luna"
        assert album == "The Long Road North"

    def test_extract_artist_album_em_dash(self, config):
        """Test em-dash separator."""
        scraper = AngryMetalGuyScraper(config)
        artist, album = scraper.extract_artist_album("Neurosis – Through Silver in Blood Review")
        assert artist == "Neurosis"
        assert album == "Through Silver in Blood"

    def test_extract_artist_album_no_review_suffix(self, config):
        """Test title without 'Review' suffix."""
        scraper = AngryMetalGuyScraper(config)
        artist, album = scraper.extract_artist_album("Bell Witch - Mirror Reaper")
        assert artist == "Bell Witch"
        assert album == "Mirror Reaper"

    def test_meets_threshold_above(self, config):
        """Test threshold check with score above."""
        scraper = AngryMetalGuyScraper(config)
        assert scraper.meets_threshold(75.0, threshold=70) is True

    def test_meets_threshold_at(self, config):
        """Test threshold check at exact value."""
        scraper = AngryMetalGuyScraper(config)
        assert scraper.meets_threshold(70.0, threshold=70) is True

    def test_meets_threshold_below(self, config):
        """Test threshold check below."""
        scraper = AngryMetalGuyScraper(config)
        assert scraper.meets_threshold(65.0, threshold=70) is False

    def test_meets_threshold_none(self, config):
        """Test threshold check with None score."""
        scraper = AngryMetalGuyScraper(config)
        assert scraper.meets_threshold(None, threshold=70) is False


class TestAngryMetalGuyScraper:
    """Tests for the Angry Metal Guy scraper."""

    @pytest.fixture
    def scraper(self):
        config = SiteConfig(
            name="angry_metal_guy",
            display_name="Angry Metal Guy",
            url="https://www.angrymetalguy.com",
            rss_url="https://www.angrymetalguy.com/feed/",
            score_scale=5.0,
            min_score_for_threshold=3.5,
            enabled=True,
            scraper_type="rss_with_score",
        )
        return AngryMetalGuyScraper(config)

    def test_extract_score_standard(self, scraper):
        """Test score extraction from standard format."""
        content = "Great album! Rating: 4.0/5.0"
        score = scraper._extract_score(content)
        assert score == 4.0

    def test_extract_score_without_decimal(self, scraper):
        """Test score extraction without decimal in scale."""
        content = "Excellent! Rating: 4.5/5"
        score = scraper._extract_score(content)
        assert score == 4.5

    def test_extract_score_no_match(self, scraper):
        """Test score extraction with no score present."""
        content = "This album is amazing but no score given."
        score = scraper._extract_score(content)
        assert score is None

    def test_is_review_with_review_keyword(self, scraper):
        """Test review detection with 'Review' in title."""
        assert scraper._is_review("Cult of Luna - The Long Road North Review") is True

    def test_is_review_with_dash_format(self, scraper):
        """Test review detection with artist-album format."""
        assert scraper._is_review("YOB - Our Raw Heart") is True

    def test_is_review_news_post(self, scraper):
        """Test that news posts are not detected as reviews."""
        assert scraper._is_review("New Album Announcement") is False
