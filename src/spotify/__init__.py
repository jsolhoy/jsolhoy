"""Spotify integration for the metal playlist generator."""

from src.spotify.client import SpotifyClient
from src.spotify.playlist import PlaylistManager

__all__ = ["SpotifyClient", "PlaylistManager"]
