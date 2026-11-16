"""
storage.py - Handles saving and loading application data.

Stores the music library, playlists, favorites, and recently played
songs using JSON files so data persists between application restarts.
"""

import json
import os

# Default data directory - stored next to the application
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)


def _data_path(filename):
    """Return the full path for a data file."""
    _ensure_data_dir()
    return os.path.join(DATA_DIR, filename)


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def save_library(songs):
    """
    Save the music library to disk.

    Args:
        songs: list of dicts, each with keys like
               'path', 'title', 'artist', 'album', 'duration'.
    """
    path = _data_path("library.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(songs, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[storage] Could not save library: {e}")


def load_library():
    """
    Load the music library from disk.

    Returns:
        list of song dicts (empty list if no file exists).
    """
    path = _data_path("library.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[storage] Could not load library: {e}")
        return []


# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------

def save_playlists(playlists):
    """
    Save playlists to disk.

    Args:
        playlists: dict mapping playlist name -> list of file paths.
    """
    path = _data_path("playlists.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(playlists, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[storage] Could not save playlists: {e}")


def load_playlists():
    """
    Load playlists from disk.

    Returns:
        dict mapping playlist name -> list of file paths.
    """
    path = _data_path("playlists.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[storage] Could not load playlists: {e}")
        return {}


# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------

def save_favorites(favorites):
    """
    Save favorite song paths to disk.

    Args:
        favorites: list of file path strings.
    """
    path = _data_path("favorites.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(favorites, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[storage] Could not save favorites: {e}")


def load_favorites():
    """
    Load favorite song paths from disk.

    Returns:
        list of file path strings.
    """
    path = _data_path("favorites.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[storage] Could not load favorites: {e}")
        return []


# ---------------------------------------------------------------------------
# Recently Played
# ---------------------------------------------------------------------------

MAX_RECENT = 50  # keep at most this many entries


def save_recently_played(recent):
    """
    Save the recently-played list to disk.

    Args:
        recent: list of file path strings (newest first).
    """
    path = _data_path("recent.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(recent[:MAX_RECENT], f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[storage] Could not save recently played: {e}")


def load_recently_played():
    """
    Load the recently-played list from disk.

    Returns:
        list of file path strings (newest first).
    """
    path = _data_path("recent.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[storage] Could not load recently played: {e}")
        return []


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def save_settings(settings):
    """Save application settings (volume, repeat mode, etc.)."""
    path = _data_path("settings.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"[storage] Could not save settings: {e}")


def load_settings():
    """Load application settings."""
    path = _data_path("settings.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[storage] Could not load settings: {e}")
        return {}
