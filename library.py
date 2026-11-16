"""
library.py - Manages the music library.

Handles importing files, scanning folders, reading metadata,
searching/filtering songs, and tracking favorites.
"""

import os
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE
from mutagen.mp4 import MP4

import storage

# Audio formats the player supports
SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".mp4", ".wma", ".aac"}


def _format_duration(seconds):
    """Convert seconds (float) to a 'MM:SS' string."""
    if seconds is None or seconds <= 0:
        return "0:00"
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins}:{secs:02d}"


def read_metadata(filepath):
    """
    Read metadata from a single audio file.

    Returns:
        dict with keys: path, title, artist, album, duration, duration_str
        or None if the file cannot be read.
    """
    if not os.path.isfile(filepath):
        return None

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return None

    title = os.path.splitext(os.path.basename(filepath))[0]
    artist = "Unknown Artist"
    album = "Unknown Album"
    duration = 0.0

    try:
        audio = MutagenFile(filepath)
        if audio is None:
            # Mutagen could not identify the file; use filename only
            return {
                "path": filepath,
                "title": title,
                "artist": artist,
                "album": album,
                "duration": 0,
                "duration_str": "0:00",
            }

        # Duration
        if hasattr(audio, "info") and audio.info is not None:
            duration = audio.info.length if audio.info.length else 0

        # Try reading tags depending on format
        if isinstance(audio, MP3):
            tags = audio.tags
            if tags:
                title = str(tags.get("TIT2", title))
                artist = str(tags.get("TPE1", artist))
                album = str(tags.get("TALB", album))
        elif isinstance(audio, FLAC):
            title = audio.get("title", [title])[0]
            artist = audio.get("artist", [artist])[0]
            album = audio.get("album", [album])[0]
        elif isinstance(audio, OggVorbis):
            title = audio.get("title", [title])[0]
            artist = audio.get("artist", [artist])[0]
            album = audio.get("album", [album])[0]
        elif isinstance(audio, MP4):
            title = audio.tags.get("\xa9nam", [title])[0] if audio.tags else title
            artist = audio.tags.get("\xa9ART", [artist])[0] if audio.tags else artist
            album = audio.tags.get("\xa9alb", [album])[0] if audio.tags else album
        elif isinstance(audio, WAVE):
            tags = audio.tags
            if tags:
                title = str(tags.get("TIT2", title))
                artist = str(tags.get("TPE1", artist))
                album = str(tags.get("TALB", album))
        else:
            # Generic fallback: try common keys
            if hasattr(audio, "tags") and audio.tags:
                title = str(audio.tags.get("title", [title])[0]) if "title" in audio.tags else title
                artist = str(audio.tags.get("artist", [artist])[0]) if "artist" in audio.tags else artist
                album = str(audio.tags.get("album", [album])[0]) if "album" in audio.tags else album

    except Exception:
        # If metadata reading fails, fall back to filename
        pass

    return {
        "path": filepath,
        "title": title,
        "artist": artist,
        "album": album,
        "duration": duration,
        "duration_str": _format_duration(duration),
    }


