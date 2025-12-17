"""Main entry point for the metal playlist generator."""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from src.config import get_settings, get_sites_config
from src.models import Album
from src.scrapers import get_scraper
from src.spotify.client import SpotifyClient
from src.spotify.playlist import PlaylistManager

console = Console()


def scrape_all_sites(days_back: int = 7) -> list[Album]:
    """Scrape all enabled sites for highly-rated albums."""
    sites_config = get_sites_config()
    all_albums: list[Album] = []
    since = datetime.now() - timedelta(days=days_back)

    console.print(Panel(f"[bold]Scraping reviews from last {days_back} days[/bold]"))

    for site in sites_config.enabled_sites:
        console.print(f"\n[bold blue]{'=' * 50}[/bold blue]")
        console.print(f"[bold]Processing: {site.display_name}[/bold]")
        console.print(f"[bold blue]{'=' * 50}[/bold blue]")

        scraper = get_scraper(site)
        if not scraper:
            console.print(f"[yellow]No scraper available for {site.name}[/yellow]")
            continue

        try:
            albums = scraper.scrape_reviews(since)
            all_albums.extend(albums)
        except Exception as e:
            console.print(f"[red]Error scraping {site.display_name}: {e}[/red]")

    # Deduplicate albums by artist + title
    seen = set()
    unique_albums = []
    for album in all_albums:
        key = f"{album.artist.lower()}:{album.title.lower()}"
        if key not in seen:
            seen.add(key)
            unique_albums.append(album)

    console.print(f"\n[green]Total unique albums found: {len(unique_albums)}[/green]")
    return unique_albums


def generate_playlist(albums: list[Album]) -> dict:
    """Generate or update the Spotify playlist with the given albums."""
    settings = get_settings()

    if not settings.spotify_client_id or not settings.spotify_client_secret:
        console.print(
            "[red]Spotify credentials not configured. "
            "Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env[/red]"
        )
        return {}

    console.print(Panel("[bold]Updating Spotify Playlist[/bold]"))

    spotify = SpotifyClient(settings)
    playlist_manager = PlaylistManager(spotify, settings)

    # Limit to max albums per week
    albums_to_add = albums[: settings.max_albums_per_week]

    return playlist_manager.add_albums_to_playlist(albums_to_add)


def run_weekly_update(days_back: int = 7) -> None:
    """Run the weekly playlist update."""
    console.print(Panel("[bold green]Metal Playlist Generator - Weekly Update[/bold green]"))
    console.print(f"[dim]Started at: {datetime.now().isoformat()}[/dim]\n")

    # Scrape reviews
    albums = scrape_all_sites(days_back)

    if not albums:
        console.print("[yellow]No new albums found meeting the threshold.[/yellow]")
        return

    # Sort by normalized score (highest first)
    albums.sort(key=lambda a: a.normalized_score or 0, reverse=True)

    # Generate playlist
    stats = generate_playlist(albums)

    # Print summary
    console.print("\n" + "=" * 50)
    console.print(Panel("[bold]Summary[/bold]"))
    console.print(f"Albums processed: {stats.get('albums_processed', 0)}")
    console.print(f"Albums found on Spotify: {stats.get('albums_found', 0)}")
    console.print(f"Albums skipped (duplicate): {stats.get('albums_skipped_duplicate', 0)}")
    console.print(f"Albums not found: {stats.get('albums_not_found', 0)}")
    console.print(f"Tracks added: {stats.get('tracks_added', 0)}")


def show_stats() -> None:
    """Show current playlist statistics."""
    settings = get_settings()
    spotify = SpotifyClient(settings)
    playlist_manager = PlaylistManager(spotify, settings)

    stats = playlist_manager.get_stats()
    console.print(Panel("[bold]Playlist Statistics[/bold]"))
    console.print(f"Total albums added: {stats['total_albums_added']}")
    console.print(f"Total tracks added: {stats['total_tracks_added']}")
    console.print(f"Last run: {stats['last_run'] or 'Never'}")
    console.print(f"Playlist ID: {stats['playlist_id'] or 'Not created'}")


def clear_history() -> None:
    """Clear the album/track history."""
    settings = get_settings()
    spotify = SpotifyClient(settings)
    playlist_manager = PlaylistManager(spotify, settings)
    playlist_manager.clear_state()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Spotify playlists from metal review sites"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run the playlist generator")
    run_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days back to search for reviews (default: 7)",
    )

    # Scrape-only command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape reviews without updating playlist")
    scrape_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days back to search for reviews (default: 7)",
    )

    # Stats command
    subparsers.add_parser("stats", help="Show playlist statistics")

    # Clear command
    subparsers.add_parser("clear", help="Clear album/track history")

    # Schedule command
    schedule_parser = subparsers.add_parser("schedule", help="Run on a schedule")
    schedule_parser.add_argument(
        "--day",
        type=str,
        default="sunday",
        help="Day of week to run (default: sunday)",
    )
    schedule_parser.add_argument(
        "--time",
        type=str,
        default="10:00",
        help="Time to run in HH:MM format (default: 10:00)",
    )

    args = parser.parse_args()

    if args.command == "run":
        run_weekly_update(args.days)
    elif args.command == "scrape":
        albums = scrape_all_sites(args.days)
        console.print(f"\n[bold]Found {len(albums)} albums:[/bold]")
        for album in albums:
            console.print(f"  - {album.display_name} ({album.normalized_score:.0f}%)")
    elif args.command == "stats":
        show_stats()
    elif args.command == "clear":
        clear_history()
    elif args.command == "schedule":
        run_scheduler(args.day, args.time)
    else:
        parser.print_help()


def run_scheduler(day: str, time_str: str) -> None:
    """Run the generator on a schedule."""
    import schedule
    import time

    console.print(
        Panel(f"[bold]Scheduling weekly run for {day.capitalize()} at {time_str}[/bold]")
    )

    # Map day names to schedule methods
    day_map = {
        "monday": schedule.every().monday,
        "tuesday": schedule.every().tuesday,
        "wednesday": schedule.every().wednesday,
        "thursday": schedule.every().thursday,
        "friday": schedule.every().friday,
        "saturday": schedule.every().saturday,
        "sunday": schedule.every().sunday,
    }

    scheduler = day_map.get(day.lower())
    if not scheduler:
        console.print(f"[red]Invalid day: {day}[/red]")
        return

    scheduler.at(time_str).do(run_weekly_update)

    console.print("[green]Scheduler started. Press Ctrl+C to stop.[/green]")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
