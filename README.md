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

Restart Rocket League after editing this file.

## Installation

### Windows installer (recommended)

1. Download **`RLLiveTracker-Setup-x.y.z.exe`** from [GitHub Releases](https://github.com/Minitsonga/rl-live-tracker/releases) (available from **v1.0.0** onward; beta tags ship source ZIP only).
2. Run the installer (per-user, no admin required). Optional: desktop shortcut, launch after install, **Start with Windows** (off by default).
3. Config and logs live under `%LocalAppData%\RLLiveTracker\` (`data\`, `logs\`).

**SmartScreen / antivirus:** unsigned PyInstaller builds may show “unknown publisher” or a false positive. Use **More info → Run anyway** if you trust the release, or run from source below.

### From source (developers)

```powershell
cd rl-live-tracker
python -m pip install -r requirements.txt
```

### Build the installer locally

Requires [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```powershell
.\packaging\build.ps1
```

Output: `dist\RLLiveTracker\` (portable folder) and `dist\RLLiveTracker-Setup-*.exe`.

## Dev quality checks

```powershell
python -m pip install pre-commit pytest ruff
pre-commit install
pre-commit run --all-files
$env:PYTHONPATH = "$PWD\src"; pytest -q
```

CI runs the same checks on `dev`, `staging`, and `main` pushes and on PRs targeting `staging`/`main`.
Pushing a version tag (example: `v1.0.0`) runs the Release workflow: GitHub release notes, source archive, and Windows **Setup.exe** when the Windows build job succeeds.

Pre-release example: `v1.0-beta.2` (sources only, no installer).

## Run

```powershell
$env:PYTHONPATH = "$PWD\src"; python -m rl_live_tracker
```

Or double-click `start.bat`.

A tray icon appears near the clock (display shortcuts, network MMR, data folder, **About**, **Check for updates**, etc.).

When Rocket League is **not** running, the app stays in **idle** mode (no Stats API TCP retries, slower timers) to reduce CPU and network use. Launch the tracker when you play, or enable **Start with Windows** in F5 if you want it in the tray before RL starts.

## Settings (F5)

Press **F5** to open/close the centered settings panel (mouse-friendly):

- **Display**: session card (W/L), lobby roster, and in-game MMR visibility in overlays.
- **Position - session / roster**: four screen corners (**◤ TL**, **◥ TR**, **◣ BL**, **◢ BR**) or **Custom** (manual coordinates).
- **Drag to reposition...**: enables moving both overlays with the mouse; click **Finish dragging** to save the position. Both anchors switch to **Custom** and are saved into `data/config.json`.

**Esc** or **F5** closes the panel. If dragging is active, positions are saved on close.

By default, only one global hotkey is enabled: `menu_toggle_hotkeys` -> `["f5"]`. The lists `toggle_hotkeys`, `roster_toggle_hotkeys`, `mmr_tracker_toggle_hotkeys`, and `mmr_ingame_toggle_hotkeys` are empty, so you can add extra shortcuts if needed (avoid collisions with **F5**).

## Configuration

`data/config.json` is created on first run. Key fields:

- `self_player_id`: auto-filled after a **1v1** match; otherwise set your local player key manually as `Platform|Uid`.
- `position_session_anchor` / `position_roster_anchor`: `top-left`, `top-right`, `bottom-left`, `bottom-right`, or `custom` with `position_*_custom_xy` `[x, y]`.
- `show_session_overlay`, `show_roster_overlay`, `show_mmr_ingame`: persisted state for F5 panel toggles.
- `roster_visible_default`: only used to migrate legacy configs into `show_roster_overlay`.
- `idle_when_rl_closed`: pause Stats API when `RocketLeague.exe` is absent (default `true`).
- `check_updates_on_startup`: optional GitHub Releases check (default `true`, non-blocking).
- `launch_at_windows_startup`: HKCU Run entry (default `false`).

## First-time config template

This repository includes `config.example.json`. Copy it to `data/config.json` before first run if you want to preconfigure values.

## Local runtime data

- `data/mmr_cache.json` - MMR cache
- `logs/mmr.log`, `logs/api_dump.log` - log files (also visible on stderr)
