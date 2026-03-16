from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720

_FONT_PATHS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/calibri.ttf",
]


def generate_thumbnail(
    image_path: Path,
    output_path: Path,
    text: str = "",
    font_size: int = 52,
) -> Path:
    """
    Genera un thumbnail de 1280x720 para YouTube.

    - Recorta la imagen desde el centro para ajustarse a 16:9.
    - Si se provee text (brief.image_text), lo superpone en la esquina
      inferior izquierda con outline negro para legibilidad.

    Returns:
        Path al archivo thumbnail.jpg generado.
    """
    img = Image.open(image_path).convert("RGB")
    img = _resize_and_crop(img, THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)

    if text:
        _add_text_overlay(img, text, font_size=font_size)

    img.save(output_path, "JPEG", quality=95)
    print(f"[thumbnail] Generado: {output_path} ({THUMBNAIL_WIDTH}x{THUMBNAIL_HEIGHT})")
    return output_path


def _resize_and_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    """Redimensiona la imagen y recorta desde el centro para ajustarse al tamaño exacto."""
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Imagen más ancha: escalar por alto, recortar ancho
        new_height = height
        new_width = int(height * img_ratio)
    else:
        # Imagen más alta: escalar por ancho, recortar alto
        new_width = width
        new_height = int(width / img_ratio)

    img = img.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return img.crop((left, top, left + width, top + height))


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Intenta cargar una fuente del sistema. Fallback a la fuente default de PIL."""
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size=size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _add_text_overlay(img: Image.Image, text: str, font_size: int) -> None:
    """
    Superpone texto en la esquina inferior izquierda.
    Usa outline negro (8 direcciones) para que sea legible sobre cualquier fondo.
    Modifica img en el lugar (in-place).
    """
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size)

    padding = 36
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]

    x = padding
    y = img.height - text_height - padding

    # Outline negro en 8 direcciones para legibilidad sobre cualquier fondo
    outline = 3
    for dx in range(-outline, outline + 1):
        for dy in range(-outline, outline + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font)

    # Texto principal blanco
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
