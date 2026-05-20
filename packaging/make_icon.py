"""Prépare app_icon.png (rogne, carré, RGBA) et génère app.ico multi-résolution."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_BRANDING = _ROOT / "branding"
_PNG = _BRANDING / "app_icon.png"
_ICO = _BRANDING / "app.ico"
# Tailles barre des tâches Windows (y compris HiDPI)
_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
_MASTER_SIZE = 1024
_MARGIN_RATIO = 0.06


def prepare_app_icon_png(src: Path, dest: Path, *, size: int = _MASTER_SIZE) -> None:
    """Rogne le fond transparent, centre sur un carré, exporte en PNG."""
    from PIL import Image

    img = Image.open(src).convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    side = max(w, h)
    margin = max(1, int(side * _MARGIN_RATIO))
    canvas_side = side + 2 * margin
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    ox = (canvas_side - w) // 2
    oy = (canvas_side - h) // 2
    canvas.paste(img, (ox, oy), img)
    out = canvas.resize((size, size), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "PNG")


def write_ico_from_png(png: Path, ico: Path) -> None:
    from PIL import Image

    img = Image.open(png).convert("RGBA")
    icons = [img.resize((s, s), Image.Resampling.LANCZOS) for s in _SIZES]
    icons[0].save(
        ico,
        format="ICO",
        sizes=[(s, s) for s in _SIZES],
        append_images=icons[1:],
    )


def _find_source_png() -> Path | None:
    """Source brute : app_icon_source.png, sinon tout PNG sauf app_icon.png."""
    source = _BRANDING / "app_icon_source.png"
    if source.is_file():
        return source
    for candidate in sorted(_BRANDING.glob("*.png")):
        if candidate.name not in ("app_icon.png",):
            return candidate
    if _PNG.is_file():
        return _PNG
    return None


def main() -> int:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Install Pillow: pip install pillow", file=sys.stderr)
        return 1

    src = _find_source_png()
    if src is None:
        print(f"Missing PNG in {_BRANDING}", file=sys.stderr)
        return 1

    # Toujours re-normaliser (rogne + carré) avant ICO.
    prepare_app_icon_png(src, _PNG)
    write_ico_from_png(_PNG, _ICO)
    print(f"Wrote {_PNG} ({_MASTER_SIZE}x{_MASTER_SIZE} RGBA)")
    print(f"Wrote {_ICO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
