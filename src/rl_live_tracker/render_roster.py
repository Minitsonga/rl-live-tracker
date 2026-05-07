"""Compact HTML for lobby roster (in-game MMR).

La police de base vient du QFont du QLabel (config) — pas de font-family dans le HTML."""
from __future__ import annotations

from typing import Any, Optional

RO_CANON = frozenset({"full", "mmr_only", "full_2v2_mmr"})
# Anciens réglages → "full"
_LEGACY_ROSTER_PRESET = frozenset({"compact", "rank_only"})

# (preset_id, libellé menu — exemples sans pseudo, affiché à côté du nom)
ROSTER_MMR_PRESET_OPTIONS: tuple[tuple[str, str], ...] = (
    (
        "full",
        "Rank + MMR · ex. Diamond 2 Div II (1200) - 2v2: Champion 1 Div III (1320)",
    ),
    (
        "mmr_only",
        "MMR label · ex. 1v1: 860 - 2v2: 1500",
    ),
    (
        "full_2v2_mmr",
        "Full rank (active mode) + 2v2: MMR only · ex. Diamond 2 Div II (1200) - 2v2: 1320",
    ),
)


def _mmr_to_int(mmr: Any) -> Optional[int]:
    if mmr is None:
        return None
    try:
        return int(round(float(mmr)))
    except (TypeError, ValueError):
        return None


def roster_mmr_preset(cfg: dict) -> str:
    v = str(cfg.get("roster_mmr_preset") or "full").strip().lower()
    if v in _LEGACY_ROSTER_PRESET:
        return "full"
    return v if v in RO_CANON else "full"


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


_NB = "&nbsp;"


def roster_overlay_empty_html(cfg: dict) -> str:
    mc = cfg.get("muted_color", "#5a6578")
    return f'<div style="color:{mc}; font-size:9pt;">No lobby — waiting…</div>'


def _rank_full_segment(pl_row: dict) -> str:
    tier = pl_row.get("tier") or "?"
    div = str(pl_row.get("division") or "").strip()
    if div.lower().startswith("division "):
        div = div[len("division "):].strip()
    if div and not div.lower().startswith("div "):
        div = f"Div {div}"
    mmr = pl_row.get("mmr")
    parts_td = [str(tier)]
    if div:
        parts_td.append(str(div))
    rank_str = " ".join(parts_td)
    m_i = _mmr_to_int(mmr)
    if m_i is not None:
        return f"{rank_str} ({m_i})"
    return rank_str


def format_roster_mmr_only_main(active_pl: str, pl_row: dict) -> str:
    """Ex. « 1v1 : 860 » (espaces autour de « : »)."""
    m_i = _mmr_to_int(pl_row.get("mmr"))
    if m_i is None:
        return "—"
    return f"{active_pl} : {m_i}"


def format_roster_main_for_preset(
    main: dict, active_pl: str, preset: str
) -> str:
    p = roster_mmr_preset({"roster_mmr_preset": preset})
    if p == "mmr_only":
        return format_roster_mmr_only_main(active_pl, main)
    return _rank_full_segment(main)


def format_roster_secondary_2v2(r2: dict, preset: str) -> str:
    """Si pas en 2v2 : rappel 2v2 — rang complet (full) ou « 2v2 : mmr » (mmr_only / full_2v2_mmr)."""
    if not isinstance(r2, dict):
        return ""
    p = roster_mmr_preset({"roster_mmr_preset": preset})
    if p == "full":
        inner = _rank_full_segment(r2)
        if not inner or inner == "—":
            return ""
        return f"2v2 : {inner}"
    # mmr_only et full_2v2_mmr : MMR 2v2 uniquement
    m_i = _mmr_to_int(r2.get("mmr"))
    if m_i is None:
        return ""
    return f"2v2 : {m_i}"


def _rank_body_span(plain: str) -> str:
    return (
        "<span style='color:#d2dcea; font-size:10pt; font-weight:550; "
        "letter-spacing:-0.01em;'>"
        f"{_esc(plain)}</span>"
    )


