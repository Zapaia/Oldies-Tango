"""
Buscador y descargador de tangos de dominio publico desde archive.org.

Usa la API publica de archive.org (sin API key):
- Buscar: GET /advancedsearch.php?q={query}&fl[]=identifier&fl[]=title&fl[]=creator&rows=10&output=json
- Metadata: GET /metadata/{identifier}/files
- Descargar: GET /download/{identifier}/{filename}
"""
from __future__ import annotations

import json
import random
import urllib.request
import urllib.parse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArchiveResult:
    """Un resultado de busqueda en archive.org."""
    identifier: str
    title: str
    creator: str


@dataclass(frozen=True)
class DownloadedTrack:
    """Track descargado exitosamente."""
    audio_path: Path
    title: str
    artist: str
    source_url: str
    identifier: str


AUDIO_EXTENSIONS = (".mp3", ".flac", ".ogg", ".wav")
USED_SONGS_PATH = Path("data/used_songs.json")
BLACKLIST_PATH = Path("data/blacklist_identifiers.json")


def _load_used_identifiers() -> set[str]:
    """Carga los identificadores de canciones ya usadas."""
    if USED_SONGS_PATH.exists():
        return set(json.loads(USED_SONGS_PATH.read_text(encoding="utf-8")))
    return set()


def _save_used_identifier(identifier: str) -> None:
    """Agrega un identificador al historial de canciones usadas."""
    used = _load_used_identifiers()
    used.add(identifier)
    USED_SONGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    USED_SONGS_PATH.write_text(json.dumps(sorted(used), indent=2), encoding="utf-8")


def _load_blacklist() -> set[str]:
    """Carga el blacklist de grabaciones con ContentID en YouTube."""
    if BLACKLIST_PATH.exists():
        return set(json.loads(BLACKLIST_PATH.read_text(encoding="utf-8")))
    return set()


def add_to_blacklist(identifier: str) -> None:
    """
    Agrega un archive.org identifier al blacklist.

    Llamar cuando YouTube detecta ContentID claim en un video que usó esa grabación.
    Los futuros runs saltearán automáticamente este identifier.
    """
    blacklist = _load_blacklist()
    if identifier in blacklist:
        return
    blacklist.add(identifier)
    BLACKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    BLACKLIST_PATH.write_text(json.dumps(sorted(blacklist), indent=2), encoding="utf-8")
    print(f"[public_domain] Blacklist actualizado: {identifier}")


def _build_query(query: str, artist: str = "") -> str:
    """
    Construye una query optimizada para archive.org.

    Usa campos estructurados (creator:, subject:) en vez de texto libre,
    porque archive.org responde mucho mejor a queries con campos.
    """
    parts = ["mediatype:audio"]

    if artist:
        # creator: es el campo mas efectivo en archive.org
        parts.append(f"creator:{artist}")
        parts.append("tango")
    elif query:
        # Si no hay artista, usar la query pero simplificada
        parts.append(query)
    else:
        parts.append("tango")

    return " ".join(parts)


def search_archive(query: str, rows: int = 20, artist: str = "") -> list[ArchiveResult]:
    """
    Busca items en archive.org.

    Args:
        query: Query de busqueda (ej: "tango gardel 1920s")
        rows: Cantidad maxima de resultados (aumentado a 20 para tener más variedad)
        artist: Nombre del artista (usa creator: field, mucho mas efectivo)

    Returns:
        Lista de ArchiveResult
    """
    full_query = _build_query(query, artist)

    params = urllib.parse.urlencode({
        "q": full_query,
        "fl[]": ["identifier", "title", "creator"],
        "rows": rows,
        "output": "json",
    }, doseq=True)

    url = f"https://archive.org/advancedsearch.php?{params}"
    print(f"[public_domain] Buscando en archive.org: {full_query}")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OldiesTango/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[public_domain] Error en busqueda: {e}")
        return []

    docs = data.get("response", {}).get("docs", [])
    results = []
    for doc in docs:
        # creator puede ser string o lista — normalizar a string
        creator = doc.get("creator", "")
        if isinstance(creator, list):
            creator = ", ".join(creator)
        results.append(ArchiveResult(
            identifier=doc.get("identifier", ""),
            title=doc.get("title", ""),
            creator=creator,
        ))

    print(f"[public_domain] {len(results)} resultados encontrados")
    return results


