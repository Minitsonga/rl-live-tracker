# RL Live Tracker v1.0.0

First stable Windows release: in-game overlays for session tracking (W/L, streak, tracker.gg MMR) and lobby ranks—no API key required.

---

## Download

- **Installer (recommended)**: `RL-LiveTracker-Setup.exe` (GitHub release assets)
- **User data**: `%LocalAppData%\RLLiveTracker\` (`data\`, `logs\`) — separate from the install folder

> Unsigned build: Windows may show “unknown publisher”. Use **More info → Run anyway** if you trust the release, or run from source (see [README](../README.md)).

---

## Main features

### In-game overlays (F5)

- **Session** card: wins / losses, streak, session cumulative MMR delta
- **Lobby roster**: per-player MMR (tracker.gg cache via `curl_cffi`)
- Multiple **themes** (minimal, broadcast, console, etc.), screen corners or **custom** position, **drag** mode
- Overlays hidden when Rocket League is not in the foreground (`require_rl_focus`, configurable)

### Windows app

- Hub window + **system tray**: status, menus, Stats API help
- **Idle mode** until the Stats API is connected (overlays hidden, slower timers)
- Optional **update check** on startup (GitHub Releases)
- **Run at Windows startup**, minimize to tray, close to tray (settings)

### Automatic W/L (Stats API)

- **Win**: only when `MatchEnded` reports your team as winner
- **Loss**: match ends without `MatchEnded` (forfeit, quit during replay, crash, early lobby close)
- Session reset when Rocket League disconnects

### MMR

- tracker.gg lookup without an API key, local cache
- Post-match polling to apply TRN delta on the session card

---

## Rocket League setup

Create or edit `TAGame/Config/DefaultStatsAPI.ini` in your game folder, for example:

```ini
[StatsAPI]
PacketSendRate=2
Port=49123
```

Restart Rocket League. The app does **not** modify game files—only `data/` and `logs/`. See **Help → Stats API setup** in the app.

**Requirements**: Windows, Rocket League in **borderless** mode, Python 3.11+ if running from source.

---

## What’s new in this release (vs betas)

- **Inno Setup** installer and optimized PyInstaller build (~50 MB installed)
- Dedicated app window (injector-style), tray, minimize/close preferences
- Official icon (exe, tray, multi-resolution taskbar)
- Readable dark theme (hub, Help, About)
- Status text: **Waiting for Rocket League** / **Rocket League is running**
- Simplified W/L rules (forfeit / quit → loss; guard against late false wins)
- Stats API help without touching game files (relative path + copyable example)

---

## Shortcuts

| Action | Result |
|--------|--------|
| **F5** | Overlay settings panel |
| **Tray** (double-click) | Open app window |
| **Tray → Quit** | Exit completely |

---

## Known limitations

- Larger install size than native plugins (bundled Python + Qt)
- A cancelled lobby after `MatchInitialized` may count as a **loss** (intentional to handle forfeit / quit)
- W/L and MMR depend on the Stats API and TRN cache (possible delay after a match)

---

## Credits

Architecture inspired by [rl-h2h](https://github.com/Florentde29/rl-h2h)—separate implementation focused on persistent overlays and a roster window.

---

**Repository**: https://github.com/Minitsonga/rl-live-tracker
