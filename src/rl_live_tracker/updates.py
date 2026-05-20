"""Vérification des releases GitHub (issue #6)."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from . import __version__

GITHUB_REPO = "Minitsonga/rl-live-tracker"
_USER_AGENT = "RLLiveTracker"


@dataclass(frozen=True)
class ReleaseInfo:
    tag_name: str
    html_url: str
    name: str
    body: str

    @property
    def version(self) -> str:
        return _strip_v(self.tag_name)


def _strip_v(tag: str) -> str:
    s = str(tag or "").strip()
    if s.lower().startswith("v"):
        return s[1:]
    return s


def _parse_version_tuple(version: str) -> tuple[int, ...]:
    main = _strip_v(version).split("-", 1)[0]
    parts: list[int] = []
    for piece in main.split("."):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    return tuple(parts) if parts else (0,)


def _prerelease_key(version: str) -> tuple[int, str]:
    s = _strip_v(version)
    if "-" not in s:
        return (1, "")
    pre = s.split("-", 1)[1].lower()
    m = re.match(r"^beta\.(\d+)$", pre)
    if m:
        return (0, f"beta.{int(m.group(1)):09d}")
    return (0, pre)


def is_newer_version(latest: str, current: str) -> bool:
    """True si latest (tag ou version) est strictement plus récent que current."""
    la, ca = _strip_v(latest), _strip_v(current)
    if la == ca:
        return False
    lt, ct = _parse_version_tuple(la), _parse_version_tuple(ca)
    if lt != ct:
        return lt > ct
    return _prerelease_key(la) > _prerelease_key(ca)


def fetch_latest_release(repo: str = GITHUB_REPO) -> Optional[ReleaseInfo]:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None
    if not isinstance(data, dict):
        return None
    tag = data.get("tag_name")
    html = data.get("html_url")
    if not isinstance(tag, str) or not isinstance(html, str):
        return None
    return ReleaseInfo(
        tag_name=tag,
        html_url=html,
        name=str(data.get("name") or tag),
        body=str(data.get("body") or "")[:500],
    )


def check_for_update(current: Optional[str] = None) -> tuple[bool, Optional[ReleaseInfo]]:
    """Retourne (plus_récent_disponible, info_release)."""
    cur = current or __version__
    info = fetch_latest_release()
    if info is None:
        return False, None
    return is_newer_version(info.version, cur), info