def get_audio_files(identifier: str) -> list[dict]:
    """
    Obtiene la lista de archivos de audio de un item en archive.org.

    Returns:
        Lista de dicts con 'name', 'format', 'size'
    """
    url = f"https://archive.org/metadata/{identifier}/files"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OldiesTango/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[public_domain] Error obteniendo metadata de {identifier}: {e}")
        return []

    files = data.get("result", [])
    audio_files = []
    for f in files:
        name = f.get("name", "")
        if name.lower().endswith(AUDIO_EXTENSIONS):
            audio_files.append({
                "name": name,
                "format": f.get("format", ""),
                "size": f.get("size", "0"),
            })

    return audio_files


def _pick_best_audio(files: list[dict]) -> dict | None:
    """Elige el mejor archivo de audio (prefiere MP3, luego FLAC, luego otros)."""
    if not files:
        return None

    # Prioridad: MP3 > FLAC > OGG > WAV
    priority = {".mp3": 0, ".flac": 1, ".ogg": 2, ".wav": 3}
    files_sorted = sorted(
        files,
        key=lambda f: priority.get(Path(f["name"]).suffix.lower(), 99)
    )
    return files_sorted[0]


def download_audio(identifier: str, filename: str, dest_dir: Path) -> Path:
    """
    Descarga un archivo de audio de archive.org.

    Args:
        identifier: ID del item en archive.org
        filename: Nombre del archivo a descargar
        dest_dir: Directorio destino

    Returns:
        Path al archivo descargado
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Sanitizar nombre para filesystem
    safe_name = filename.replace("/", "_").replace("\\", "_")
    dest_path = dest_dir / safe_name

    url = f"https://archive.org/download/{identifier}/{urllib.parse.quote(filename)}"
    print(f"[public_domain] Descargando: {filename}")

    req = urllib.request.Request(url, headers={"User-Agent": "OldiesTango/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest_path.write_bytes(resp.read())

    size_mb = dest_path.stat().st_size / (1024 * 1024)
    print(f"[public_domain] Descargado: {safe_name} ({size_mb:.1f} MB)")
    return dest_path


def search_and_download(
    query: str,
    dest_dir: Path,
    artist_hint: str = "",
) -> DownloadedTrack | None:
    """
    Busca un tango en archive.org y descarga el mejor match.
    Evita repetir canciones usando data/used_songs.json.

    Args:
        query: Query de busqueda
        dest_dir: Directorio donde guardar el audio
        artist_hint: Artista preferido (para filtrar resultados)

    Returns:
        DownloadedTrack si tuvo exito, None si no encontro nada
    """
    results = search_archive(query, artist=artist_hint)
    if not results:
        return None

    # Si hay artist_hint, priorizar resultados de ese artista
    if artist_hint:
        artist_lower = artist_hint.lower()
        prioritized = [r for r in results if artist_lower in r.creator.lower()]
        others = [r for r in results if r not in prioritized]
        results = prioritized + others

    # Filtrar blacklist (grabaciones con ContentID claim — nunca reusar)
    blacklist = _load_blacklist()
    results = [r for r in results if r.identifier not in blacklist]

    if not results:
        print(f"[public_domain] Todos los resultados están en el blacklist ContentID para '{artist_hint}'")
        return None

    # Filtrar canciones ya usadas
    used = _load_used_identifiers()
    available = [r for r in results if r.identifier not in used]

    if not available:
        # Todas las canciones de esta búsqueda ya fueron usadas — resetear para este artista
        print(f"[public_domain] Todas las canciones ya usadas para '{artist_hint}', reiniciando historial...")
        available = results

    # Shuffle para variar dentro del artista (mantener prioritized primero pero con variedad)
    if len(available) > 1:
        # Shuffle los prioritized entre sí, y los others entre sí
        artist_lower = artist_hint.lower() if artist_hint else ""
        prioritized_avail = [r for r in available if artist_lower and artist_lower in r.creator.lower()]
        others_avail = [r for r in available if r not in prioritized_avail]
        random.shuffle(prioritized_avail)
        random.shuffle(others_avail)
        available = prioritized_avail + others_avail

    # Intentar con cada resultado hasta encontrar uno con audio
    for result in available:
        audio_files = get_audio_files(result.identifier)
        best = _pick_best_audio(audio_files)
        if best:
            try:
                audio_path = download_audio(result.identifier, best["name"], dest_dir)
                _save_used_identifier(result.identifier)
                source_url = f"https://archive.org/details/{result.identifier}"
                print(f"[public_domain] Track listo: {result.title} - {result.creator}")
                return DownloadedTrack(
                    audio_path=audio_path,
                    title=result.title,
                    artist=result.creator,
                    source_url=source_url,
                    identifier=result.identifier,
                )
            except Exception as e:
                print(f"[public_domain] Error descargando {result.identifier}: {e}")
                continue

    print("[public_domain] No se encontro audio descargable")
    return None
