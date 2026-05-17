# RL Live Tracker

Windows overlay for Rocket League: session stats (W/L, streak, tracker.gg MMR without API key) and team-by-team lobby ranks.

## Credits

The architecture (Stats API TCP client, NDJSON parsing, tracker.network disk cache via `curl_cffi`, logs) is heavily inspired by [**rl-h2h**](https://github.com/Florentde29/rl-h2h) (Florentde29 / rl-h2h). This repository is a separate implementation focused on a persistent overlay plus a second roster window.

## Requirements

- Windows
- Python 3.11+
- Rocket League in **Borderless**
- `DefaultStatsAPI.ini` in your Rocket League install folder, for example:

```ini
[StatsAPI]
PacketSendRate=2
Port=49123
```

Restart Rocket League after editing this file. The tracker connects to `127.0.0.1` on that port only. It does **not** modify game files — only `data/` (config, MMR cache, match log) and `logs/`. **Help → Stats API setup** shows the default relative path `TAGame/Config/DefaultStatsAPI.ini` and a short setup guide.

## Repository layout

```
rl-live-tracker/
  .github/workflows/   # CI and release (Windows installer on version tags)
  docs/dev/            # overlay HTML design references (not shipped)
  packaging/           # PyInstaller spec, Inno Setup, build.ps1, prune_bundle.ps1
  src/rl_live_tracker/ # application code
  tests/
  config.example.json  # optional template for data/config.json
  pyproject.toml       # dependencies and version (single source of truth)
  start.bat            # quick dev launch
```

Generated locally (gitignored): `build/`, `dist/`, `*.egg-info/`, `.venv/`.

## Installation

### Windows installer (recommended)

1. Download **`RL-LiveTracker-Setup.exe`** from [GitHub Releases](https://github.com/Minitsonga/rl-live-tracker/releases) (from **v1.0.0** onward; beta tags ship source ZIP only).
2. Run the installer (per-user, no admin required). Choose or create a folder under `%LocalAppData%` (default: `%LocalAppData%\RLLiveTracker\`).
3. Optional: desktop shortcut, launch after install, **Start with Windows** (off by default).
4. Config and logs live under `%LocalAppData%\RLLiveTracker\` (`data\`, `logs\`) — separate from the program folder.

**SmartScreen / antivirus:** unsigned PyInstaller builds may show “unknown publisher” or a false positive. Use **More info → Run anyway** if you trust the release, or run from source below.

### From source (developers)

```powershell
cd rl-live-tracker
python -m pip install -e ".[dev]"
```

### Build the installer locally

Requires [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```powershell
.\packaging\build.ps1
```

Output:

- `dist\RLLiveTracker\` — portable folder (`RLLiveTracker.exe` + `runtime\`)
- `dist\RL-LiveTracker-Setup.exe` — installer (target installed size ≤ ~50 MB after prune; see size note below)

Size report: `build\size-report.txt` (gitignored).

## Dev quality checks

```powershell
pip install -e ".[dev]"
pre-commit install
pre-commit run --all-files
$env:PYTHONPATH = "$PWD\src"; pytest -q
```

CI runs the same checks on `dev`, `staging`, and `main` pushes and on PRs targeting `staging`/`main`.
Pushing a version tag (example: `v1.0.0`) runs the Release workflow: GitHub release notes, source archive, and Windows **RL-LiveTracker-Setup.exe** when the Windows build job succeeds.

Pre-release example: `v1.0-beta.2` (sources only, no installer).

## Run

```powershell
$env:PYTHONPATH = "$PWD\src"; python -m rl_live_tracker
```

Or double-click `start.bat`.

On start, the **app window** opens unless **Start minimized to tray** is enabled in **Settings**. The app always lives in the system tray while running.

When the **Stats API** is not connected (`idle_when_rl_closed`, default on), overlays stay hidden and timers slow down; the app keeps light TCP retries until RL exports stats. Launch the tracker when you play, or enable **Run on startup** under **Settings**.

### Installed size vs BakkesMod

The Windows build bundles **Python 3.12 + Qt (PySide6)** (~40–50 MB installed after pruning). Tools like BakkesMod (~20 MB) are native C++ plugins without a Python/Qt runtime. A similar footprint would require a different technology stack, not just smaller packaging.

## App window, overlay settings, and tray

| Action | Behavior |
|--------|----------|
| **Tray → Open** / double-click tray | Show app window (status + menus) |
| **Tray → Check for updates** | Windows Yes/No dialog if an update exists |
| **Tray → Quit** | Exit completely |
| **F5** | Toggle **overlay settings** panel (in-game layout; not the app window) |
| **Minimize app window** | First time: choose **Quit**, **Hide to tray**, or **Cancel**; then tray or quit per your choice / Settings |
| **Close app window (X)** | Default: **quit** the application. Enable **Close to system tray** in Settings (or pick **Hide to tray** on first close) to keep running |
| **File → Exit** / **Tray → Quit** | Exit completely |

Overlay settings (visibility, themes, screen corners, drag mode) are separate from the app window — dark panel opened with **F5**.

- **Display**: session card (W/L), lobby roster, in-game MMR in overlays.
- **Position**: four corners or **Custom**; **Drag overlays** saves custom coordinates to `data/config.json`.
- **Esc** or **F5** closes the overlay settings panel (does not quit the app).

**Session stats (W/L, MMR cumulative on the session card):** only matches that end with an official **MatchEnded** event are counted. Lobbies cancelled before the game starts (e.g. a player failed to connect, **MatchDestroyed** without **MatchEnded**) are ignored. When you **close Rocket League**, the overlay session (W/L, streaks, session MMR total) is reset for the next play session.

Overlays still respect `require_rl_focus` when RL is not in the foreground (overlay settings panel can stay open).

## Configuration

`data/config.json` is created on first run. Key fields:

- `self_player_id`: auto-filled after a **1v1** match; otherwise set your local player key manually as `Platform|Uid`.
- `position_session_anchor` / `position_roster_anchor`: `top-left`, `top-right`, `bottom-left`, `bottom-right`, or `custom` with `position_*_custom_xy` `[x, y]`.
- `show_session_overlay`, `show_roster_overlay`, `show_mmr_ingame`: persisted overlay visibility.
- `idle_when_rl_closed`: idle UI until Stats API TCP connects (default `true`); session resets on disconnect.
- `check_updates_on_startup`: optional GitHub Releases check (default `true`; also in **Settings**).
- `launch_at_windows_startup`: HKCU Run entry (default `false`; **Settings → Run on startup**).
- `close_to_tray`: when `true`, the window **X** hides to the tray instead of quitting (default `false`).
- `start_minimized_to_tray`: start without showing the app window (default `false`).
- `tray_minimize_prompt_done` / `tray_close_prompt_done`: first-run tray dialogs (managed automatically).

## First-time config template

Copy `config.example.json` to `data/config.json` before first run if you want to preconfigure values.

## Local runtime data

- `data/mmr_cache.json` - MMR cache
- `logs/mmr.log`, `logs/api_dump.log` - log files (also visible on stderr)
