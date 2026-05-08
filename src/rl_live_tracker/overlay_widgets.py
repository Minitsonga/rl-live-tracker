"""Fenêtres frameless transparentes always-on-top (drag optionnel)."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QCursor, QFont, QGuiApplication, QScreen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .applog import warn_log


CORNER_ANCHORS = ("top-left", "top-right", "bottom-left", "bottom-right")
ALL_ANCHORS = CORNER_ANCHORS + ("custom",)


def resolve_overlay_screen(cfg: dict) -> QScreen | None:
    """Écran utilisé pour positionner les overlays (ancres) et centrer le menu."""
    screens = QGuiApplication.screens()
    if not screens:
        return None
    v = cfg.get("overlay_screen", "primary")
    if isinstance(v, bool):
        v = "primary"
    if isinstance(v, int):
        i = int(v)
        if 0 <= i < len(screens):
            return screens[i]
        return QGuiApplication.primaryScreen()
    if isinstance(v, str):
        s = v.strip().lower()
        if s == "cursor":
            return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    return QGuiApplication.primaryScreen()


def _infer_homologous_screen_pivot(widget_geo: QRect, screen_geo: QRect) -> str:
    """Coin du widget le plus proche du coin d'écran homologue (TL↔TL, …)."""
    pairs: tuple[tuple[str, QPoint, QPoint], ...] = (
        ("top-left", widget_geo.topLeft(), screen_geo.topLeft()),
        ("top-right", widget_geo.topRight(), screen_geo.topRight()),
        ("bottom-left", widget_geo.bottomLeft(), screen_geo.bottomLeft()),
        ("bottom-right", widget_geo.bottomRight(), screen_geo.bottomRight()),
    )
    best_name = "top-right"
    best_d = 10**18
    for name, wp, sp in pairs:
        d = (wp.x() - sp.x()) ** 2 + (wp.y() - sp.y()) ** 2
        if d < best_d:
            best_d = d
            best_name = name
    return best_name


def _new_topleft_keeping_corner(
    old_geo: QRect, pivot: str, new_w: int, new_h: int
) -> tuple[int, int]:
    """Coins Qt inclusifs (topRight, …) : garde ce pixel stable après changement de taille."""
    nw = max(new_w, 1)
    nh = max(new_h, 1)
    if pivot == "top-left":
        p = old_geo.topLeft()
        return p.x(), p.y()
    if pivot == "top-right":
        p = old_geo.topRight()
        return p.x() - nw + 1, p.y()
    if pivot == "bottom-left":
        p = old_geo.bottomLeft()
        return p.x(), p.y() - nh + 1
    if pivot == "bottom-right":
        p = old_geo.bottomRight()
        return p.x() - nw + 1, p.y() - nh + 1
    p = old_geo.topLeft()
    return p.x(), p.y()


