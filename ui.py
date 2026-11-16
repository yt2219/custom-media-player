"""
ui.py - The entire Tkinter user interface for Custom Media Player.

Builds the dark-themed window with sidebar, main content area, and
bottom player control bar.  Ties together player.py, library.py,
playlist.py, and storage.py.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from player import AudioPlayer
from library import MusicLibrary, SUPPORTED_EXTENSIONS
from playlist import PlaylistManager, PlayQueue, REPEAT_OFF, REPEAT_ALL, REPEAT_ONE
import storage

# ======================================================================
# Color palette
# ======================================================================
BG_DARK      = "#121212"
BG_SIDEBAR   = "#181818"
BG_CARD      = "#1e1e1e"
BG_CONTROL   = "#1a1a1a"
BG_HOVER     = "#2a2a2a"
BG_ACTIVE    = "#333333"
FG_PRIMARY   = "#ffffff"
FG_SECONDARY = "#b3b3b3"
FG_DIM       = "#727272"
ACCENT       = "#1db954"     # Spotify-like green accent
ACCENT_HOVER = "#1ed760"
DANGER       = "#e74c3c"


def _format_time(seconds):
    """Format seconds as M:SS."""
    if seconds is None or seconds < 0:
        seconds = 0
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


# ======================================================================
# Main Application Window
# ======================================================================

class MediaPlayerApp:
    """
    Root application class.  Creates the Tk window, wires up all
    components, and runs the main loop.
    """

    def __init__(self):
        # ----- Data layer -----
        self.lib = MusicLibrary()
        self.playlists = PlaylistManager()
        self.queue = PlayQueue()
        self.audio = AudioPlayer()

        # Load saved settings
        settings = storage.load_settings()
        vol = settings.get("volume", 0.7)
        self.audio.set_volume(vol)
        self.queue.shuffle = settings.get("shuffle", False)
        self.queue.repeat = settings.get("repeat", REPEAT_OFF)

        # ----- Tk root -----
        self.root = tk.Tk()
        self.root.title("Custom Media Player")
        self.root.geometry("1100x700")
        self.root.minsize(800, 500)
        self.root.configure(bg=BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to set the window icon (skip if not available)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        # ----- Style -----
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._configure_styles()

        # ----- Layout frames -----
        # Top container (sidebar + main)
        self.top_frame = tk.Frame(self.root, bg=BG_DARK)
        self.top_frame.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar()
        self._build_main_area()
        self._build_control_bar()

        # ----- State -----
        self.current_page = None
        self.selected_song_path = None
        self._seeking = False  # True while user drags the seek bar

        # Spacebar shortcut for Play/Pause
        self.root.bind("<space>", self._on_space_key)

        # Show home page initially
        self._show_home()

        # ----- Periodic update loop -----
        self._tick()

    # ==================================================================
    # Styles
    # ==================================================================

    def _configure_styles(self):
        s = self.style
        # Scale (slider) styles
        s.configure("Horizontal.TScale",
                     background=BG_CONTROL,
                     troughcolor="#333333",
                     sliderthickness=12)
        s.configure("Volume.Horizontal.TScale",
                     background=BG_CONTROL,
                     troughcolor="#333333",
                     sliderthickness=10)
        # Treeview
        s.configure("Dark.Treeview",
                     background=BG_CARD,
                     foreground=FG_PRIMARY,
                     fieldbackground=BG_CARD,
                     borderwidth=0,
                     font=("Segoe UI", 10))
        s.configure("Dark.Treeview.Heading",
                     background=BG_SIDEBAR,
                     foreground=FG_SECONDARY,
                     font=("Segoe UI", 10, "bold"),
                     borderwidth=0)
        s.map("Dark.Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", FG_PRIMARY)])

    # ==================================================================
    # Sidebar
    # ==================================================================

    def _build_sidebar(self):
        self.sidebar = tk.Frame(self.top_frame, bg=BG_SIDEBAR, width=200)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Logo / App name
        tk.Label(self.sidebar, text="🎵 Media Player",
                 font=("Segoe UI", 14, "bold"),
                 bg=BG_SIDEBAR, fg=ACCENT,
                 anchor="w", padx=16, pady=18).pack(fill=tk.X)

        nav_items = [
            ("🏠  Home",            self._show_home),
            ("🎶  Music Library",   self._show_library),
            ("📋  Playlists",       self._show_playlists),
            ("❤️  Favorites",       self._show_favorites),
            ("🕐  Recently Played", self._show_recent),
            ("⚙️  Settings",        self._show_settings),
        ]
        self._nav_buttons = []
        for text, command in nav_items:
            btn = tk.Label(self.sidebar, text=text,
                           font=("Segoe UI", 11),
                           bg=BG_SIDEBAR, fg=FG_SECONDARY,
                           anchor="w", padx=20, pady=10,
                           cursor="hand2")
            btn.pack(fill=tk.X)
            btn.bind("<Button-1>", lambda e, c=command, b=btn: self._nav_click(c, b))
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=BG_HOVER))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(
                bg=BG_ACTIVE if b == self._active_nav else BG_SIDEBAR))
            self._nav_buttons.append(btn)

        self._active_nav = self._nav_buttons[0]
        self._active_nav.configure(bg=BG_ACTIVE, fg=FG_PRIMARY)

    def _nav_click(self, command, btn):
        # Reset previous
        if self._active_nav:
            self._active_nav.configure(bg=BG_SIDEBAR, fg=FG_SECONDARY)
        btn.configure(bg=BG_ACTIVE, fg=FG_PRIMARY)
        self._active_nav = btn
        command()

    # ==================================================================
    # Main Content Area (swappable pages)
    # ==================================================================

    def _build_main_area(self):
        self.main_frame = tk.Frame(self.top_frame, bg=BG_DARK)
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.page_frame = None  # current page widget

    def _clear_main(self):
        """Remove the current page from the main area."""
        if self.page_frame:
            self.page_frame.destroy()
        self.page_frame = tk.Frame(self.main_frame, bg=BG_DARK)
        self.page_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        return self.page_frame

    # ------------------------------------------------------------------
    # Home Page
    # ------------------------------------------------------------------

    def _show_home(self):
        self.current_page = "home"
        f = self._clear_main()

        tk.Label(f, text="Welcome to Custom Media Player",
                 font=("Segoe UI", 22, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(anchor="w", pady=(10, 20))

        # --- Recently Played section ---
        recent_songs = self.lib.get_recent_songs(limit=6)
        if recent_songs:
            tk.Label(f, text="🕐  Recently Played",
                     font=("Segoe UI", 14, "bold"),
                     bg=BG_DARK, fg=FG_PRIMARY).pack(anchor="w", pady=(10, 5))
            cards_frame = tk.Frame(f, bg=BG_DARK)
            cards_frame.pack(fill=tk.X, pady=(0, 15))
            for i, song in enumerate(recent_songs):
                self._song_card(cards_frame, song, i)

        # --- My Music section ---
        tk.Label(f, text="🎶  My Music",
                 font=("Segoe UI", 14, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(anchor="w", pady=(10, 5))
        if not self.lib.songs:
            tk.Label(f, text="No music imported yet. Go to Music Library to add songs.",
                     font=("Segoe UI", 11), bg=BG_DARK, fg=FG_DIM).pack(anchor="w")
        else:
            cards_frame2 = tk.Frame(f, bg=BG_DARK)
            cards_frame2.pack(fill=tk.X, pady=(0, 15))
            for i, song in enumerate(self.lib.songs[:6]):
                self._song_card(cards_frame2, song, i)

        # --- Playlists section ---
        names = self.playlists.get_names()
        if names:
            tk.Label(f, text="📋  Playlists",
                     font=("Segoe UI", 14, "bold"),
                     bg=BG_DARK, fg=FG_PRIMARY).pack(anchor="w", pady=(10, 5))
            pl_frame = tk.Frame(f, bg=BG_DARK)
            pl_frame.pack(fill=tk.X, pady=(0, 15))
            for i, name in enumerate(names[:6]):
                count = len(self.playlists.get_songs(name))
                card = tk.Frame(pl_frame, bg=BG_CARD, padx=12, pady=10,
                                highlightbackground="#333", highlightthickness=1)
                card.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
                tk.Label(card, text=f"📋 {name}",
                         font=("Segoe UI", 10, "bold"),
                         bg=BG_CARD, fg=FG_PRIMARY).pack(anchor="w")
                tk.Label(card, text=f"{count} songs",
                         font=("Segoe UI", 9), bg=BG_CARD, fg=FG_DIM).pack(anchor="w")
                card.bind("<Button-1>", lambda e, n=name: self._play_playlist(n))
                for child in card.winfo_children():
                    child.bind("<Button-1>", lambda e, n=name: self._play_playlist(n))

    def _song_card(self, parent, song, col):
        """Create a small clickable card for a song."""
        card = tk.Frame(parent, bg=BG_CARD, padx=12, pady=10,
                        highlightbackground="#333", highlightthickness=1)
        card.grid(row=0, column=col, padx=5, pady=5, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        title = song.get("title", "Unknown")[:25]
        artist = song.get("artist", "")[:20]

        tk.Label(card, text=f"🎵 {title}",
                 font=("Segoe UI", 10, "bold"),
                 bg=BG_CARD, fg=FG_PRIMARY, anchor="w").pack(fill=tk.X)
        tk.Label(card, text=artist,
                 font=("Segoe UI", 9), bg=BG_CARD, fg=FG_DIM, anchor="w").pack(fill=tk.X)

        # Click to play
        path = song["path"]
        card.bind("<Button-1>", lambda e, p=path: self._play_song(p))
        for child in card.winfo_children():
            child.bind("<Button-1>", lambda e, p=path: self._play_song(p))

        # Hover
        card.bind("<Enter>", lambda e: card.configure(bg=BG_HOVER))
        card.bind("<Leave>", lambda e: card.configure(bg=BG_CARD))

    # ------------------------------------------------------------------
    # Music Library Page
    # ------------------------------------------------------------------

    def _show_library(self):
        self.current_page = "library"
        f = self._clear_main()

        # Header row
        header = tk.Frame(f, bg=BG_DARK)
        header.pack(fill=tk.X, pady=(0, 10))
        tk.Label(header, text="🎶  Music Library",
                 font=("Segoe UI", 18, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(side=tk.LEFT)

        btn_frame = tk.Frame(header, bg=BG_DARK)
        btn_frame.pack(side=tk.RIGHT)
        self.btn_lib_fav = self._make_button(btn_frame, "♡ Favorite", self._toggle_like)
        self.btn_lib_fav.pack(side=tk.LEFT, padx=4)
        self.btn_lib_add_pl = self._make_button(btn_frame, "➕ Add to Playlist", self._add_selected_to_playlist)
        self.btn_lib_add_pl.pack(side=tk.LEFT, padx=4)
        self._make_button(btn_frame, "📁 Add Folder", self._add_folder).pack(side=tk.LEFT, padx=4)
        self._make_button(btn_frame, "📄 Add Files", self._add_files).pack(side=tk.LEFT, padx=4)

        # Search bar
        search_frame = tk.Frame(f, bg=BG_CARD, padx=8, pady=6,
                                highlightbackground="#333", highlightthickness=1)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(search_frame, text="🔍", bg=BG_CARD, fg=FG_DIM,
                 font=("Segoe UI", 12)).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_library())
        search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                font=("Segoe UI", 11),
                                bg=BG_CARD, fg=FG_PRIMARY,
                                insertbackground=FG_PRIMARY,
                                border=0, highlightthickness=0)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # Song list (Treeview)
        tree_frame = tk.Frame(f, bg=BG_DARK)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("title", "artist", "album", "duration")
        self.lib_tree = ttk.Treeview(tree_frame, columns=columns,
                                      show="headings", style="Dark.Treeview",
                                      selectmode="extended")
        self.lib_tree.heading("title",    text="Title")
        self.lib_tree.heading("artist",   text="Artist")
        self.lib_tree.heading("album",    text="Album")
        self.lib_tree.heading("duration", text="Duration")
        self.lib_tree.column("title",    width=280, minwidth=120)
        self.lib_tree.column("artist",   width=180, minwidth=80)
        self.lib_tree.column("album",    width=180, minwidth=80)
        self.lib_tree.column("duration", width=70,  minwidth=50, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                   command=self.lib_tree.yview)
        self.lib_tree.configure(yscrollcommand=scrollbar.set)
        self.lib_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.lib_tree.bind("<Double-1>", self._on_lib_double_click)
        self.lib_tree.bind("<<TreeviewSelect>>", self._on_lib_select)

        # Right-click context menu
        self.lib_menu = tk.Menu(self.root, tearoff=0,
                                bg=BG_CARD, fg=FG_PRIMARY,
                                activebackground=ACCENT)
        self.lib_menu.add_command(label="▶  Play", command=self._ctx_play)
        self.lib_menu.add_command(label="❤️  Toggle Favorite", command=self._ctx_toggle_fav)
        self.lib_menu.add_separator()
        self.lib_menu.add_command(label="📋  Add to Playlist…", command=self._ctx_add_to_playlist)
        self.lib_menu.add_separator()
        self.lib_menu.add_command(label="🗑  Remove from Library", command=self._ctx_remove)
        self.lib_tree.bind("<Button-3>", self._show_lib_menu)

        self._populate_library()
        self._update_fav_btn()

    def _populate_library(self, songs=None):
        """Fill the treeview with songs."""
        if not hasattr(self, "lib_tree"):
            return
        self.lib_tree.delete(*self.lib_tree.get_children())
        items = songs if songs is not None else self.lib.songs
        for s in items:
            fav = "❤️ " if self.lib.is_favorite(s["path"]) else ""
            missing = "" if os.path.isfile(s["path"]) else " ⚠️"
            self.lib_tree.insert("", tk.END,
                                  iid=s["path"],
                                  values=(fav + s.get("title", "Unknown") + missing,
                                          s.get("artist", ""),
                                          s.get("album", ""),
                                          s.get("duration_str", "0:00")))

    def _filter_library(self):
        q = self.search_var.get()
        results = self.lib.search(q)
        self._populate_library(results)

    # --- Library actions ---

    def _add_files(self):
        filetypes = [("Audio Files", " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)),
                     ("All Files", "*.*")]
        paths = filedialog.askopenfilenames(title="Add Audio Files",
                                             filetypes=filetypes)
        if not paths:
            return
        count = 0
        for p in paths:
            if self.lib.add_file(p):
                count += 1
        if hasattr(self, "lib_tree"):
            self._populate_library()
        if count:
            messagebox.showinfo("Import Complete", f"Added {count} song(s) to library.")

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Add Music Folder")
        if not folder:
            return
        added = self.lib.add_folder(folder)
        if hasattr(self, "lib_tree"):
            self._populate_library()
        messagebox.showinfo("Import Complete",
                            f"Added {len(added)} new song(s) from folder.")

    def _on_lib_double_click(self, event):
        sel = self.lib_tree.selection()
        if sel:
            path = sel[0]
            # Set the full library as the queue
            all_paths = [s["path"] for s in self.lib.songs]
            self.queue.set_queue(all_paths, start_path=path)
            self._play_song(path)

    def _show_lib_menu(self, event):
        item = self.lib_tree.identify_row(event.y)
        if item:
            self.lib_tree.selection_set(item)
            try:
                self.lib_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.lib_menu.grab_release()

    def _ctx_play(self):
        sel = self.lib_tree.selection()
        if sel:
            self._play_song(sel[0])

    def _on_lib_select(self, event=None):
        if hasattr(self, "lib_tree"):
            sel = self.lib_tree.selection()
            if sel:
                self.selected_song_path = sel[0]
                self._update_fav_btn()

    def _ctx_toggle_fav(self):
        sel = self.lib_tree.selection()
        if sel:
            self.selected_song_path = sel[0]
        self._toggle_like()

    def _ctx_add_to_playlist(self):
        sel = self.lib_tree.selection()
        if sel:
            self.selected_song_path = sel[0]
        self._add_selected_to_playlist()

    def _add_selected_to_playlist(self):
        target = self._get_target_song()
        if not target:
            messagebox.showinfo("No Song Selected",
                                "Please select a song from the library or start playback to add it to a playlist.")
            return
        self._show_add_to_playlist_dialog(target)

    def _show_add_to_playlist_dialog(self, song_path):
        song = self.lib.get_song(song_path)
        title = song.get("title", os.path.basename(song_path)) if song else os.path.basename(song_path)

        win = tk.Toplevel(self.root)
        win.title("Add to Playlist")
        win.geometry("340x430")
        win.minsize(300, 360)
        win.configure(bg=BG_DARK)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Add to Playlist",
                 font=("Segoe UI", 13, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(pady=(12, 2))
        tk.Label(win, text=f"Song: {title[:32]}",
                 font=("Segoe UI", 10),
                 bg=BG_DARK, fg=FG_SECONDARY).pack(pady=(0, 10))

        list_frame = tk.Frame(win, bg=BG_DARK)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        listbox = tk.Listbox(list_frame, bg=BG_CARD, fg=FG_PRIMARY,
                             selectbackground=ACCENT, font=("Segoe UI", 11),
                             border=0, highlightthickness=1,
                             highlightbackground="#333", selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def populate_pl():
            listbox.delete(0, tk.END)
            for n in self.playlists.get_names():
                count = len(self.playlists.get_songs(n))
                listbox.insert(tk.END, f"{n} ({count} songs)")

        populate_pl()
        if self.playlists.get_names():
            listbox.select_set(0)

        def do_add():
            idx = listbox.curselection()
            names = self.playlists.get_names()
            if not idx or idx[0] >= len(names):
                messagebox.showwarning("Select Playlist", "Please select a playlist from the list.", parent=win)
                return
            chosen_name = names[idx[0]]
            added = self.playlists.add_song(chosen_name, song_path)
            if added:
                messagebox.showinfo("Success", f"Added '{title}' to playlist '{chosen_name}'.", parent=win)
                win.destroy()
                if self.current_page == "playlists":
                    self._refresh_playlists()
                elif self.current_page == "playlist_detail" and getattr(self, "_current_playlist_view", None) == chosen_name:
                    self._view_playlist(chosen_name)
            else:
                messagebox.showinfo("Already in Playlist", f"'{title}' is already in playlist '{chosen_name}'.", parent=win)
                win.destroy()

        def do_new_playlist():
            name = simpledialog.askstring("New Playlist", "Enter playlist name:", parent=win)
            if name and name.strip():
                clean_name = name.strip()
                if not self.playlists.create(clean_name):
                    messagebox.showwarning("Exists", f"Playlist '{clean_name}' already exists.", parent=win)
                else:
                    populate_pl()
                    names = self.playlists.get_names()
                    if clean_name in names:
                        new_idx = names.index(clean_name)
                        listbox.selection_clear(0, tk.END)
                        listbox.selection_set(new_idx)
                        listbox.see(new_idx)
                    if self.current_page == "playlists":
                        self._refresh_playlists()

        listbox.bind("<Double-1>", lambda e: do_add())

        btn_box = tk.Frame(win, bg=BG_DARK)
        btn_box.pack(fill=tk.X, padx=16, pady=12)

        self._make_button(btn_box, "➕ Add to Selected", do_add).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        self._make_button(btn_box, "➕ New Playlist", do_new_playlist).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0))

    def _ctx_remove(self):
        sel = self.lib_tree.selection()
        if sel:
            for path in sel:
                self.lib.remove_song(path)
            self._populate_library()

    # ------------------------------------------------------------------
    # Playlists Page
    # ------------------------------------------------------------------

    def _show_playlists(self):
        self.current_page = "playlists"
        f = self._clear_main()

        header = tk.Frame(f, bg=BG_DARK)
        header.pack(fill=tk.X, pady=(0, 10))
        tk.Label(header, text="📋  Playlists",
                 font=("Segoe UI", 18, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(side=tk.LEFT)
        self._make_button(header, "➕ New Playlist", self._create_playlist).pack(side=tk.RIGHT)

        self.playlist_list_frame = tk.Frame(f, bg=BG_DARK)
        self.playlist_list_frame.pack(fill=tk.BOTH, expand=True)
        self._refresh_playlists()

    def _refresh_playlists(self):
        if not hasattr(self, "playlist_list_frame"):
            return
        for w in self.playlist_list_frame.winfo_children():
            w.destroy()

        names = self.playlists.get_names()
        if not names:
            tk.Label(self.playlist_list_frame,
                     text="No playlists yet. Click '➕ New Playlist' to create one.",
                     font=("Segoe UI", 11), bg=BG_DARK, fg=FG_DIM).pack(anchor="w", pady=20)
            return

        for name in names:
            songs = self.playlists.get_songs(name)
            row = tk.Frame(self.playlist_list_frame, bg=BG_CARD,
                           padx=12, pady=10,
                           highlightbackground="#333", highlightthickness=1)
            row.pack(fill=tk.X, pady=3)

            tk.Label(row, text=f"📋 {name}",
                     font=("Segoe UI", 12, "bold"),
                     bg=BG_CARD, fg=FG_PRIMARY).pack(side=tk.LEFT)
            tk.Label(row, text=f"  ({len(songs)} songs)",
                     font=("Segoe UI", 10),
                     bg=BG_CARD, fg=FG_DIM).pack(side=tk.LEFT, padx=5)

            btn_f = tk.Frame(row, bg=BG_CARD)
            btn_f.pack(side=tk.RIGHT)
            self._make_small_button(btn_f, "▶ Play",
                                     lambda n=name: self._play_playlist(n)).pack(side=tk.LEFT, padx=3)
            self._make_small_button(btn_f, "📝 View",
                                     lambda n=name: self._view_playlist(n)).pack(side=tk.LEFT, padx=3)
            self._make_small_button(btn_f, "🗑",
                                     lambda n=name: self._delete_playlist(n)).pack(side=tk.LEFT, padx=3)

            row.bind("<Enter>", lambda e, r=row: r.configure(bg=BG_HOVER))
            row.bind("<Leave>", lambda e, r=row: r.configure(bg=BG_CARD))

    def _create_playlist(self):
        name = simpledialog.askstring("New Playlist", "Playlist name:",
                                       parent=self.root)
        if name and name.strip():
            if not self.playlists.create(name.strip()):
                messagebox.showwarning("Exists", f"Playlist '{name}' already exists.")
            else:
                self._refresh_playlists()

    def _delete_playlist(self, name):
        if messagebox.askyesno("Delete Playlist",
                                f"Delete playlist '{name}'?"):
            self.playlists.delete(name)
            self._refresh_playlists()

    def _play_playlist(self, name):
        paths = self.playlists.get_songs(name)
        if not paths:
            messagebox.showinfo("Empty", "This playlist is empty.")
            return
        valid_paths = [p for p in paths if os.path.isfile(p)]
        if not valid_paths:
            messagebox.showwarning("Missing Files", "None of the songs in this playlist exist on disk.")
            return
        self.queue.set_queue(paths, start_path=valid_paths[0])
        self._play_song(valid_paths[0])

    def _play_song_from_playlist(self, playlist_name, filepath):
        if not os.path.isfile(filepath):
            messagebox.showwarning("File Missing", f"The file '{filepath}' could not be found.")
            return
        paths = self.playlists.get_songs(playlist_name)
        self.queue.set_queue(paths, start_path=filepath)
        self._play_song(filepath)

    def _view_playlist(self, name):
        """Open a sub-view showing songs in a playlist."""
        f = self._clear_main()
        self.current_page = "playlist_detail"
        self._current_playlist_view = name

        header = tk.Frame(f, bg=BG_DARK)
        header.pack(fill=tk.X, pady=(0, 10))
        self._make_button(header, "← Back", self._show_playlists).pack(side=tk.LEFT)
        tk.Label(header, text=f"📋  {name}",
                 font=("Segoe UI", 16, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(side=tk.LEFT, padx=10)
        self._make_button(header, "▶ Play All",
                           lambda: self._play_playlist(name)).pack(side=tk.RIGHT)

        songs = self.playlists.get_songs(name)
        if not songs:
            tk.Label(f, text="This playlist is empty.",
                     font=("Segoe UI", 11), bg=BG_DARK, fg=FG_DIM).pack(anchor="w", pady=20)
            return

        listbox_frame = tk.Frame(f, bg=BG_DARK)
        listbox_frame.pack(fill=tk.BOTH, expand=True)

        for i, path in enumerate(songs):
            song = self.lib.get_song(path)
            title = song["title"] if song else os.path.basename(path)
            artist = song.get("artist", "") if song else ""
            exists = os.path.isfile(path)

            row = tk.Frame(listbox_frame, bg=BG_CARD, padx=10, pady=6,
                           highlightbackground="#333", highlightthickness=1)
            row.pack(fill=tk.X, pady=2)

            display = f"{i+1}. {title}"
            if not exists:
                display += " ⚠️ (missing)"
            lbl_title = tk.Label(row, text=display,
                     font=("Segoe UI", 11),
                     bg=BG_CARD, fg=FG_PRIMARY if exists else DANGER)
            lbl_title.pack(side=tk.LEFT)
            lbl_artist = None
            if artist:
                lbl_artist = tk.Label(row, text=f"  —  {artist}",
                         font=("Segoe UI", 10),
                         bg=BG_CARD, fg=FG_DIM)
                lbl_artist.pack(side=tk.LEFT)

            btn_del = self._make_small_button(row, "🗑",
                                     lambda n=name, p=path: self._remove_from_playlist(n, p))
            btn_del.pack(side=tk.RIGHT, padx=2)

            if exists:
                btn_play = self._make_small_button(row, "▶",
                                         lambda p=path: self._play_song_from_playlist(name, p))
                btn_play.pack(side=tk.RIGHT, padx=4)

                row.bind("<Double-1>", lambda e, p=path: self._play_song_from_playlist(name, p))
                lbl_title.bind("<Double-1>", lambda e, p=path: self._play_song_from_playlist(name, p))
                if lbl_artist:
                    lbl_artist.bind("<Double-1>", lambda e, p=path: self._play_song_from_playlist(name, p))

            row.bind("<Enter>", lambda e, r=row: r.configure(bg=BG_HOVER))
            row.bind("<Leave>", lambda e, r=row: r.configure(bg=BG_CARD))

        self._current_playlist_view = name

    def _remove_from_playlist(self, name, path):
        self.playlists.remove_song(name, path)
        self._view_playlist(name)

    # ------------------------------------------------------------------
    # Favorites Page
    # ------------------------------------------------------------------

    def _show_favorites(self):
        self.current_page = "favorites"
        f = self._clear_main()

        tk.Label(f, text="❤️  Favorites",
                 font=("Segoe UI", 18, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(anchor="w", pady=(0, 10))

        favs = self.lib.get_favorites()
        if not favs:
            tk.Label(f, text="No favorites yet. Select a song and click '♡ Favorite' to add it.",
                     font=("Segoe UI", 11), bg=BG_DARK, fg=FG_DIM).pack(anchor="w", pady=20)
            return

        for i, song in enumerate(favs):
            row = tk.Frame(f, bg=BG_CARD, padx=10, pady=8,
                           highlightbackground="#333", highlightthickness=1)
            row.pack(fill=tk.X, pady=2)
            exists = os.path.isfile(song["path"])
            title = song.get("title", "Unknown")
            if not exists:
                title += " ⚠️"
            lbl_title = tk.Label(row, text=f"❤️  {title}",
                     font=("Segoe UI", 11),
                     bg=BG_CARD, fg=FG_PRIMARY if exists else DANGER)
            lbl_title.pack(side=tk.LEFT)
            lbl_artist = None
            if song.get("artist"):
                lbl_artist = tk.Label(row, text=f"  —  {song.get('artist', '')}",
                         font=("Segoe UI", 10),
                         bg=BG_CARD, fg=FG_DIM)
                lbl_artist.pack(side=tk.LEFT)
            tk.Label(row, text=song.get("duration_str", ""),
                     font=("Segoe UI", 10),
                     bg=BG_CARD, fg=FG_DIM).pack(side=tk.RIGHT, padx=10)
            self._make_small_button(row, "💔",
                                     lambda p=song["path"]: self._unfav(p)).pack(side=tk.RIGHT)
            if exists:
                self._make_small_button(row, "▶",
                                         lambda p=song["path"]: self._play_song(p)).pack(side=tk.RIGHT, padx=4)
                row.bind("<Double-1>", lambda e, p=song["path"]: self._play_song(p))
                lbl_title.bind("<Double-1>", lambda e, p=song["path"]: self._play_song(p))
                if lbl_artist:
                    lbl_artist.bind("<Double-1>", lambda e, p=song["path"]: self._play_song(p))
            row.bind("<Enter>", lambda e, r=row: r.configure(bg=BG_HOVER))
            row.bind("<Leave>", lambda e, r=row: r.configure(bg=BG_CARD))

    def _unfav(self, path):
        self.lib.toggle_favorite(path)
        self._update_fav_btn()
        self._show_favorites()

    # ------------------------------------------------------------------
    # Recently Played Page
    # ------------------------------------------------------------------

    def _show_recent(self):
        self.current_page = "recent"
        f = self._clear_main()

        tk.Label(f, text="🕐  Recently Played",
                 font=("Segoe UI", 18, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(anchor="w", pady=(0, 10))

        recent = self.lib.get_recent_songs(limit=30)
        if not recent:
            tk.Label(f, text="No songs played yet.",
                     font=("Segoe UI", 11), bg=BG_DARK, fg=FG_DIM).pack(anchor="w", pady=20)
            return

        for song in recent:
            row = tk.Frame(f, bg=BG_CARD, padx=10, pady=8,
                           highlightbackground="#333", highlightthickness=1)
            row.pack(fill=tk.X, pady=2)
            exists = os.path.isfile(song["path"])
            title = song.get("title", "Unknown")
            if not exists:
                title += " ⚠️"
            tk.Label(row, text=f"🎵  {title}",
                     font=("Segoe UI", 11),
                     bg=BG_CARD, fg=FG_PRIMARY if exists else DANGER).pack(side=tk.LEFT)
            tk.Label(row, text=f"  —  {song.get('artist', '')}",
                     font=("Segoe UI", 10),
                     bg=BG_CARD, fg=FG_DIM).pack(side=tk.LEFT)
            tk.Label(row, text=song.get("duration_str", ""),
                     font=("Segoe UI", 10),
                     bg=BG_CARD, fg=FG_DIM).pack(side=tk.RIGHT, padx=10)
            if exists:
                row.bind("<Double-1>", lambda e, p=song["path"]: self._play_song(p))
            row.bind("<Enter>", lambda e, r=row: r.configure(bg=BG_HOVER))
            row.bind("<Leave>", lambda e, r=row: r.configure(bg=BG_CARD))

    # ------------------------------------------------------------------
    # Settings Page
    # ------------------------------------------------------------------

    def _show_settings(self):
        self.current_page = "settings"
        f = self._clear_main()

        tk.Label(f, text="⚙️  Settings",
                 font=("Segoe UI", 18, "bold"),
                 bg=BG_DARK, fg=FG_PRIMARY).pack(anchor="w", pady=(0, 20))

        # Library stats
        info_frame = tk.Frame(f, bg=BG_CARD, padx=15, pady=15,
                              highlightbackground="#333", highlightthickness=1)
        info_frame.pack(fill=tk.X, pady=5)
        tk.Label(info_frame, text="Library Statistics",
                 font=("Segoe UI", 13, "bold"),
                 bg=BG_CARD, fg=FG_PRIMARY).pack(anchor="w")
        tk.Label(info_frame, text=f"Songs: {len(self.lib.songs)}",
                 font=("Segoe UI", 11),
                 bg=BG_CARD, fg=FG_SECONDARY).pack(anchor="w", pady=2)
        tk.Label(info_frame, text=f"Favorites: {len(self.lib.favorites)}",
                 font=("Segoe UI", 11),
                 bg=BG_CARD, fg=FG_SECONDARY).pack(anchor="w", pady=2)
        tk.Label(info_frame, text=f"Playlists: {len(self.playlists.playlists)}",
                 font=("Segoe UI", 11),
                 bg=BG_CARD, fg=FG_SECONDARY).pack(anchor="w", pady=2)

        # Check missing
        missing = self.lib.check_missing()
        if missing:
            miss_frame = tk.Frame(f, bg=BG_CARD, padx=15, pady=15,
                                  highlightbackground=DANGER, highlightthickness=1)
            miss_frame.pack(fill=tk.X, pady=10)
            tk.Label(miss_frame,
                     text=f"⚠️  {len(missing)} file(s) are missing from disk.",
                     font=("Segoe UI", 11),
                     bg=BG_CARD, fg=DANGER).pack(anchor="w")
            self._make_button(miss_frame, "Remove Missing Files",
                               self._remove_missing).pack(anchor="w", pady=5)

        # About
        about_frame = tk.Frame(f, bg=BG_CARD, padx=15, pady=15,
                               highlightbackground="#333", highlightthickness=1)
        about_frame.pack(fill=tk.X, pady=10)
        tk.Label(about_frame, text="About",
                 font=("Segoe UI", 13, "bold"),
                 bg=BG_CARD, fg=FG_PRIMARY).pack(anchor="w")
        tk.Label(about_frame,
                 text="Custom Media Player v1.0\nBuilt with Python + Tkinter + Pygame-CE",
                 font=("Segoe UI", 11),
                 bg=BG_CARD, fg=FG_SECONDARY, justify="left").pack(anchor="w", pady=5)

    def _remove_missing(self):
        missing = self.lib.check_missing()
        for p in missing:
            self.lib.remove_song(p)
        messagebox.showinfo("Done", f"Removed {len(missing)} missing file(s).")
        self._show_settings()

    # ==================================================================
    # Bottom Control Bar
    # ==================================================================

    def _build_control_bar(self):
        bar = tk.Frame(self.root, bg=BG_CONTROL, height=110)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)

        # ---- Row 1: Song info + Progress ----
        row1 = tk.Frame(bar, bg=BG_CONTROL)
        row1.pack(fill=tk.X, padx=15, pady=(8, 0))

        # Left: song info & favorite button
        info = tk.Frame(row1, bg=BG_CONTROL)
        info.pack(side=tk.LEFT, fill=tk.X)

        self.btn_fav = tk.Label(info, text="♡",
                                font=("Segoe UI", 14),
                                bg=BG_CONTROL, fg=FG_DIM,
                                cursor="hand2")
        self.btn_fav.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_fav.bind("<Button-1>", lambda e: self._toggle_like())

        text_info = tk.Frame(info, bg=BG_CONTROL)
        text_info.pack(side=tk.LEFT, fill=tk.X)
        self.lbl_title = tk.Label(text_info, text="No song playing",
                                   font=("Segoe UI", 11, "bold"),
                                   bg=BG_CONTROL, fg=FG_PRIMARY, anchor="w")
        self.lbl_title.pack(anchor="w")
        self.lbl_artist = tk.Label(text_info, text="",
                                    font=("Segoe UI", 9),
                                    bg=BG_CONTROL, fg=FG_DIM, anchor="w")
        self.lbl_artist.pack(anchor="w")

        # Right: time display
        time_frame = tk.Frame(row1, bg=BG_CONTROL)
        time_frame.pack(side=tk.RIGHT)
        self.lbl_time = tk.Label(time_frame, text="0:00",
                                  font=("Segoe UI", 9),
                                  bg=BG_CONTROL, fg=FG_DIM)
        self.lbl_time.pack(side=tk.LEFT)
        tk.Label(time_frame, text=" / ", bg=BG_CONTROL, fg=FG_DIM,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.lbl_total = tk.Label(time_frame, text="0:00",
                                   font=("Segoe UI", 9),
                                   bg=BG_CONTROL, fg=FG_DIM)
        self.lbl_total.pack(side=tk.LEFT)

        # ---- Progress bar ----
        self.seek_var = tk.DoubleVar(value=0)
        self.seek_bar = ttk.Scale(bar, from_=0, to=100,
                                   orient=tk.HORIZONTAL,
                                   variable=self.seek_var,
                                   style="Horizontal.TScale",
                                   command=self._on_seek_move)
        self.seek_bar.pack(fill=tk.X, padx=15, pady=(4, 2))
        self.seek_bar.bind("<ButtonPress-1>", self._seek_start)
        self.seek_bar.bind("<B1-Motion>", self._seek_drag)
        self.seek_bar.bind("<ButtonRelease-1>", self._seek_end)

        # ---- Row 2: Controls ----
        row2 = tk.Frame(bar, bg=BG_CONTROL)
        row2.pack(fill=tk.X, padx=15, pady=(2, 8))

        # Center: playback buttons
        ctrl = tk.Frame(row2, bg=BG_CONTROL)
        ctrl.pack(side=tk.LEFT, expand=True)

        self.btn_shuffle = self._ctrl_btn(ctrl, "🔀", self._toggle_shuffle)
        self.btn_prev    = self._ctrl_btn(ctrl, "⏮", self._prev)
        self.btn_play    = self._ctrl_btn(ctrl, "▶", self._toggle_play, size=16)
        self.btn_next    = self._ctrl_btn(ctrl, "⏭", self._next)
        self.btn_stop    = self._ctrl_btn(ctrl, "⏹", self._stop)
        self.btn_repeat  = self._ctrl_btn(ctrl, "🔁", self._toggle_repeat)

        # Right: volume
        vol_frame = tk.Frame(row2, bg=BG_CONTROL)
        vol_frame.pack(side=tk.RIGHT)

        self.btn_mute = tk.Label(vol_frame, text="🔊",
                                  font=("Segoe UI", 13),
                                  bg=BG_CONTROL, fg=FG_SECONDARY,
                                  cursor="hand2")
        self.btn_mute.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_mute.bind("<Button-1>", lambda e: self._toggle_mute())

        self.vol_var = tk.DoubleVar(value=self.audio.volume * 100)
        self.vol_slider = ttk.Scale(vol_frame, from_=0, to=100,
                                     orient=tk.HORIZONTAL,
                                     variable=self.vol_var,
                                     style="Volume.Horizontal.TScale",
                                     length=120,
                                     command=self._on_volume_change)
        self.vol_slider.pack(side=tk.LEFT)

        # Update button states to match loaded settings
        self._update_shuffle_btn()
        self._update_repeat_btn()
        self._update_fav_btn()

    def _ctrl_btn(self, parent, text, command, size=13):
        """Create a control-bar button."""
        btn = tk.Label(parent, text=text,
                       font=("Segoe UI", size),
                       bg=BG_CONTROL, fg=FG_SECONDARY,
                       padx=10, cursor="hand2")
        btn.pack(side=tk.LEFT)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(fg=FG_PRIMARY))
        btn.bind("<Leave>", lambda e: btn.configure(
            fg=ACCENT if btn in (self.btn_shuffle, self.btn_repeat) and
            self._is_accent(btn) else FG_SECONDARY))
        return btn

    def _is_accent(self, btn):
        return btn.cget("fg") == ACCENT

    # ==================================================================
    # Favorite Helpers
    # ==================================================================

    def _get_target_song(self):
        """Return the path of the currently selected or playing song."""
        if getattr(self, "selected_song_path", None):
            return self.selected_song_path
        if self.audio.current_file:
            return self.audio.current_file
        return self.queue.current()

    def _update_fav_btn(self):
        """Update the visual state of the favorite/like buttons."""
        target = self._get_target_song()
        is_fav = bool(target and self.lib.is_favorite(target))
        if hasattr(self, "btn_fav"):
            self.btn_fav.config(text="❤️" if is_fav else "♡",
                                fg="#e74c3c" if is_fav else FG_DIM)
        if hasattr(self, "btn_lib_fav") and self.btn_lib_fav.winfo_exists():
            self.btn_lib_fav.config(text="❤️ Favorited" if is_fav else "♡ Favorite",
                                    bg="#e74c3c" if is_fav else ACCENT)

    def _toggle_like(self):
        """Toggle favorite status for the currently selected/playing song."""
        target = self._get_target_song()
        if not target:
            messagebox.showinfo("No Song Selected",
                                "Please select or play a song first to add it to Favorites.")
            return
        is_fav = self.lib.toggle_favorite(target)
        self._update_fav_btn()
        if self.current_page == "favorites":
            self._show_favorites()
        elif self.current_page == "library":
            self._populate_library()

    # ==================================================================
    # Keyboard Shortcuts
    # ==================================================================

    def _on_space_key(self, event):
        """Handle spacebar shortcut for play/pause without affecting text entries."""
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox, ttk.Spinbox)):
            return None
        self._toggle_play()
        return "break"

    # ==================================================================
    # Playback Actions
    # ==================================================================

    def _play_song(self, filepath):
        """Start playing a specific song."""
        if not os.path.isfile(filepath):
            messagebox.showerror("File Missing",
                                 f"Cannot play: file not found.\n{filepath}")
            return
        try:
            self.audio.play(filepath)
        except Exception as e:
            messagebox.showerror("Playback Error",
                                 f"Could not play this file.\n{e}")
            return

        self.selected_song_path = filepath
        self._update_fav_btn()

        # Update queue if song isn't the current queue track
        if self.queue.current() != filepath:
            all_paths = [s["path"] for s in self.lib.songs]
            if filepath in all_paths:
                self.queue.set_queue(all_paths, start_path=filepath)

        # Update UI
        song = self.lib.get_song(filepath)
        if song:
            self.lbl_title.config(text=song.get("title", "Unknown"))
            self.lbl_artist.config(text=song.get("artist", ""))
            self.lbl_total.config(text=song.get("duration_str", "0:00"))
        else:
            self.lbl_title.config(text=os.path.basename(filepath))
            self.lbl_artist.config(text="")
            self.lbl_total.config(text=_format_time(self.audio.duration))

        self.btn_play.config(text="⏸")
        self.lib.add_recent(filepath)

    def _toggle_play(self):
        """Play/Pause toggle."""
        if not self.audio.is_playing and not self.audio.is_paused:
            if self.audio.current_file and os.path.isfile(self.audio.current_file):
                self._play_song(self.audio.current_file)
                return
            current = self.queue.current()
            if current:
                self._play_song(current)
                return
            if getattr(self, "selected_song_path", None) and os.path.isfile(self.selected_song_path):
                self._play_song(self.selected_song_path)
                return
            if self.lib.songs:
                first = self.lib.songs[0]["path"]
                all_paths = [s["path"] for s in self.lib.songs]
                self.queue.set_queue(all_paths, start_path=first)
                self._play_song(first)
                return
            return

        is_paused = self.audio.toggle_pause()
        self.btn_play.config(text="▶" if is_paused else "⏸")

    def _stop(self):
        self.audio.stop()
        self.btn_play.config(text="▶")
        self.seek_var.set(0)
        self.lbl_time.config(text="0:00")

    def _next(self):
        nxt = self.queue.next()
        if nxt:
            self._play_song(nxt)

    def _prev(self):
        prv = self.queue.previous()
        if prv:
            self._play_song(prv)

    def _toggle_shuffle(self):
        self.queue.toggle_shuffle()
        self._update_shuffle_btn()

    def _update_shuffle_btn(self):
        if self.queue.shuffle:
            self.btn_shuffle.config(fg=ACCENT)
        else:
            self.btn_shuffle.config(fg=FG_SECONDARY)

    def _toggle_repeat(self):
        self.queue.cycle_repeat()
        self._update_repeat_btn()

    def _update_repeat_btn(self):
        if self.queue.repeat == REPEAT_OFF:
            self.btn_repeat.config(text="🔁", fg=FG_SECONDARY)
        elif self.queue.repeat == REPEAT_ALL:
            self.btn_repeat.config(text="🔁", fg=ACCENT)
        else:  # REPEAT_ONE
            self.btn_repeat.config(text="🔂", fg=ACCENT)

    def _toggle_mute(self):
        muted = self.audio.toggle_mute()
        self.btn_mute.config(text="🔇" if muted else "🔊")

    def _on_volume_change(self, value):
        v = float(value) / 100.0
        self.audio.set_volume(v)
        if self.audio.muted:
            self.audio.muted = False
            self.btn_mute.config(text="🔊")

    # --- Seek ---

    def _seek_start(self, event=None):
        self._seeking = True
        if event and self.seek_bar.winfo_width() > 0:
            pct = max(0.0, min(100.0, (event.x / self.seek_bar.winfo_width()) * 100.0))
            self.seek_var.set(pct)
            if self.audio.duration > 0:
                secs = (pct / 100.0) * self.audio.duration
                self.lbl_time.config(text=_format_time(secs))

    def _seek_drag(self, event=None):
        if self._seeking and event and self.seek_bar.winfo_width() > 0:
            pct = max(0.0, min(100.0, (event.x / self.seek_bar.winfo_width()) * 100.0))
            self.seek_var.set(pct)
            if self.audio.duration > 0:
                secs = (pct / 100.0) * self.audio.duration
                self.lbl_time.config(text=_format_time(secs))

    def _seek_end(self, event=None):
        if event and self.seek_bar.winfo_width() > 0:
            pct = max(0.0, min(100.0, (event.x / self.seek_bar.winfo_width()) * 100.0))
            self.seek_var.set(pct)
        self._seeking = False
        if self.audio.duration > 0:
            pct = self.seek_var.get()
            target = (pct / 100.0) * self.audio.duration
            self.audio.seek(target)
            self.lbl_time.config(text=_format_time(target))

    def _on_seek_move(self, value):
        if self._seeking and self.audio.duration > 0:
            pct = float(value)
            secs = (pct / 100.0) * self.audio.duration
            self.lbl_time.config(text=_format_time(secs))

    # ==================================================================
    # Periodic Update (tick every 200 ms)
    # ==================================================================

    def _tick(self):
        if self.audio.is_playing and not self.audio.is_paused:
            # Check if song ended
            if self.audio.check_end_event():
                nxt = self.queue.next()
                if nxt:
                    self._play_song(nxt)
                else:
                    self._stop()
            else:
                # Update progress
                pos = self.audio.get_position()
                if not self._seeking:
                    if self.audio.duration > 0:
                        pct = (pos / self.audio.duration) * 100.0
                        self.seek_var.set(min(pct, 100.0))
                    self.lbl_time.config(text=_format_time(pos))

        self.root.after(200, self._tick)

    # ==================================================================
    # Helpers
    # ==================================================================

    def _make_button(self, parent, text, command):
        """Create a styled button."""
        btn = tk.Label(parent, text=text,
                       font=("Segoe UI", 10),
                       bg=ACCENT, fg=FG_PRIMARY,
                       padx=12, pady=5, cursor="hand2")
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=ACCENT_HOVER))
        btn.bind("<Leave>", lambda e: btn.configure(bg=ACCENT))
        return btn

    def _make_small_button(self, parent, text, command):
        """Create a small secondary button."""
        btn = tk.Label(parent, text=text,
                       font=("Segoe UI", 9),
                       bg=BG_CARD, fg=FG_SECONDARY,
                       padx=6, pady=2, cursor="hand2")
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(fg=FG_PRIMARY))
        btn.bind("<Leave>", lambda e: btn.configure(fg=FG_SECONDARY))
        return btn

    def _on_close(self):
        """Save state and exit."""
        settings = {
            "volume": self.audio.volume,
            "shuffle": self.queue.shuffle,
            "repeat": self.queue.repeat,
        }
        storage.save_settings(settings)
        self.lib.save()
        self.audio.cleanup()
        self.root.destroy()

    # ==================================================================
    # Run
    # ==================================================================

    def run(self):
        """Start the Tkinter main loop."""
        self.root.mainloop()
