"""Rich HTML — session card. Espaces via &nbsp; (Qt RichText les conserve). Tailles modérées."""
from __future__ import annotations

from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session_state import SessionState

DEFAULT_MMR_DISPLAY = 600

_NB = "&nbsp;"
_NB2 = "&nbsp;&nbsp;"
_NB3 = "&nbsp;&nbsp;&nbsp;"

# fire.png à la racine du dépôt rl-live-tracker (à côté de src/)
_FIRE_PNG = Path(__file__).resolve().parent.parent.parent / "fire.png"


def _streak_fire_html() -> str:
    """Icône série : PNG local si présent, sinon emoji (fallback)."""
    p = _FIRE_PNG
    if p.is_file():
        uri = escape(p.as_uri(), quote=True)
        return (
            f'<img src="{uri}" width="15" height="15" '
            'style="vertical-align:-3px;"/>'
        )
    return "<span style='font-size:11pt; vertical-align:middle;'>🔥</span>"


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _playlist_label(playlist: str, in_match: bool) -> str:
    p = (playlist or "").strip().lower()
    mapping = {
        "1v1": "1v1",
        "2v2": "2v2",
        "3v3": "3v3",
        "other": "Other",
    }
    if not in_match:
        return "Menu"
    return mapping.get(p, "Other")


def render_session_html(cfg: dict, session: "SessionState", in_match: bool = False) -> str:
    ac = cfg.get("accent_color", "#00c8ff")
    tc = cfg.get("text_color", "#f4f7fc")
    lc_label = cfg.get("label_color", "#d4e2f4")
    wc = cfg.get("win_color", "#00e5a0")
    lc = cfg.get("loss_color", "#ff4060")
    mc = cfg.get("muted_color", "#b8c6d9")

    pl = session.active_playlist
    pl_label = _playlist_label(pl, in_match)
    if session.stats_connected:
        status_color = wc
    elif in_match:
        status_color = "#ffb347"
    else:
        status_color = lc
    show_mmr = bool(cfg.get("show_mmr_ingame", True))
    if not show_mmr:
        mmr_txt = "—"
    elif session.current_mmr is None:
        mmr_txt = str(DEFAULT_MMR_DISPLAY)
    else:
        mmr_txt = str(session.current_mmr)

    sess_d = session.session_delta_display(pl)
    if sess_d is None:
        sess_d = 0
    sd_col = wc if sess_d > 0 else (lc if sess_d < 0 else mc)
    sd_sign = f"+{sess_d}" if sess_d > 0 else str(sess_d)

    last_d = session.last_match_delta
    if last_d is not None:
        ld_col = wc if last_d > 0 else (lc if last_d < 0 else mc)
        ld_sign = f"+{last_d}" if last_d > 0 else str(last_d)
        last_val = f"<span style='color:{ld_col}; font-weight:800;'>{ld_sign}</span>"
    else:
        last_val = f"<span style='color:{mc}; font-weight:700;'>—</span>"

    # Série à droite sur la ligne MMR : valeur puis flamme (ex. 5🔥), — / -n / n
    fire = _streak_fire_html()
    if session.loss_streak > 0:
        streak_val = (
            f"<span style='font-size:10pt; color:{lc}; font-weight:800;'>"
            f"-{session.loss_streak}</span>"
        )
    elif session.win_streak > 0:
        streak_val = (
            f"<span style='font-size:10pt; color:{wc}; font-weight:800;'>"
            f"{session.win_streak}</span>"
        )
    else:
        streak_val = f"<span style='font-size:10pt; color:{mc}; font-weight:700;'>—</span>"
    streak_right = f"{streak_val}{_NB}{fire}"

    row_mmr_left = (
        f"<span style='font-size:9pt; color:{lc_label}; font-weight:700;'>MMR</span>"
        f"{_NB}<span style='font-size:12pt; color:{tc}; font-weight:800;'>{mmr_txt}</span>"
        f"{_NB}<span style='font-size:10pt; color:{sd_col}; font-weight:800;'>({sd_sign})</span>"
    )

    row_mmr = f"""<table border="0" cellspacing="0" cellpadding="0" width="100%" style="margin:0;"><tr>
<td style="vertical-align:middle; white-space:nowrap;">{row_mmr_left}</td>
<td align="right" style="vertical-align:middle; white-space:nowrap; padding-left:8pt;">{streak_right}</td>
</tr></table>"""

    row_bottom = (
        f"<span style='font-size:11pt; color:{wc}; font-weight:700;'>{session.wins}</span>"
        f"{_NB}<span style='font-size:10pt; color:{wc}; font-weight:800;'>W</span>"
        f"{_NB2}<span style='font-size:11pt; color:{lc}; font-weight:700;'>{session.losses}</span>"
        f"{_NB}<span style='font-size:10pt; color:{lc}; font-weight:800;'>L</span>"
        f"{_NB3}"
        f"<span style='font-size:10pt; color:{lc_label}; font-weight:700;'>Last : </span>"
        f"<span style='font-size:11pt;'>{last_val}</span>"
    )

    row_top = (
        f"""<table border="0" cellspacing="0" cellpadding="0" width="100%" style="margin:0;"><tr>
<td style="vertical-align:middle; white-space:nowrap;">
<span style='font-size:9pt; color:{ac}; font-weight:700;'>{_esc(pl_label)}</span>
</td>
<td align="right" style="vertical-align:middle; white-space:nowrap; padding-left:8pt;">
<span style='display:inline-block; width:8px; height:8px; border-radius:4px; background:{status_color};'></span>
</td>
</tr></table>"""
    )

    return f"""<table border="0" cellspacing="0" cellpadding="0" width="100%"
 style="margin:0; border-collapse:collapse;">
<tr><td style="padding:0 0 2px 0; line-height:1.2; white-space:nowrap;
 border-bottom:1px solid rgba(0,200,255,0.12);">{row_top}</td></tr>
<tr><td style="padding:3px 0 0 0; line-height:1.2; white-space:nowrap;">{row_mmr}</td></tr>
<tr><td style="padding:4px 0 0 0; line-height:1.25; white-space:nowrap;">{row_bottom}</td></tr>
</table>"""
