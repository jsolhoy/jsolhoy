"""Tests for data models."""

import pytest

from src.models import Album


class TestAlbum:
    """Tests for the Album model."""

    def test_normalize_score_5_scale(self):
        """Test score normalization for 5-point scale."""
        album = Album(
            artist="Cult of Luna",
            title="The Long Road North",
            source_site="angry_metal_guy",
            source_url="https://example.com/review",
            raw_score=4.0,
            score_scale=5.0,
        )
        result = album.normalize_score()
        assert result == 80.0
        assert album.normalized_score == 80.0

    def test_normalize_score_10_scale(self):
        """Test score normalization for 10-point scale."""
        album = Album(
            artist="Isis",
            title="Panopticon",
            source_site="some_site",
            source_url="https://example.com/review",
            raw_score=8.5,
            score_scale=10.0,
        )
        result = album.normalize_score()
        assert result == 85.0

    def test_normalize_score_no_score(self):
        """Test normalization with missing score."""
        album = Album(
            artist="Neurosis",
            title="Through Silver in Blood",
            source_site="doom_charts",
            source_url="https://example.com/review",
        )
        result = album.normalize_score()
        assert result is None

    def test_search_query(self):
        """Test Spotify search query generation."""
        album = Album(
            artist="Bell Witch",
            title="Mirror Reaper",
            source_site="test",
            source_url="https://example.com",
        )
        assert album.search_query == "album:Mirror Reaper artist:Bell Witch"

    def test_display_name(self):
        """Test display name property."""
        album = Album(
            artist="YOB",
            title="Our Raw Heart",
            source_site="test",
            source_url="https://example.com",
        )
        assert album.display_name == "YOB - Our Raw Heart"


class TestScoreThreshold:
    """Tests for score threshold logic."""

    @pytest.mark.parametrize(
        "raw_score,scale,expected_percent",
        [
            (3.5, 5.0, 70.0),  # Exactly at threshold
            (4.0, 5.0, 80.0),  # Above threshold
            (3.0, 5.0, 60.0),  # Below threshold
            (7.0, 10.0, 70.0),  # 10-point scale at threshold
            (5.0, 5.0, 100.0),  # Perfect score
        ],
    )
    def test_various_scales(self, raw_score, scale, expected_percent):
        """Test normalization across different scales."""
        album = Album(
            artist="Test",
            title="Test Album",
            source_site="test",
            source_url="https://example.com",
            raw_score=raw_score,
            score_scale=scale,
        )
        album.normalize_score()
        assert album.normalized_score == expected_percent