class MusicLibrary:
    """
    Manages the collection of imported songs.

    Attributes:
        songs:     list of song metadata dicts
        favorites: set of file paths marked as favorite
        recent:    list of file paths (newest first)
    """

    def __init__(self):
        self.songs = []           # list of song dicts
        self.favorites = set()    # set of paths
        self.recent = []          # list of paths (newest first)
        self._path_set = set()    # quick lookup to avoid duplicates
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self):
        """Load songs, favorites, and recently played from storage."""
        raw = storage.load_library()
        self.songs = []
        self._path_set = set()
        for s in raw:
            p = s.get("path", "")
            if p and p not in self._path_set:
                self.songs.append(s)
                self._path_set.add(p)

        self.favorites = set(storage.load_favorites())
        self.recent = storage.load_recently_played()

    def save(self):
        """Persist current state to disk."""
        storage.save_library(self.songs)
        storage.save_favorites(list(self.favorites))
        storage.save_recently_played(self.recent)

    # ------------------------------------------------------------------
    # Importing
    # ------------------------------------------------------------------

    def add_file(self, filepath):
        """
        Import a single audio file.

        Returns:
            The song dict if successful, or None.
        """
        filepath = os.path.abspath(filepath)
        if filepath in self._path_set:
            return None  # already in library

        meta = read_metadata(filepath)
        if meta is None:
            return None

        self.songs.append(meta)
        self._path_set.add(filepath)
        self.save()
        return meta

    def add_folder(self, folder):
        """
        Recursively scan a folder and import all supported files.

        Returns:
            list of newly added song dicts.
        """
        added = []
        for root, _dirs, files in os.walk(folder):
            for fname in sorted(files):
                ext = os.path.splitext(fname)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    full = os.path.join(root, fname)
                    song = self.add_file(full)
                    if song:
                        added.append(song)
        self.save()
        return added

    def remove_song(self, filepath):
        """Remove a song from the library by its path."""
        filepath = os.path.abspath(filepath)
        self.songs = [s for s in self.songs if s["path"] != filepath]
        self._path_set.discard(filepath)
        self.favorites.discard(filepath)
        self.recent = [r for r in self.recent if r != filepath]
        self.save()

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_song(self, filepath):
        """Return the song dict for the given path, or None."""
        if not filepath:
            return None
        norm_target = os.path.normcase(os.path.abspath(filepath))
        for s in self.songs:
            if os.path.normcase(os.path.abspath(s["path"])) == norm_target:
                return s
        return None

    def search(self, query):
        """
        Filter songs whose title, artist, or album contain the query
        (case-insensitive).

        Returns:
            list of matching song dicts.
        """
        q = query.lower().strip()
        if not q:
            return list(self.songs)
        return [
            s for s in self.songs
            if q in s.get("title", "").lower()
            or q in s.get("artist", "").lower()
            or q in s.get("album", "").lower()
        ]

    # ------------------------------------------------------------------
    # Favorites
    # ------------------------------------------------------------------

    def toggle_favorite(self, filepath):
        """Toggle whether a song is a favorite. Returns new state."""
        if not filepath:
            return False
        norm = os.path.normcase(os.path.abspath(filepath))
        matched = None
        for p in self.favorites:
            if os.path.normcase(os.path.abspath(p)) == norm:
                matched = p
                break

        if matched is not None:
            self.favorites.discard(matched)
            is_fav = False
        else:
            self.favorites.add(filepath)
            is_fav = True

        self.save()
        return is_fav

    def is_favorite(self, filepath):
        if not filepath:
            return False
        norm = os.path.normcase(os.path.abspath(filepath))
        return any(os.path.normcase(os.path.abspath(p)) == norm for p in self.favorites)

    def get_favorites(self):
        """Return song dicts that are favorites."""
        fav_norm = {os.path.normcase(os.path.abspath(p)) for p in self.favorites}
        result = []
        matched_paths = set()
        for s in self.songs:
            norm = os.path.normcase(os.path.abspath(s["path"]))
            if norm in fav_norm:
                result.append(s)
                matched_paths.add(norm)
        # Fallback for favorited songs not yet in self.songs
        for p in self.favorites:
            norm = os.path.normcase(os.path.abspath(p))
            if norm not in matched_paths:
                meta = read_metadata(p)
                if meta:
                    result.append(meta)
                    matched_paths.add(norm)
        return result

    # ------------------------------------------------------------------
    # Recently Played
    # ------------------------------------------------------------------

    def add_recent(self, filepath):
        """Record a song as recently played (moves it to front)."""
        filepath = os.path.abspath(filepath)
        self.recent = [r for r in self.recent if r != filepath]
        self.recent.insert(0, filepath)
        self.recent = self.recent[:storage.MAX_RECENT]
        self.save()

    def get_recent_songs(self, limit=20):
        """Return song dicts for recently played songs."""
        result = []
        for p in self.recent[:limit]:
            song = self.get_song(p)
            if song:
                result.append(song)
        return result

    # ------------------------------------------------------------------
    # Missing file check
    # ------------------------------------------------------------------

    def check_missing(self):
        """Return list of paths in the library whose files no longer exist."""
        return [s["path"] for s in self.songs if not os.path.isfile(s["path"])]
