"""Genera favicon.ico y favicon PNG a partir del diseño de NEXUS.

Uso: python tools/generar_icono.py
Se ejecuta una sola vez; los iconos generados se guardan en static/.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent.parent / "static"
BASE = 512  # se dibuja grande y luego se reduce (antialias limpio)

TOP = (91, 143, 196)     # #5b8fc4
BOTTOM = (61, 109, 157)  # #3d6d9d
WHITE = (255, 255, 255)


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = size * 0.03
    box = (margin, margin, size - margin, size - margin)
    radius = size * 0.22

    # Degradado vertical de fondo.
    grad = Image.new("RGB", (1, size), TOP)
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / max(1, size - 1)
        gd.point((0, y), fill=(
            round(TOP[0] + (BOTTOM[0] - TOP[0]) * t),
            round(TOP[1] + (BOTTOM[1] - TOP[1]) * t),
            round(TOP[2] + (BOTTOM[2] - TOP[2]) * t),
        ))
    grad = grad.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)

    # La "N" como trazo angular.
    stroke = round(size * 0.10)
    pts = [(size * 0.26, size * 0.74), (size * 0.26, size * 0.26),
           (size * 0.74, size * 0.74), (size * 0.74, size * 0.26)]
    d.line(pts, fill=WHITE, width=stroke, joint="curve")
    # Extremos redondeados.
    for x, y in pts:
        r = stroke / 2
        d.ellipse((x - r, y - r, x + r, y + r), fill=WHITE)

    # Nodo de vigilancia en la esquina superior derecha.
    cx, cy, r_outer = size * 0.74, size * 0.26, size * 0.115
    d.ellipse((cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer), fill=WHITE)
    r_in = r_outer * 0.42
    d.ellipse((cx - r_in, cy - r_in, cx + r_in, cy + r_in), fill=BOTTOM)

    return img


def main() -> None:
    big = draw_icon(BASE)

    big.resize((512, 512), Image.LANCZOS).save(STATIC / "favicon-512.png")
    big.resize((192, 192), Image.LANCZOS).save(STATIC / "favicon-192.png")
    big.resize((180, 180), Image.LANCZOS).save(STATIC / "apple-touch-icon.png")

    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    big.save(STATIC / "favicon.ico", format="ICO", sizes=ico_sizes)

    for name in ("favicon.ico", "favicon-192.png", "favicon-512.png",
                 "apple-touch-icon.png"):
        print(f"{name}: {(STATIC / name).stat().st_size} bytes")


if __name__ == "__main__":
    main()
