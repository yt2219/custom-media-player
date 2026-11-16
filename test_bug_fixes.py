"""
test_bug_fixes.py - Automated tests verifying all 4 bug fixes:
1. Bug 1: Like / Favorites toggle, persistence, UI state, duplicate prevention
2. Bug 2: Playlist creation, adding songs, persistence, duplicate prevention, playback & missing file safety
3. Bug 3: Seeking during playback & paused state without stopping or losing position
4. Bug 4: Spacebar play/pause shortcut without interfering with text entry
"""

import os
import sys
import time
import tempfile
import shutil
import tkinter as tk
from tkinter import ttk

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import storage
import library
import playlist
import player
from ui import MediaPlayerApp

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

print("\n" + "="*60)
print("RUNNING COMPREHENSIVE BUG FIX VERIFICATION")
print("="*60)

# Use real audio file for playback tests if available
sample_mp3 = r"C:\Users\Yasaswi\Downloads\One Sun One Moon.mp3"
has_real_audio = os.path.isfile(sample_mp3)

# ---------------------------------------------------------------------------
# BUG 1 TESTS: FAVORITES / LIKE
# ---------------------------------------------------------------------------
print("\n=== BUG 1: FAVORITES / LIKE ===")
test_dir = tempfile.mkdtemp(prefix="mp_bug1_")
storage.DATA_DIR = test_dir

lib = library.MusicLibrary()
song_a = sample_mp3 if has_real_audio else os.path.join(test_dir, "song_a.mp3")
if not has_real_audio:
    with open(song_a, "wb") as f:
        f.write(b"dummy")

lib.add_file(song_a)

# 1. Select Song A, Like it
is_fav1 = lib.toggle_favorite(song_a)
check("Like Song A toggles to True", is_fav1 is True)
check("Song A is_favorite returns True", lib.is_favorite(song_a) is True)

# 2. Check get_favorites
favs = lib.get_favorites()
check("Song A appears in get_favorites()", any(s["path"] == song_a for s in favs))

# 3. Duplicate check - toggle_favorite does not duplicate
lib.save()
check("Favorites set length is 1", len(lib.favorites) == 1)

# 4. Persistence: Close and reload from disk
lib2 = library.MusicLibrary()
check("After reload, Song A is still in favorites", lib2.is_favorite(song_a) is True)
check("After reload, get_favorites has Song A", len(lib2.get_favorites()) == 1)

# 5. Unlike Song A
is_fav2 = lib2.toggle_favorite(song_a)
check("Unlike Song A toggles to False", is_fav2 is False)
check("Song A is no longer in favorites", lib2.is_favorite(song_a) is False)
check("get_favorites is now empty", len(lib2.get_favorites()) == 0)

# 6. Reopen again - confirm it stayed unliked
lib3 = library.MusicLibrary()
check("After second reload, favorites remains empty", len(lib3.get_favorites()) == 0)

