"""
playlist.py - Manages playlists and the current playback queue.

Provides creating, deleting, and modifying named playlists, plus
a PlayQueue class that tracks the current playback order including
shuffle and repeat modes.
"""

import random
import storage


class PlaylistManager:
    """
    Manages named playlists (stored as playlist_name -> [filepath, ...]).
    """

    def __init__(self):
        self.playlists = {}   # name -> list of paths
        self.load()

    def load(self):
        self.playlists = storage.load_playlists()

    def save(self):
        storage.save_playlists(self.playlists)

    # ------------------------------------------------------------------

    def create(self, name):
        """Create a new empty playlist. Returns False if name exists."""
        if name in self.playlists:
            return False
        self.playlists[name] = []
        self.save()
        return True

    def delete(self, name):
        """Delete a playlist by name."""
        if name in self.playlists:
            del self.playlists[name]
            self.save()

    def rename(self, old_name, new_name):
        """Rename a playlist. Returns False on conflict."""
        if old_name not in self.playlists or new_name in self.playlists:
            return False
        self.playlists[new_name] = self.playlists.pop(old_name)
        self.save()
        return True

    def get_names(self):
        """Return sorted list of playlist names."""
        return sorted(self.playlists.keys())

    def get_songs(self, name):
        """Return list of paths in the playlist."""
        return list(self.playlists.get(name, []))

    def add_song(self, name, filepath):
        """Add a song path to a playlist (no duplicates). Returns True if added, False otherwise."""
        if name not in self.playlists:
            return False
        import os
        norm_fp = os.path.normcase(os.path.abspath(filepath))
        for p in self.playlists[name]:
            if os.path.normcase(os.path.abspath(p)) == norm_fp:
                return False
        self.playlists[name].append(filepath)
        self.save()
        return True

    def remove_song(self, name, filepath):
        """Remove a song path from a playlist."""
        if name not in self.playlists:
            return
        import os
        norm_fp = os.path.normcase(os.path.abspath(filepath))
        self.playlists[name] = [
            p for p in self.playlists[name]
            if os.path.normcase(os.path.abspath(p)) != norm_fp
        ]
        self.save()


# Repeat mode constants
REPEAT_OFF = 0
REPEAT_ALL = 1
REPEAT_ONE = 2


class PlayQueue:
    """
    Manages the current playback order.

    Attributes:
        original:  the original list of file paths
        order:     the (possibly shuffled) playback order
        index:     current position in `order`
        shuffle:   whether shuffle is enabled
        repeat:    REPEAT_OFF, REPEAT_ALL, or REPEAT_ONE
    """

    def __init__(self):
        self.original = []
        self.order = []
        self.index = -1
        self.shuffle = False
        self.repeat = REPEAT_OFF

    def set_queue(self, paths, start_path=None):
        """
        Replace the queue with a new list of paths.

        If start_path is given, begin at that song.
        """
        self.original = list(paths)
        self._rebuild_order()
        if start_path and start_path in self.order:
            self.index = self.order.index(start_path)
        else:
            self.index = 0 if self.order else -1

    def _rebuild_order(self):
        """Rebuild the play order (applying shuffle if needed)."""
        self.order = list(self.original)
        if self.shuffle:
            random.shuffle(self.order)

    def current(self):
        """Return the current song path, or None."""
        if 0 <= self.index < len(self.order):
            return self.order[self.index]
        return None

    def next(self):
        """
        Advance to the next song according to repeat/shuffle rules.

        Returns:
            The next song path, or None if playback should stop.
        """
        if not self.order:
            return None

        if self.repeat == REPEAT_ONE:
            return self.current()

        self.index += 1
        if self.index >= len(self.order):
            if self.repeat == REPEAT_ALL:
                # Reshuffle if shuffle is on
                if self.shuffle:
                    self._rebuild_order()
                self.index = 0
            else:
                self.index = len(self.order) - 1
                return None  # end of queue

        return self.current()

    def previous(self):
        """
        Go back to the previous song.

        Returns:
            The previous song path, or None.
        """
        if not self.order:
            return None

        self.index -= 1
        if self.index < 0:
            if self.repeat == REPEAT_ALL:
                self.index = len(self.order) - 1
            else:
                self.index = 0
        return self.current()

    def toggle_shuffle(self):
        """Toggle shuffle on/off, preserving the current song."""
        current = self.current()
        self.shuffle = not self.shuffle
        self._rebuild_order()
        if current and current in self.order:
            self.index = self.order.index(current)
        return self.shuffle

    def cycle_repeat(self):
        """Cycle through repeat modes: Off -> All -> One -> Off."""
        self.repeat = (self.repeat + 1) % 3
        return self.repeat

    def is_empty(self):
        return len(self.order) == 0
