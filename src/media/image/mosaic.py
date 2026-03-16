"""
mosaic.py — Genera thumbnail mosaico para compilaciones Oldies Tango.

Crea una grilla de thumbnails individuales con overlay de texto.
Tamaño final: 1280x720 (16:9 estándar YouTube).
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_mosaic(
    thumbnail_paths: list[Path],
    output_path: Path,
    size: tuple[int, int] = (1280, 720),
    title_text: str = "OLDIES TANGO",
    subtitle_text: str = "Argentine Tango Compilation",
) -> Path:
    """
    Crea un mosaico de thumbnails para la portada de la compilación.

    Usa hasta 4 imágenes en grid 2x2. Si hay menos, rellena repitiendo.
    Agrega overlay oscuro en la parte inferior con título y subtítulo.
    """
    if not thumbnail_paths:
        raise ValueError("Se necesita al menos un thumbnail para el mosaico")

    # Siempre usar grid 2x2 (4 tiles) — más limpio visualmente
    cols, rows = 2, 2
    n_tiles = cols * rows
    tile_w = size[0] // cols
    tile_h = size[1] // rows

    # Seleccionar hasta 4 thumbnails (distribuidos en el video si hay más)
    if len(thumbnail_paths) >= n_tiles:
        step = len(thumbnail_paths) / n_tiles
        tiles = [thumbnail_paths[int(i * step)] for i in range(n_tiles)]
    else:
        # Repetir los disponibles para rellenar los 4 slots
        tiles = []
        for i in range(n_tiles):
            tiles.append(thumbnail_paths[i % len(thumbnail_paths)])

    # Construir mosaico base
    mosaic = Image.new("RGB", size, (10, 10, 18))

    for i, path in enumerate(tiles):
        row = i // cols
        col = i % cols
        try:
            img = Image.open(path).convert("RGB")
            img = img.resize((tile_w, tile_h), Image.LANCZOS)
            mosaic.paste(img, (col * tile_w, row * tile_h))
        except Exception:
            pass  # tile vacío si falla la imagen

    # Overlay semitransparente en la mitad inferior para legibilidad del texto
    overlay_height = 180
    gradient = Image.new("RGBA", (size[0], overlay_height), (0, 0, 0, 0))
    draw_grad = ImageDraw.Draw(gradient)
    for y in range(overlay_height):
        alpha = int(220 * (y / overlay_height))
        draw_grad.rectangle([0, y, size[0], y + 1], fill=(0, 0, 0, alpha))

    mosaic_rgba = mosaic.convert("RGBA")
    mosaic_rgba.paste(gradient, (0, size[1] - overlay_height), gradient)
    mosaic = mosaic_rgba.convert("RGB")

    # Texto
    draw = ImageDraw.Draw(mosaic)

    def _load_font(size_pt: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for font_name in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]:
            try:
                return ImageFont.truetype(font_name, size_pt)
            except OSError:
                continue
        return ImageFont.load_default()

    font_title = _load_font(58)
    font_sub = _load_font(26)

    cx = size[0] // 2
    y_title = size[1] - 110
    y_sub = size[1] - 42

    # Sombra del título
    for dx, dy in [(-2, -2), (2, 2), (-2, 2), (2, -2)]:
        draw.text((cx + dx, y_title + dy), title_text, font=font_title,
                  fill=(0, 0, 0), anchor="mm")
    draw.text((cx, y_title), title_text, font=font_title,
              fill=(201, 168, 76), anchor="mm")

    # Subtítulo
    draw.text((cx, y_sub), subtitle_text, font=font_sub,
              fill=(180, 160, 120), anchor="mm")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mosaic.save(str(output_path), "JPEG", quality=90)
    return output_path
