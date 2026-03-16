from __future__ import annotations

import os
import textwrap
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.core.brief import Brief

load_dotenv()

DALLE_COST_USD = 0.08  # DALL-E 3 standard 1792x1024 (landscape 16:9)

# Texto sobre la imagen
_FONT_PATHS = [
    "C:/Windows/Fonts/georgiab.ttf",   # Georgia Bold — retro serif (preferida)
    "C:/Windows/Fonts/georgia.ttf",    # Georgia Regular
    "C:/Windows/Fonts/pala.ttf",       # Palatino Linotype
    "C:/Windows/Fonts/timesbd.ttf",    # Times New Roman Bold
    "C:/Windows/Fonts/arialbd.ttf",    # fallback
    "C:/Windows/Fonts/arial.ttf",
]
TITLE_FONT_SIZE = 46
TITLE_MAX_LINE_CHARS = 50   # wrap antes de este ancho
TITLE_LINE_SPACING = 12
GRADIENT_HEIGHT_RATIO = 0.35  # el gradiente cubre el 35% inferior de la imagen


@dataclass(frozen=True)
class VisualResult:
    image_path: Path
    source: str       # "api" | "manual"
    prompt_used: str
    cost_usd: float


def generate_image(brief: Brief, run_dir: Path) -> VisualResult:
    """
    Genera imagen con DALL-E 3, le agrega el título con Pillow y la guarda
    en run_dir/image.png redimensionada a 1280x720.

    Raises:
        ValueError: Si no hay OPENAI_API_KEY o el brief no tiene dalle_prompt.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY no configurada en .env")

    prompt = brief.dalle_prompt
    if not prompt:
        raise ValueError("El brief no tiene dalle_prompt — regenerar el brief")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    print("[visual_agent] Generando imagen con DALL-E 3...")
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024",  # Landscape nativo ~16:9, sin recorte
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url
    raw_path = run_dir / "image_raw.png"

    print("[visual_agent] Descargando imagen...")
    urllib.request.urlretrieve(image_url, raw_path)

    image_path = run_dir / "image.png"
    _process_image(raw_path, image_path, title=brief.title)
    print(f"[visual_agent] Imagen lista: {image_path}")

    return VisualResult(
        image_path=image_path,
        source="api",
        prompt_used=prompt,
        cost_usd=DALLE_COST_USD,
    )


def _process_image(src: Path, dst: Path, title: str) -> None:
    """Redimensiona a 1280x720 y superpone el título con Pillow."""
    from PIL import Image

    img = Image.open(src).convert("RGB")
    img = _resize_and_crop(img, 1280, 720)

    if title:
        img = _add_title(img, title)

    img.save(dst, "PNG")


def _resize_and_crop(img, width: int, height: int):
    from PIL import Image
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        new_height = height
        new_width = int(height * img_ratio)
    else:
        new_width = width
        new_height = int(width / img_ratio)

    img = img.resize((new_width, new_height), Image.LANCZOS)
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return img.crop((left, top, left + width, top + height))


def _add_title(img, title: str):
    """
    Superpone el título con estilo chyron retro:
    - Barra oscura sepia a ancho completo con opacidad ~80%
    - Líneas doradas decorativas arriba y abajo de la barra
    - Fuente serif (Georgia), texto color crema
    Retorna la imagen modificada.
    """
    from PIL import Image, ImageDraw, ImageFont

    draw = ImageDraw.Draw(img)

    font = None
    for fp in _FONT_PATHS:
        try:
            font = ImageFont.truetype(fp, size=TITLE_FONT_SIZE)
            break
        except (IOError, OSError):
            continue
    if font is None:
        font = ImageFont.load_default()

    lines = textwrap.wrap(title, width=TITLE_MAX_LINE_CHARS)

    sample_bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = sample_bbox[3] - sample_bbox[1]
    total_text_h = len(lines) * line_height + (len(lines) - 1) * TITLE_LINE_SPACING

    # Dimensiones de la barra
    bar_padding_v = 22
    bar_h = total_text_h + bar_padding_v * 2
    bar_margin_bottom = 48
    bar_y = img.height - bar_h - bar_margin_bottom

    # Barra semi-transparente sepia oscura
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    draw_ov.rectangle(
        [(0, bar_y), (img.width, bar_y + bar_h)],
        fill=(18, 8, 2, 205),  # sepia oscuro, ~80% opacidad
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Líneas doradas decorativas
    gold = (190, 155, 85)
    draw.line([(0, bar_y), (img.width, bar_y)], fill=gold, width=2)
    draw.line([(0, bar_y + bar_h), (img.width, bar_y + bar_h)], fill=gold, width=2)

    # Texto centrado dentro de la barra
    y = bar_y + bar_padding_v
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (img.width - text_w) // 2

        # Sombra sutil
        draw.text((x + 1, y + 2), line, fill=(0, 0, 0, 180), font=font)
        # Texto crema
        draw.text((x, y), line, fill=(245, 232, 200), font=font)
        y += line_height + TITLE_LINE_SPACING

    return img