class TransparentOverlay(QWidget):
    """Overlay click-through sauf en mode drag ; `position_*_anchor` + `position_*_custom_xy`."""

    positionCommitted = Signal()

    def __init__(
        self,
        cfg: dict,
        width_key: str = "width_session",
        position_key: str = "position_session",
        *,
        word_wrap: bool = True,
        body_font_pt: int | None = None,
    ):
        super().__init__()
        self.cfg = cfg
        self._width_key = width_key
        self._position_key = position_key
        self._max_width_px = max(int(cfg.get(width_key, 320)), 32)
        self._want_word_wrap = word_wrap
        self._drag_enabled = False
        self._drag_offset = QPoint()
        self._dragging = False
        self._custom_pos_key = f"{position_key}_custom_xy"
        self._anchor_key = f"{position_key}_anchor"
        self._resize_pivot: str | None = None

        self._apply_window_flags()
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._label = QLabel(self)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._label.setTextFormat(Qt.RichText)
        self._label.setWordWrap(word_wrap)

        self._body_font_pt = body_font_pt
        self._apply_style_from_cfg()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._label.setText("")
        self.resize(72, 48)
        self.hide()

    def _apply_style_from_cfg(self) -> None:
        bg = self.cfg.get("background_rgba")
        border = self.cfg.get("border_rgba")
        bg_vals = bg if isinstance(bg, (list, tuple)) else [10, 12, 16, 110]
        border_vals = border if isinstance(border, (list, tuple)) else [0, 200, 255, 45]
        bg_rgba = ",".join(str(int(bg_vals[i]) if i < len(bg_vals) else [10, 12, 16, 110][i]) for i in range(4))
        border_rgba = ",".join(
            str(int(border_vals[i]) if i < len(border_vals) else [0, 200, 255, 45][i]) for i in range(4)
        )
        radius = int(self.cfg.get("border_radius_px", 6))
        tc = self.cfg.get("text_color", "#e4eaf4")
        ff = self.cfg.get("font_family", "Segoe UI")
        fs = int(self._body_font_pt) if self._body_font_pt is not None else int(
            self.cfg.get("font_size", 10)
        )
        self._label.setFont(QFont(ff, fs))
        pad = self.cfg.get("overlay_padding_px") or [8, 10]
        py, px = (int(pad[0]), int(pad[1])) if len(pad) >= 2 else (8, 10)
        self._label.setStyleSheet(
            "QLabel {"
            f"  color: {tc};"
            f"  background-color: rgba({bg_rgba});"
            f"  border: 1px solid rgba({border_rgba});"
            f"  border-radius: {radius}px;"
            f"  padding: {py}px {px}px;"
            "}"
        )

    def anchor_key(self) -> str:
        return self._anchor_key

    def _apply_html_and_layout(self, html: str) -> None:
        mw = max(int(self.cfg.get(self._width_key, self._max_width_px)), 32)
        self._max_width_px = mw
        lbl = self._label
        lbl.setWordWrap(False)
        lbl.setMinimumWidth(0)
        lbl.setMaximumWidth(16777215)
        lbl.setText(html)
        lbl.adjustSize()
        natural = max(lbl.sizeHint().width(), 1)

        if self._want_word_wrap and natural > mw:
            lbl.setWordWrap(True)
            lbl.setFixedWidth(mw)
        else:
            lbl.setWordWrap(False)
            if not self._want_word_wrap:
                # Session card: width_session is only a hard cap with min(natural, mw).
                # If content is narrower than the cap, raising width_session does nothing unless
                # session_width_fill blends toward the cap (0 = tight, 1 = full cap width).
                fill = float(self.cfg.get("session_width_fill", 0.0) or 0.0)
                fill = max(0.0, min(1.0, fill))
                if mw >= natural:
                    wid = int(round(natural + (mw - natural) * fill))
                else:
                    wid = mw
                wid = max(32, min(wid, mw))
                lbl.setFixedWidth(wid)
            else:
                lbl.setFixedWidth(min(natural, mw))

        lbl.adjustSize()
        self.adjustSize()

    def _custom_xy_ok(self, raw: object) -> bool:
        return (
            isinstance(raw, (list, tuple))
            and len(raw) == 2
            and all(isinstance(v, (int, float)) for v in raw)
        )

    def set_html(self, html: str) -> None:
        self._apply_style_from_cfg()
        screen_obj = resolve_overlay_screen(self.cfg)
        anchor = self._resolved_anchor()
        cx: int | None = None
        cy: int | None = None
        raw_xy = self.cfg.get(self._custom_pos_key)
        if anchor == "custom" and self._custom_xy_ok(raw_xy):
            cx, cy = int(raw_xy[0]), int(raw_xy[1])  # type: ignore[index]
            self.move(cx, cy)

        old_geo = self.frameGeometry()
        self._apply_html_and_layout(html)

        if screen_obj is None:
            self._resize_pivot = None
            return

        nw, nh = self.width(), self.height()
        screen_rect = screen_obj.availableGeometry()

        if anchor == "custom" and cx is not None and cy is not None:
            hyp_final = QRect(cx, cy, nw, nh)
            if self._resize_pivot is None:
                self._resize_pivot = _infer_homologous_screen_pivot(hyp_final, screen_rect)

            pivot = self._resize_pivot
            if (
                old_geo.width() <= 96
                and old_geo.height() <= 96
                and nw > old_geo.width()
                and nh > old_geo.height()
            ):
                self.move(cx, cy)
                self.cfg[self._custom_pos_key] = [cx, cy]
            else:
                nx, ny = _new_topleft_keeping_corner(old_geo, pivot, nw, nh)
                self.move(nx, ny)
                self.cfg[self._custom_pos_key] = [int(nx), int(ny)]
        else:
            self._resize_pivot = None
            self._reposition()

    def set_drag_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._drag_enabled:
            return
        self._drag_enabled = enabled
        # Le QLabel recouvre toute la fenêtre : sans ça, le parent ne reçoit pas les événements souris.
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        was_visible = self.isVisible()
        self._apply_window_flags()
        if was_visible:
            self.show()
            self.raise_()

    def current_pos(self) -> tuple[int, int]:
        p = self.pos()
        return int(p.x()), int(p.y())

    def _apply_window_flags(self) -> None:
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        # En mode drag : la fenêtre doit accepter la souris (et le focus évite des soucis sous Windows).
        if not self._drag_enabled:
            flags |= Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating, not self._drag_enabled)

    def _sync_resize_pivot(self) -> None:
        anchor = self._resolved_anchor()
        if anchor != "custom":
            self._resize_pivot = None
            return
        screen_obj = resolve_overlay_screen(self.cfg)
        if screen_obj is None:
            self._resize_pivot = None
            return
        self._resize_pivot = _infer_homologous_screen_pivot(
            self.frameGeometry(),
            screen_obj.availableGeometry(),
        )

    def _resolved_anchor(self) -> str:
        a = self.cfg.get(self._anchor_key)
        if isinstance(a, str):
            a = a.strip().lower()
        if a not in ALL_ANCHORS:
            # Legacy : clé position_session encore présente
            legacy = self.cfg.get(self._position_key, "top-right")
            if isinstance(legacy, str):
                legacy = legacy.lower()
            if legacy == "top-center":
                legacy = "top-right"
            if legacy in CORNER_ANCHORS:
                return legacy
            return "top-right"
        return a

    def _reposition(self) -> None:
        anchor = self._resolved_anchor()
        if anchor == "custom":
            custom = self.cfg.get(self._custom_pos_key)
            if self._custom_xy_ok(custom):
                self.move(int(custom[0]), int(custom[1]))  # type: ignore[arg-type,index]
                return
            anchor = "top-right"

        screen_obj = resolve_overlay_screen(self.cfg)
        if screen_obj is None:
            return
        screen = screen_obj.availableGeometry()
        m = int(self.cfg.get("margin", 20))
        w, h = self.width(), self.height()
        if anchor not in CORNER_ANCHORS:
            warn_log(f"unknown anchor {anchor!r}, using top-right")
            anchor = "top-right"
        coords = {
            "top-left": (screen.left() + m, screen.top() + m),
            "top-right": (screen.right() - w - m, screen.top() + m),
            "bottom-left": (screen.left() + m, screen.bottom() - h - m),
            "bottom-right": (screen.right() - w - m, screen.bottom() - h - m),
        }
        x, y = coords[anchor]
        self.move(x, y)

    def reposition(self) -> None:
        """Repositionne selon `position_*_anchor` / `position_*_custom_xy` (sans changer le HTML)."""
        self._reposition()
        anchor = self._resolved_anchor()
        if anchor != "custom":
            self._resize_pivot = None
            return
        if self._custom_xy_ok(self.cfg.get(self._custom_pos_key)):
            self._sync_resize_pivot()

    def mousePressEvent(self, event):
        if not self._drag_enabled:
            return super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self._drag_enabled:
            return super().mouseMoveEvent(event)
        if self._dragging and (event.buttons() & Qt.LeftButton):
            pos = event.globalPosition().toPoint() - self._drag_offset
            self.move(pos)
            self.cfg[self._custom_pos_key] = [int(pos.x()), int(pos.y())]
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._drag_enabled:
            return super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self._dragging = False
            p = self.pos()
            self.cfg[self._custom_pos_key] = [int(p.x()), int(p.y())]
            self._sync_resize_pivot()
            self.positionCommitted.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)
