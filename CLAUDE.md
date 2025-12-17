# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Metal Playlist Generator - An automation tool that scrapes highly-rated album reviews from metal music websites (focusing on doom, sludge, post-metal, and related subgenres) and creates weekly Spotify playlists from albums scoring above a configurable threshold (default: 70%).

## Tech Stack

- **Language**: Python 3.10+
- **Web Scraping**: BeautifulSoup4, feedparser, requests
- **Spotify API**: spotipy
- **Configuration**: pydantic, pydantic-settings, python-dotenv
- **Scheduling**: schedule
- **CLI Output**: rich
- **Testing**: pytest
- **Linting**: ruff, mypy

## Getting Started

```bash
# Install dependencies
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your Spotify credentials

# Run the playlist generator
python -m src.main run
```

### Spotify Setup

1. Create app at https://developer.spotify.com/dashboard
2. Add `http://localhost:8888/callback` as redirect URI
3. Copy Client ID and Secret to `.env`
4. First run will open browser for OAuth authentication

## Development Commands

```bash
# Run playlist generator
python -m src.main run --days 7

# Scrape only (no Spotify update)
python -m src.main scrape --days 7

# Show statistics
python -m src.main stats

# Clear history (keeps playlist)
python -m src.main clear

# Run on schedule (e.g., Sunday 10:00)
python -m src.main schedule --day sunday --time 10:00

# Test
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Format
ruff format src/ tests/
```

## Project Structure

```
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── models.py            # Pydantic data models (Album, SpotifyTrack, etc.)
│   ├── config.py            # Settings and site configuration
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py          # BaseScraper abstract class
│   │   ├── angry_metal_guy.py  # Angry Metal Guy scraper (5-point scale)
│   │   ├── doom_charts.py   # Doom Charts scraper (ranking-based)
│   │   └── registry.py      # Scraper factory
│   └── spotify/
│       ├── __init__.py
│       ├── client.py        # Spotify API wrapper
│       └── playlist.py      # Playlist management and state
├── tests/
│   ├── test_models.py
│   └── test_scrapers.py
├── config/
│   └── sites.json           # Review site configurations
├── data/                    # State files (gitignored)
│   └── state.json
├── pyproject.toml
├── .env.example
└── .gitignore
```

## Code Style & Conventions

- **Type hints**: Use throughout, enforced by mypy strict mode
- **Models**: Use Pydantic for data validation
- **Scrapers**: Inherit from `BaseScraper`, implement `scrape_reviews()` and `parse_review()`
- **Error handling**: Use rich console for user-friendly output
- **Configuration**: Environment variables via pydantic-settings, site configs in JSON
- **Line length**: 100 characters (ruff)

## Important Notes

### Adding New Review Sites

1. Create new scraper in `src/scrapers/` inheriting from `BaseScraper`
2. Implement `scrape_reviews()` and `parse_review()` methods
3. Add site configuration to `config/sites.json`
4. Register scraper type in `src/scrapers/registry.py`

### Score Normalization

- 5-point scales: multiply by 20 (e.g., 4.0 = 80%)
- 10-point scales: multiply by 10 (e.g., 8.0 = 80%)
- Chart-based sites: top N positions automatically pass threshold

### Configured Review Sites

| Site | Type | Scale | Threshold |
|------|------|-------|-----------|
| Angry Metal Guy | RSS + Score | 0-5.0 | 3.5 (70%) |
| Heavy Blog Is Heavy | RSS + Score | 0-5.0 | 3.5 (70%) |
| Doom Charts | Monthly Ranking | Top 20 | All charted |

### State Management

- `data/state.json` tracks added albums/tracks to prevent duplicates
- Playlist ID is preserved when clearing history
- Use `python -m src.main clear` to reset history while keeping playlist
