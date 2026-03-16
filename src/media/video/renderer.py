from __future__ import annotations

from pathlib import Path

from moviepy import AudioFileClip, ImageClip
import moviepy.video.fx as vfx
import moviepy.audio.fx as afx


def render_video(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    fade_duration: float = 2.0,
    max_duration: float | None = None,
) -> Path:
    """
    Genera un video combinando una imagen estatica con un archivo de audio.

    Args:
        image_path: Ruta a la imagen.
        audio_path: Ruta al audio (mezclado).
        output_path: Donde guardar el video.mp4.
        fade_duration: Segundos de fade in/out (0 para desactivar).
        max_duration: Duracion maxima en segundos (None = duracion del audio).
    """
    print(f"[renderer] Imagen: {image_path}")
    print(f"[renderer] Audio: {audio_path}")

    audio = AudioFileClip(str(audio_path))

    # Aplicar duracion maxima si se especifica
    duration = audio.duration
    if max_duration is not None:
        duration = min(duration, max_duration)
        audio = audio.subclipped(0, duration)

    image = ImageClip(str(image_path)).with_duration(duration)

    # Aplicar fade in/out al video y al audio
    if fade_duration > 0:
        image = image.with_effects([
            vfx.FadeIn(fade_duration),
            vfx.FadeOut(fade_duration),
        ])
        audio = audio.with_effects([
            afx.AudioFadeIn(fade_duration),
            afx.AudioFadeOut(fade_duration),
        ])

    video = image.with_audio(audio)

    print(f"[renderer] Renderizando video ({duration:.1f}s, fade={fade_duration}s)...")

    video.write_videofile(
        str(output_path),
        fps=1,
        codec="libx264",
        audio_codec="aac",
        logger="bar",
    )

    audio.close()
    video.close()

    print(f"[renderer] Video generado: {output_path}")
    return output_path