def _line_for_player(
    name: str,
    entry: Optional[dict],
    active_pl: str,
    show_mmr: bool,
    preset: str,
) -> str:
    sep_mid = (
        "<span style='color:#627286; font-weight:600; font-size:9pt;'>"
        f"{_NB}-{_NB}</span>"
    )
    name_html = (
        "<span style='color:#f0f4fb; font-size:10pt; font-weight:650; "
        "letter-spacing:0.01em;'>"
        f"{_esc(name)}</span>"
        f"{_NB}"
        "<span style='color:#8a97a8; font-size:10pt; font-weight:600; "
        "margin-right:2pt;'>=&gt;</span>"
    )
    after_arrow = _NB
    if not show_mmr:
        return name_html

    if not entry or entry.get("not_found"):
        return (
            f"{name_html}{after_arrow}"
            "<span style='color:#7a8a9e; font-size:9pt;'>TRN —</span>"
        )

    pls: dict[str, Any] = entry.get("playlists") or {}
    main = pls.get(active_pl)
    if main:
        main_plain = format_roster_main_for_preset(main, active_pl, preset)
        chunks: list[str] = [
            name_html,
            after_arrow,
            _rank_body_span(main_plain),
        ]
        if active_pl != "2v2":
            r2 = pls.get("2v2")
            r2_txt = format_roster_secondary_2v2(r2, preset)
            if r2_txt:
                chunks.append(sep_mid)
                chunks.append(_rank_body_span(r2_txt))
        return "".join(chunks)

    best = entry.get("best")
    if isinstance(best, dict) and best.get("mmr") is not None:
        bpl = str(best.get("playlist") or "?")
        p = roster_mmr_preset({"roster_mmr_preset": preset})
        if p == "mmr_only":
            frag = format_roster_mmr_only_main(bpl, best)
        else:
            frag = _rank_full_segment(best)
        return (
            f"{name_html}{after_arrow}"
            "<span style='color:#9eb0c4; font-size:9pt;'>best "
            f"{_esc(bpl)} {_esc(frag)}</span>"
        )
    return (
        f"{name_html}{after_arrow}"
        "<span style='color:#7a8a9e; font-size:9pt;'>—</span>"
    )


def render_roster_html(
    cfg: dict,
    roster: list[dict],
    mmr_db: dict[str, Optional[dict]],
    active_pl: str,
) -> str:
    show_mmr = bool(cfg.get("show_mmr_ingame", True))
    preset = roster_mmr_preset(cfg)
    mc = cfg.get("muted_color", "#a8b4c8")
    bc = cfg.get("accent_color", "#00c8ff")

    blue = [p for p in roster if p.get("team") == 0]
    orange = [p for p in roster if p.get("team") == 1]
    blue.sort(key=lambda p: p.get("name") or "")
    orange.sort(key=lambda p: p.get("name") or "")

    def block(title: str, players: list[dict]) -> str:
        rows = []
        for p in players:
            k = p.get("key") or ""
            nm = p.get("name") or "?"
            ent = mmr_db.get(k)
            rows.append(
                "<div style='margin:0 0 2pt 0;line-height:1.25;'>"
                f"{_line_for_player(nm, ent, active_pl, show_mmr, preset)}</div>"
            )
        body = "".join(rows) if rows else f"<div style='color:{mc}; font-size:9pt;'>—</div>"
        return (
            f"<div style='margin-bottom:4pt;'>"
            f"<div style='color:{bc}; font-size:9pt; font-weight:700; "
            f"letter-spacing:0.12em; margin-bottom:1pt;'>{title}</div>"
            f"{body}</div>"
        )

    head = (
        f"<div style='color:{mc}; font-size:9pt; margin-bottom:3pt; "
        f"font-weight:700; letter-spacing:0.08em;'>{_esc(active_pl.upper())}</div>"
    )
    return head + block("BLUE", blue) + block("ORANGE", orange)


def render_roster_preview_html(cfg: dict) -> str:
    preset = roster_mmr_preset(cfg)
    active_pl = "2v2"
    if preset in ("mmr_only", "full_2v2_mmr"):
        # Use a non-2v2 active playlist to preview the 2v2 secondary segment too.
        active_pl = "1v1"

    roster = [
        {"key": "preview_blue_1", "name": "Blue One", "team": 0},
        {"key": "preview_blue_2", "name": "Blue Two", "team": 0},
        {"key": "preview_orange_1", "name": "Orange One", "team": 1},
        {"key": "preview_orange_2", "name": "Orange Two", "team": 1},
    ]
    mmr_db = {
        "preview_blue_1": {
            "playlists": {
                "1v1": {"mmr": 1154, "tier": "Diamond 1", "division": "III"},
                "2v2": {"mmr": 1310, "tier": "Champion 1", "division": "II"},
                "3v3": {"mmr": 1068, "tier": "Platinum 3", "division": "IV"},
            }
        },
        "preview_blue_2": {
            "playlists": {
                "1v1": {"mmr": 1092, "tier": "Platinum 3", "division": "II"},
                "2v2": {"mmr": 1242, "tier": "Diamond 3", "division": "III"},
                "3v3": {"mmr": 1028, "tier": "Platinum 2", "division": "IV"},
            }
        },
        "preview_orange_1": {
            "playlists": {
                "1v1": {"mmr": 1218, "tier": "Diamond 3", "division": "I"},
                "2v2": {"mmr": 1378, "tier": "Champion 2", "division": "I"},
                "3v3": {"mmr": 1136, "tier": "Diamond 1", "division": "I"},
            }
        },
        "preview_orange_2": {
            "playlists": {
                "1v1": {"mmr": 1036, "tier": "Platinum 2", "division": "I"},
                "2v2": {"mmr": 1198, "tier": "Diamond 2", "division": "II"},
                "3v3": {"mmr": 987, "tier": "Platinum 1", "division": "IV"},
            }
        },
    }
    return render_roster_html(cfg, roster, mmr_db, active_pl)
