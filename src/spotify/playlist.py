"""Playlist management for the metal playlist generator."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from src.config import Settings
from src.models import Album
from src.spotify.client import SpotifyClient

console = Console()


class PlaylistManager:
    """Manages playlist creation and track additions."""

    def __init__(self, spotify_client: SpotifyClient, settings: Settings):
        self.spotify = spotify_client
        self.settings = settings
        self.state_file = Path(settings.state_file)
        self._state: dict = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load state from file."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                self._state = json.load(f)
        else:
            self._state = {
                "added_albums": [],
                "added_track_uris": [],
                "last_run": None,
                "playlist_id": None,
            }

    def _save_state(self) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2, default=str)

    def get_or_create_playlist(self) -> Optional[str]:
        """Get existing playlist or create a new one."""
        playlist_name = self.settings.spotify_playlist_name

        # Check if we have a saved playlist ID
        playlist_id = self._state.get("playlist_id")
        if playlist_id:
            console.print(f"[blue]Using existing playlist: {playlist_name}[/blue]")
            return playlist_id

        # Try to find existing playlist by name
        playlist_id = self.spotify.get_playlist_by_name(playlist_name)
        if playlist_id:
            self._state["playlist_id"] = playlist_id
            self._save_state()
            console.print(f"[blue]Found existing playlist: {playlist_name}[/blue]")
            return playlist_id

        # Create new playlist
        console.print(f"[blue]Creating new playlist: {playlist_name}[/blue]")
        playlist_id = self.spotify.create_playlist(
            name=playlist_name,
            description=self.settings.spotify_playlist_description,
            public=True,
        )

        if playlist_id:
            self._state["playlist_id"] = playlist_id
            self._save_state()

        return playlist_id

    def is_album_added(self, album: Album) -> bool:
        """Check if an album has already been added."""
        album_key = f"{album.artist.lower()}:{album.title.lower()}"
        return album_key in [a.lower() for a in self._state.get("added_albums", [])]

    def add_albums_to_playlist(self, albums: list[Album]) -> dict:
        """
        Add albums to the playlist.

        Args:
            albums: List of Album objects to add.

        Returns:
            Dict with stats about the operation.
        """
        stats = {
            "albums_processed": 0,
            "albums_found": 0,
            "albums_skipped_duplicate": 0,
            "albums_not_found": 0,
            "tracks_added": 0,
        }

        playlist_id = self.get_or_create_playlist()
        if not playlist_id:
            console.print("[red]Could not get or create playlist[/red]")
            return stats

        # Get existing tracks to avoid duplicates
        existing_tracks = self.spotify.get_playlist_tracks(playlist_id)
        added_uris = set(self._state.get("added_track_uris", []))

        tracks_to_add = []
        results_table = Table(title="Album Processing Results")
        results_table.add_column("Artist", style="cyan")
        results_table.add_column("Album", style="magenta")
        results_table.add_column("Score", style="green")
        results_table.add_column("Status", style="yellow")

        for album in albums:
            stats["albums_processed"] += 1

            # Skip if already added
            if self.is_album_added(album):
                stats["albums_skipped_duplicate"] += 1
                results_table.add_row(
                    album.artist, album.title, f"{album.normalized_score:.0f}%", "Skipped (dup)"
                )
                continue

            # Search for album on Spotify
            spotify_album = self.spotify.search_album(album)
            if not spotify_album:
                stats["albums_not_found"] += 1
                results_table.add_row(
                    album.artist, album.title, f"{album.normalized_score:.0f}%", "Not found"
                )
                continue

            stats["albums_found"] += 1

            # Get tracks from album
            tracks = self.spotify.get_album_tracks(
                spotify_album, max_tracks=self.settings.max_tracks_per_album
            )

            # Filter out already added tracks
            new_tracks = [
                t for t in tracks if t.uri not in existing_tracks and t.uri not in added_uris
            ]

            if new_tracks:
                tracks_to_add.extend(new_tracks)
                stats["tracks_added"] += len(new_tracks)

                # Mark album as added
                album_key = f"{album.artist}:{album.title}"
                self._state.setdefault("added_albums", []).append(album_key)

                for track in new_tracks:
                    self._state.setdefault("added_track_uris", []).append(track.uri)
                    added_uris.add(track.uri)

                results_table.add_row(
                    album.artist,
                    album.title,
                    f"{album.normalized_score:.0f}%",
                    f"Added {len(new_tracks)} tracks",
                )
            else:
                results_table.add_row(
                    album.artist,
                    album.title,
                    f"{album.normalized_score:.0f}%",
                    "Tracks exist",
                )

        console.print(results_table)

        # Add tracks to playlist
        if tracks_to_add:
            track_uris = [t.uri for t in tracks_to_add]
            success = self.spotify.add_tracks_to_playlist(playlist_id, track_uris)
            if success:
                console.print(f"[green]Added {len(track_uris)} tracks to playlist[/green]")
            else:
                console.print("[red]Failed to add tracks to playlist[/red]")
                stats["tracks_added"] = 0

        # Update state
        self._state["last_run"] = datetime.now().isoformat()
        self._save_state()

        return stats

    def clear_state(self) -> None:
        """Clear the saved state (for testing or reset)."""
        self._state = {
            "added_albums": [],
            "added_track_uris": [],
            "last_run": None,
            "playlist_id": self._state.get("playlist_id"),  # Keep playlist ID
        }
        self._save_state()
        console.print("[yellow]State cleared (playlist ID preserved)[/yellow]")

    def get_stats(self) -> dict:
        """Get statistics about the playlist state."""
        return {
            "total_albums_added": len(self._state.get("added_albums", [])),
            "total_tracks_added": len(self._state.get("added_track_uris", [])),
            "last_run": self._state.get("last_run"),
            "playlist_id": self._state.get("playlist_id"),
        }
