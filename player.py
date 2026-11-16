"""
player.py - Audio playback engine using pygame.mixer.

Provides play, pause, resume, stop, seek, volume, and mute controls.
Uses pygame-ce (Community Edition) for reliable cross-platform audio
without needing external applications like VLC installed.
pygame-ce is a drop-in replacement for pygame with the same import name.
"""

import os
import pygame


class AudioPlayer:
    """
    Wraps pygame.mixer to play audio files.

    Attributes:
        is_playing:  True while audio is actively playing
        is_paused:   True while playback is paused
        volume:      float 0.0 – 1.0
        muted:       True when muted
        current_file: path of the currently loaded file
        duration:    total length of current track in seconds
    """

    def __init__(self):
        # Initialize pygame mixer
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=2048)
        pygame.mixer.init()
        pygame.init()            # needed for the USEREVENT mechanism

        self.is_playing = False
        self.is_paused = False
        self.volume = 0.7
        self.muted = False
        self._pre_mute_volume = 0.7
        self.current_file = None
        self.duration = 0.0
        self._seek_offset = 0.0  # seconds offset when seeking

        pygame.mixer.music.set_volume(self.volume)
        # When a song ends, pygame posts MUSIC_END event
        self.MUSIC_END = pygame.USEREVENT + 1
        pygame.mixer.music.set_endevent(self.MUSIC_END)

    # ------------------------------------------------------------------
    # Core controls
    # ------------------------------------------------------------------

    def play(self, filepath):
        """
        Load and play an audio file from the beginning.

        Args:
            filepath: absolute path to the audio file.

        Returns:
            True on success, raises Exception on failure.
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        self.current_file = filepath
        self.is_playing = True
        self.is_paused = False
        self._seek_offset = 0.0
        self._read_duration(filepath)
        return True

    def pause(self):
        """Pause the currently playing audio."""
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True

    def resume(self):
        """Resume paused audio."""
        if self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False

    def stop(self):
        """Stop playback completely."""
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self._seek_offset = 0.0

    def toggle_pause(self):
        """Toggle between play and pause. Returns new is_paused state."""
        if self.is_paused:
            self.resume()
        elif self.is_playing:
            self.pause()
        return self.is_paused

    # ------------------------------------------------------------------
    # Seek
    # ------------------------------------------------------------------

    def seek(self, seconds):
        """
        Seek to a position in the current track.

        Args:
            seconds: position in seconds from the start.
        """
        if not self.is_playing and not self.is_paused:
            return
        if not self.current_file or not os.path.isfile(self.current_file):
            return

        # Clamp target position to valid range
        if self.duration > 0:
            seconds = max(0.0, min(self.duration, float(seconds)))
        else:
            seconds = max(0.0, float(seconds))

        was_paused = self.is_paused

        try:
            # Temporarily unregister endevent and clear any pending MUSIC_END events
            # so that calling stop() does not trigger a false "song ended" event
            pygame.mixer.music.set_endevent()
            pygame.mixer.music.stop()
            pygame.event.clear(self.MUSIC_END)

            # Reload and play starting from the requested seconds
            try:
                pygame.mixer.music.play(start=seconds)
            except Exception:
                pygame.mixer.music.load(self.current_file)
                pygame.mixer.music.play(start=seconds)

            self._seek_offset = seconds
            self.is_playing = True

            if was_paused:
                pygame.mixer.music.pause()
                self.is_paused = True
            else:
                self.is_paused = False

            # Re-register endevent now that playback from the new position is active
            pygame.mixer.music.set_endevent(self.MUSIC_END)
        except Exception as e:
            pygame.mixer.music.set_endevent(self.MUSIC_END)
            print(f"[player] seek error: {e}")

    # ------------------------------------------------------------------
    # Position / Duration
    # ------------------------------------------------------------------

    def get_position(self):
        """
        Return current playback position in seconds.
        """
        if not self.is_playing:
            return 0.0
        # pygame gives ms since play() or since last seek
        pos_ms = pygame.mixer.music.get_pos()
        if pos_ms < 0:
            return self._seek_offset
        return self._seek_offset + pos_ms / 1000.0

    def _read_duration(self, filepath):
        """Read the track's duration using mutagen."""
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(filepath)
            if audio and audio.info:
                self.duration = audio.info.length
            else:
                self.duration = 0.0
        except Exception:
            self.duration = 0.0

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def set_volume(self, value):
        """Set volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, value))
        if not self.muted:
            pygame.mixer.music.set_volume(self.volume)

    def toggle_mute(self):
        """Toggle mute. Returns new muted state."""
        if self.muted:
            self.muted = False
            pygame.mixer.music.set_volume(self.volume)
        else:
            self.muted = True
            pygame.mixer.music.set_volume(0.0)
        return self.muted

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def is_busy(self):
        """Return True if audio is currently outputting."""
        return pygame.mixer.music.get_busy()

    def check_end_event(self):
        """
        Check if a MUSIC_END event has been posted.

        Call this periodically (e.g. via Tkinter's `after()`).

        Returns:
            True if the song has finished, False otherwise.
        """
        for event in pygame.event.get():
            if event.type == self.MUSIC_END:
                self.is_playing = False
                self.is_paused = False
                return True
        return False

    def cleanup(self):
        """Clean up pygame resources on exit."""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
            pygame.quit()
        except Exception:
            pass
