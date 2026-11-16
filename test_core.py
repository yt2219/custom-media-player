"""
test_core.py - Non-GUI tests for the media player's core logic.
Run with:  python test_core.py
"""

import os
import sys
import json
import tempfile
import shutil

# Ensure project dir is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import storage
import playlist

# Redirect storage to a temp dir so we don't pollute real data
test_dir = tempfile.mkdtemp(prefix="mp_test_")
storage.DATA_DIR = test_dir
print(f"Using temp data dir: {test_dir}")

passed = 0
failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        print(f"  ✓ {label}")
        passed += 1
    else:
        print(f"  ✗ FAIL: {label}")
        failed += 1


# --- Storage tests ---
print("\n=== Storage ===")
storage.save_library([{"path": "a.mp3", "title": "Song A"}])
lib = storage.load_library()
check("save/load library", len(lib) == 1 and lib[0]["title"] == "Song A")

storage.save_favorites(["a.mp3", "b.mp3"])
favs = storage.load_favorites()
check("save/load favorites", favs == ["a.mp3", "b.mp3"])

storage.save_playlists({"Rock": ["a.mp3"]})
pls = storage.load_playlists()
check("save/load playlists", "Rock" in pls and pls["Rock"] == ["a.mp3"])

storage.save_recently_played(["c.mp3", "a.mp3"])
rec = storage.load_recently_played()
check("save/load recent", rec == ["c.mp3", "a.mp3"])

storage.save_settings({"volume": 0.5, "shuffle": True})
sets = storage.load_settings()
check("save/load settings", sets["volume"] == 0.5 and sets["shuffle"] is True)

# --- Playlist tests ---
print("\n=== PlaylistManager ===")
pm = playlist.PlaylistManager()
pm.create("My Playlist")
check("create playlist", "My Playlist" in pm.get_names())
pm.add_song("My Playlist", "song1.mp3")
pm.add_song("My Playlist", "song2.mp3")
check("add songs", pm.get_songs("My Playlist") == ["song1.mp3", "song2.mp3"])
pm.remove_song("My Playlist", "song1.mp3")
check("remove song", pm.get_songs("My Playlist") == ["song2.mp3"])
pm.rename("My Playlist", "Renamed")
check("rename playlist", "Renamed" in pm.get_names() and "My Playlist" not in pm.get_names())
pm.delete("Renamed")
check("delete playlist", "Renamed" not in pm.get_names())

# --- PlayQueue tests ---
print("\n=== PlayQueue ===")
q = playlist.PlayQueue()
q.set_queue(["a.mp3", "b.mp3", "c.mp3"], start_path="a.mp3")
check("queue current", q.current() == "a.mp3")
check("queue next", q.next() == "b.mp3")
check("queue next again", q.next() == "c.mp3")
check("queue next end (no repeat)", q.next() is None)

# Repeat all
q.repeat = playlist.REPEAT_ALL
q.set_queue(["a.mp3", "b.mp3"], start_path="a.mp3")
q.next()  # b
nxt = q.next()
check("repeat all wraps", nxt == "a.mp3")

# Repeat one
q.repeat = playlist.REPEAT_ONE
q.set_queue(["a.mp3", "b.mp3"], start_path="a.mp3")
check("repeat one stays", q.next() == "a.mp3")

# Previous
q.repeat = playlist.REPEAT_OFF
q.set_queue(["a.mp3", "b.mp3", "c.mp3"], start_path="c.mp3")
check("previous", q.previous() == "b.mp3")

# Shuffle toggle
q.set_queue(["a.mp3", "b.mp3", "c.mp3", "d.mp3", "e.mp3"], start_path="c.mp3")
q.toggle_shuffle()
check("shuffle on", q.shuffle is True)
check("shuffle preserves current", q.current() == "c.mp3")
q.toggle_shuffle()
check("shuffle off", q.shuffle is False)

# Cycle repeat
q.repeat = playlist.REPEAT_OFF
r = q.cycle_repeat()
check("cycle repeat OFF->ALL", r == playlist.REPEAT_ALL)
r = q.cycle_repeat()
check("cycle repeat ALL->ONE", r == playlist.REPEAT_ONE)
r = q.cycle_repeat()
check("cycle repeat ONE->OFF", r == playlist.REPEAT_OFF)

# --- Library metadata (basic) ---
print("\n=== Library ===")
from library import MusicLibrary, _format_duration
check("format_duration 90s", _format_duration(90) == "1:30")
check("format_duration 0", _format_duration(0) == "0:00")
check("format_duration None", _format_duration(None) == "0:00")

# Library search
ml = MusicLibrary()
ml.songs = [
    {"path": "x.mp3", "title": "Hello World", "artist": "Alice", "album": "A1", "duration": 120, "duration_str": "2:00"},
    {"path": "y.mp3", "title": "Goodbye", "artist": "Bob", "album": "B1", "duration": 60, "duration_str": "1:00"},
]
ml._path_set = {"x.mp3", "y.mp3"}
results = ml.search("hello")
check("search by title", len(results) == 1 and results[0]["title"] == "Hello World")
results = ml.search("bob")
check("search by artist", len(results) == 1 and results[0]["artist"] == "Bob")
results = ml.search("")
check("search empty returns all", len(results) == 2)

# Favorites
ml.toggle_favorite("x.mp3")
check("toggle favorite on", ml.is_favorite("x.mp3"))
ml.toggle_favorite("x.mp3")
check("toggle favorite off", not ml.is_favorite("x.mp3"))

# Recent
ml.add_recent("y.mp3")
ml.add_recent("x.mp3")
check("recent order", ml.recent[0] == os.path.abspath("x.mp3"))

# --- Player import test ---
print("\n=== Player ===")
from player import AudioPlayer
ap = AudioPlayer()
check("player initial state", not ap.is_playing and not ap.is_paused)
check("player volume", ap.volume == 0.7)
ap.set_volume(0.5)
check("set volume", ap.volume == 0.5)
ap.toggle_mute()
check("mute on", ap.muted is True)
ap.toggle_mute()
check("mute off", ap.muted is False)
ap.cleanup()

# --- Cleanup ---
shutil.rmtree(test_dir, ignore_errors=True)

print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
else:
    print("All tests passed! ✓")
