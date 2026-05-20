"""Point d'entrée PyInstaller (imports absolus — pas de package parent)."""
from rl_live_tracker.app import run

if __name__ == "__main__":
    raise SystemExit(run())
