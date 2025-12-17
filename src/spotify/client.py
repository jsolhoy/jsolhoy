"""Spotify API client wrapper."""

from typing import Optional

import spotipy
from rich.console import Console
from spotipy.oauth2 import SpotifyOAuth

from src.config import Settings
from src.models import Album, SpotifyAlbum, SpotifyTrack

console = Console()


class SpotifyClient:
    """Wrapper around the Spotify API."""

    SCOPES = [
        "playlist-modify-public",
        "playlist-modify-private",
        "playlist-read-private",
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: Optional[spotipy.Spotify] = None

    @property
    def client(self) -> spotipy.Spotify:
        """Get or create the authenticated Spotify client."""
        if self._client is None:
            auth_manager = SpotifyOAuth(
                client_id=self.settings.spotify_client_id,
                client_secret=self.settings.spotify_client_secret,
                redirect_uri=self.settings.spotify_redirect_uri,
                scope=" ".join(self.SCOPES),
            )
            self._client = spotipy.Spotify(auth_manager=auth_manager)
        return self._client

    def search_album(self, album: Album) -> Optional[SpotifyAlbum]:
        """
        Search for an album on Spotify.

        Args:
            album: The Album object to search for.

        Returns:
            SpotifyAlbum if found, None otherwise.
        """
        # Try exact search first
        query = f'album:"{album.title}" artist:"{album.artist}"'
        result = self._search_album_query(query)

        if result:
            return result

        # Fall back to looser search
        query = f"{album.artist} {album.title}"
        return self._search_album_query(query)

    def _search_album_query(self, query: str) -> Optional[SpotifyAlbum]:
        """Execute album search query."""
        try:
            results = self.client.search(q=query, type="album", limit=5)
            albums = results.get("albums", {}).get("items", [])

            if not albums:
                return None

            # Take the first result
            sp_album = albums[0]

            return SpotifyAlbum(
                album_id=sp_album["id"],
                name=sp_album["name"],
                artist=sp_album["artists"][0]["name"] if sp_album["artists"] else "Unknown",
                uri=sp_album["uri"],
            )
        except Exception as e:
            console.print(f"[red]Error searching Spotify: {e}[/red]")
            return None

    def get_album_tracks(
        self, spotify_album: SpotifyAlbum, max_tracks: int = 3
    ) -> list[SpotifyTrack]:
        """
        Get tracks from a Spotify album.

        Args:
            spotify_album: The SpotifyAlbum to get tracks from.
            max_tracks: Maximum number of tracks to return.

        Returns:
            List of SpotifyTrack objects.
        """
        try:
            results = self.client.album_tracks(spotify_album.album_id, limit=50)
            track_items = results.get("items", [])

            # Get full track info for popularity scores
            track_ids = [t["id"] for t in track_items if t.get("id")]
            full_tracks = {}

            if track_ids:
                # Spotify API limits to 50 tracks per request
                for i in range(0, len(track_ids), 50):
                    batch = track_ids[i : i + 50]
                    tracks_info = self.client.tracks(batch)
                    for track in tracks_info.get("tracks", []):
                        if track:
                            full_tracks[track["id"]] = track

            tracks = []
            for item in track_items:
                track_id = item.get("id")
                if not track_id:
                    continue

                full_track = full_tracks.get(track_id, {})
                popularity = full_track.get("popularity", 0)

                tracks.append(
                    SpotifyTrack(
                        track_id=track_id,
                        name=item["name"],
                        artist=item["artists"][0]["name"] if item.get("artists") else "Unknown",
                        album=spotify_album.name,
                        uri=item["uri"],
                        popularity=popularity,
                    )
                )

            # Sort by popularity and return top N
            tracks.sort(key=lambda t: t.popularity, reverse=True)
            return tracks[:max_tracks]

        except Exception as e:
            console.print(f"[red]Error getting album tracks: {e}[/red]")
            return []

    def get_user_id(self) -> str:
        """Get the current user's Spotify ID."""
        user = self.client.current_user()
        return user["id"]

    def create_playlist(
        self, name: str, description: str = "", public: bool = True
    ) -> Optional[str]:
        """
        Create a new playlist.

        Returns:
            Playlist ID if successful, None otherwise.
        """
        try:
            user_id = self.get_user_id()
            playlist = self.client.user_playlist_create(
                user_id, name, public=public, description=description
            )
            return playlist["id"]
        except Exception as e:
            console.print(f"[red]Error creating playlist: {e}[/red]")
            return None

    def get_playlist_by_name(self, name: str) -> Optional[str]:
        """
        Find an existing playlist by name.

        Returns:
            Playlist ID if found, None otherwise.
        """
        try:
            offset = 0
            limit = 50

            while True:
                playlists = self.client.current_user_playlists(limit=limit, offset=offset)
                items = playlists.get("items", [])

                for playlist in items:
                    if playlist["name"] == name:
                        return playlist["id"]

                if len(items) < limit:
                    break
                offset += limit

            return None
        except Exception as e:
            console.print(f"[red]Error searching playlists: {e}[/red]")
            return None

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: list[str]) -> bool:
        """
        Add tracks to a playlist.

        Args:
            playlist_id: The playlist ID.
            track_uris: List of Spotify track URIs.

        Returns:
            True if successful.
        """
        if not track_uris:
            return True

        try:
            # Spotify limits to 100 tracks per request
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i : i + 100]
                self.client.playlist_add_items(playlist_id, batch)
            return True
        except Exception as e:
            console.print(f"[red]Error adding tracks: {e}[/red]")
            return False

    def get_playlist_tracks(self, playlist_id: str) -> set[str]:
        """
        Get all track URIs currently in a playlist.

        Returns:
            Set of track URIs.
        """
        try:
            track_uris = set()
            offset = 0
            limit = 100

            while True:
                results = self.client.playlist_tracks(
                    playlist_id, offset=offset, limit=limit, fields="items.track.uri,total"
                )
                items = results.get("items", [])

                for item in items:
                    track = item.get("track")
                    if track and track.get("uri"):
                        track_uris.add(track["uri"])

                if len(items) < limit:
                    break
                offset += limit

            return track_uris
        except Exception as e:
            console.print(f"[red]Error getting playlist tracks: {e}[/red]")
            return set()
