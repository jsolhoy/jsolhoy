# Metal Playlist Generator

Automatically creates Spotify playlists from highly-rated metal album reviews.

## Features

- Scrapes reviews from metal sites (Angry Metal Guy, Doom Charts, etc.)
- Filters albums scoring 70%+ (normalized across different rating scales)
- Creates/updates a weekly Spotify playlist
- Tracks history to avoid duplicates

## Quick Start

```bash
# Install
pip install -e .

# Configure
cp .env.example .env
# Edit .env with Spotify credentials

# Run
python -m src.main run --days 7
```

See [CLAUDE.md](CLAUDE.md) for full documentation.
