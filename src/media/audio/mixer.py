from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter


# ── Generadores de ambiente ────────────────────────────────────────

def _generate_rain(duration_sec: int, sample_rate: int = 44100) -> np.ndarray:
    """
    Genera sonido de lluvia suave con multiples capas:
    - Capa base: ruido banda-pasada (200-1200 Hz) = lluvia constante de fondo
    - Capa media: ruido banda-pasada (800-2500 Hz) con modulacion = gotas variando
    - Capa alta: impulsos suaves aleatorios = gotas individuales cayendo
    """
    n_samples = duration_sec * sample_rate

    # --- Capa 1: lluvia de fondo constante (frecuencias bajas, sonido grave) ---
    white1 = np.random.randn(n_samples).astype(np.float32)
    b_lo, a_lo = butter(3, [200 / (sample_rate / 2), 1200 / (sample_rate / 2)], btype="band")
    base = lfilter(b_lo, a_lo, white1).astype(np.float32)

    # --- Capa 2: variacion de intensidad (frecuencias medias, moduladas) ---
    white2 = np.random.randn(n_samples).astype(np.float32)
    b_mid, a_mid = butter(3, [800 / (sample_rate / 2), 2500 / (sample_rate / 2)], btype="band")
    mid = lfilter(b_mid, a_mid, white2).astype(np.float32)
    # Modular con onda lenta (la lluvia sube y baja de intensidad cada ~4-8 seg)
    mod_freq = np.random.uniform(0.12, 0.25)  # ciclos por segundo
    t = np.linspace(0, duration_sec, n_samples, dtype=np.float32)
    modulation = 0.5 + 0.5 * np.sin(2 * np.pi * mod_freq * t + np.random.uniform(0, 2 * np.pi))
    mid = mid * modulation

    # --- Capa 3: gotas individuales (microimpulsos suaves) ---
    drops = np.zeros(n_samples, dtype=np.float32)
    drops_per_sec = 30
    n_drops = duration_sec * drops_per_sec
    positions = np.random.randint(0, n_samples, n_drops)
    drops[positions] = np.random.uniform(0.2, 0.7, n_drops).astype(np.float32)
    # Suavizar gotas con pasa-bajos (que no suenen a click)
    b_drop, a_drop = butter(2, 1500 / (sample_rate / 2), btype="low")
    drops = lfilter(b_drop, a_drop, drops).astype(np.float32)

    # --- Mezcla final ---
    rain = base * 0.5 + mid * 0.35 + drops * 0.15
    peak = np.max(np.abs(rain))
    if peak > 0:
        rain = rain / peak
    return rain


def _generate_vinyl(duration_sec: int, sample_rate: int = 44100) -> np.ndarray:
    """Genera crackle de vinilo (ruido impulsivo suave)."""
    n_samples = duration_sec * sample_rate
    vinyl = np.zeros(n_samples, dtype=np.float32)
    # Clicks aleatorios (~8 por segundo)
    n_clicks = duration_sec * 8
    positions = np.random.randint(0, n_samples, n_clicks)
    vinyl[positions] = np.random.uniform(0.3, 1.0, n_clicks).astype(np.float32)
    # Suavizar con filtro pasa-bajos
    b, a = butter(2, 2000 / (sample_rate / 2), btype="low")
    vinyl = lfilter(b, a, vinyl).astype(np.float32)
    return vinyl


# ── Filtros de audio ───────────────────────────────────────────────

def _apply_lofi(audio: np.ndarray, sample_rate: int = 44100) -> np.ndarray:
    """Aplica efecto lo-fi: corta agudos y reduce rango dinamico."""
    # Cortar frecuencias arriba de 4kHz (simula parlante viejo)
    b, a = butter(3, 4000 / (sample_rate / 2), btype="low")
    filtered = lfilter(b, a, audio).astype(np.float32)
    return filtered


# ── Registro de efectos disponibles ────────────────────────────────

AMBIENCE_GENERATORS = {
    "rain": {"fn": _generate_rain, "volume": 0.15},
    "vinyl": {"fn": _generate_vinyl, "volume": 0.08},
}

FILTERS = {
    "lofi": _apply_lofi,
}


# ── Funcion principal ─────────────────────────────────────────────

def mix_audio(
    audio_path: Path,
    output_path: Path,
    fx_tags: list[str],
    sample_rate: int = 44100,
) -> Path:
    """
    Toma un audio base y le aplica efectos segun las tags del brief.

    Tags de ambiente (se mezclan sobre el audio): rain, vinyl
    Tags de filtro (modifican el audio base): lofi

    Ejemplo: fx_tags=["rain", "lofi"] → agrega lluvia + efecto lo-fi
    """
    from moviepy import AudioFileClip

    if not fx_tags:
        print("[mixer] Sin efectos, copiando audio original")
        import shutil
        shutil.copy2(audio_path, output_path)
        return output_path

    print(f"[mixer] Aplicando efectos: {fx_tags}")

    # Cargar audio base con moviepy (soporta mp3/wav/ogg)
    clip = AudioFileClip(str(audio_path))
    fps = clip.fps or sample_rate
    audio_array = clip.to_soundarray(fps=fps)
    clip.close()

    duration_sec = len(audio_array) // fps

    # Convertir a mono para procesar, luego volver a stereo
    if audio_array.ndim == 2:
        is_stereo = True
        mono = audio_array.mean(axis=1).astype(np.float32)
    else:
        is_stereo = False
        mono = audio_array.astype(np.float32)

    # Normalizar a [-1, 1]
    peak = np.max(np.abs(mono))
    if peak > 0:
        mono = mono / peak

    # 1. Aplicar filtros (modifican el audio base)
    for tag in fx_tags:
        if tag in FILTERS:
            print(f"[mixer]   Filtro: {tag}")
            mono = FILTERS[tag](mono, fps)

    # 2. Mezclar ambientes (se suman al audio)
    for tag in fx_tags:
        if tag in AMBIENCE_GENERATORS:
            gen = AMBIENCE_GENERATORS[tag]
            print(f"[mixer]   Ambiente: {tag} (vol={gen['volume']})")
            ambient = gen["fn"](duration_sec, fps)
            # Ajustar longitud al audio base
            if len(ambient) > len(mono):
                ambient = ambient[:len(mono)]
            elif len(ambient) < len(mono):
                ambient = np.pad(ambient, (0, len(mono) - len(ambient)))
            mono = mono + ambient * gen["volume"]

    # Normalizar resultado final
    peak = np.max(np.abs(mono))
    if peak > 0:
        mono = mono / peak * 0.95  # headroom

    # Convertir a stereo si el original lo era
    if is_stereo:
        stereo = np.column_stack([mono, mono])
        result = (stereo * 32767).astype(np.int16)
    else:
        result = (mono * 32767).astype(np.int16)

    wavfile.write(str(output_path), fps, result)
    print(f"[mixer] Audio procesado: {output_path}")
    return output_path
