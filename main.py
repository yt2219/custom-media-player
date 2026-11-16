"""
main.py - Entry point for the Custom Media Player application.

Checks dependencies, then launches the Tkinter-based media player.
"""

import sys
import os


def check_dependencies():
    """Verify that required packages are installed."""
    missing = []

    try:
        import pygame
    except ImportError:
        missing.append("pygame")

    try:
        import mutagen
    except ImportError:
        missing.append("mutagen")

    if missing:
        print("=" * 50)
        print("  Missing required packages:")
        for pkg in missing:
            print(f"    - {pkg}")
        print()
        print("  Install them with:")
        print(f"    pip install {' '.join(missing)}")
        print("=" * 50)
        sys.exit(1)


def main():
    """Initialize and run the media player."""
    check_dependencies()

    # Add the project directory to the path so modules can find each other
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    from ui import MediaPlayerApp

    app = MediaPlayerApp()
    app.run()


if __name__ == "__main__":
    main()