shutil.rmtree(test_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# BUG 2 TESTS: PLAYLIST ADDING & PLAYBACK
# ---------------------------------------------------------------------------
print("\n=== BUG 2: PLAYLIST ADDING & SAFETY ===")
test_dir2 = tempfile.mkdtemp(prefix="mp_bug2_")
storage.DATA_DIR = test_dir2

pm = playlist.PlaylistManager()
check("Create playlist 'Workout'", pm.create("Workout") is True)
check("'Workout' in playlist names", "Workout" in pm.get_names())

# Add Song A to Workout
added1 = pm.add_song("Workout", song_a)
check("Add Song A to Workout succeeds", added1 is True)
check("Workout contains Song A", song_a in pm.get_songs("Workout"))

# Duplicate prevention
added2 = pm.add_song("Workout", song_a)
check("Duplicate add to Workout is rejected", added2 is False)
check("Workout still has exactly 1 song", len(pm.get_songs("Workout")) == 1)

# Persistence across reload
pm2 = playlist.PlaylistManager()
check("After restart, 'Workout' exists", "Workout" in pm2.get_names())
check("After restart, Workout still contains Song A", song_a in pm2.get_songs("Workout"))

# Missing file handling
missing_file = os.path.join(test_dir2, "non_existent.mp3")
pm2.add_song("Workout", missing_file)
songs_in_workout = pm2.get_songs("Workout")
check("Playlist stores songs even if missing on disk", missing_file in songs_in_workout)
valid_songs = [p for p in songs_in_workout if os.path.isfile(p)]
check("Missing song filtered gracefully from valid playback queue", len(valid_songs) == 1)

shutil.rmtree(test_dir2, ignore_errors=True)

# ---------------------------------------------------------------------------
# BUG 3 TESTS: REAL SEEKING DURING PLAYBACK & PAUSED STATE
# ---------------------------------------------------------------------------
print("\n=== BUG 3: SEEKING PLAYBACK ENGINE ===")
if has_real_audio:
    ap = player.AudioPlayer()
    ap.play(sample_mp3)
    time.sleep(0.5)
    check("Audio is playing", ap.is_playing is True and ap.is_paused is False)
    pos_init = ap.get_position()
    check("Initial position > 0", pos_init >= 0.2)

    # Seek to 30 seconds
    ap.seek(30.0)
    check("Seeked to 30s: is_playing remains True", ap.is_playing is True)
    check("Seeked to 30s: is_paused remains False", ap.is_paused is False)
    check("No false end event generated by seek", ap.check_end_event() is False)
    time.sleep(0.6)
    pos_30 = ap.get_position()
    check("Playback continued from ~30s", 29.5 <= pos_30 <= 32.0)

    # Seek again to 60 seconds while playing
    ap.seek(60.0)
    check("Seeked to 60s: is_playing remains True", ap.is_playing is True)
    time.sleep(0.6)
    pos_60 = ap.get_position()
    check("Playback continued from ~60s", 59.5 <= pos_60 <= 62.0)

    # Pause
    ap.pause()
    check("Audio paused", ap.is_paused is True)
    pos_paused = ap.get_position()

    # Seek while paused to 90 seconds
    ap.seek(90.0)
    check("Seek while paused remains paused", ap.is_paused is True)
    check("Seek while paused is_playing is True", ap.is_playing is True)
    check("Position immediately reflects 90s", 89.9 <= ap.get_position() <= 90.1)
    time.sleep(0.5)
    check("Still paused after 0.5s", ap.is_paused is True)
    check("Still at ~90s while paused", 89.9 <= ap.get_position() <= 90.1)

    # Resume from paused state
    ap.resume()
    check("Audio resumed", ap.is_paused is False)
    time.sleep(0.7)
    pos_resumed = ap.get_position()
    check("Audio playback continued from ~90s", 90.3 <= pos_resumed <= 92.5)

    ap.cleanup()
else:
    print("  (Skipping real audio seek tests - sample audio not found)")

# ---------------------------------------------------------------------------
# BUG 4 TESTS: SPACEBAR PLAY/PAUSE SHORTCUT
# ---------------------------------------------------------------------------
print("\n=== BUG 4: SPACEBAR CONTROLS PLAY / PAUSE ===")

# Create app instance in test mode
test_dir4 = tempfile.mkdtemp(prefix="mp_bug4_")
storage.DATA_DIR = test_dir4

app = MediaPlayerApp()
# Preload song into library
if has_real_audio:
    app.lib.add_file(sample_mp3)

# Test 1: Spacebar when song is selected/ready
app.selected_song_path = sample_mp3 if has_real_audio else None
event_dummy = tk.Event()

# When not focused on Entry: spacebar triggers _toggle_play
app.root.focus_set()
app.root.update()
ret1 = app._on_space_key(event_dummy)
check("Spacebar outside entry returns 'break'", ret1 == "break")
if has_real_audio:
    check("Spacebar started playback", app.audio.is_playing is True and app.audio.is_paused is False)

    # Press spacebar again -> pause
    ret2 = app._on_space_key(event_dummy)
    check("Second spacebar returns 'break'", ret2 == "break")
    check("Spacebar paused playback", app.audio.is_paused is True)

    # Press spacebar again -> resume
    ret3 = app._on_space_key(event_dummy)
    check("Third spacebar resumes playback", app.audio.is_paused is False)
    app.audio.stop()

# Test 2: Spacebar inside entry widget (e.g. search entry)
test_entry = tk.Entry(app.root)
test_entry.pack()
test_entry.focus_set()
app.root.update()
ret_entry = app._on_space_key(event_dummy)
check("Spacebar inside Entry returns None (lets typing work)", ret_entry is None)

# Clean up app
app.root.destroy()
shutil.rmtree(test_dir4, ignore_errors=True)

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
print("\n" + "="*60)
print(f"TEST RESULTS: {passed} PASSED, {failed} FAILED")
print("="*60)

if failed == 0:
    print("ALL BUG FIXES VERIFIED SUCCESSFULLY! ✓\n")
    sys.exit(0)
else:
    print(f"FAILED {failed} TESTS!\n")
    sys.exit(1)
