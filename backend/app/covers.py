import os
import hashlib
import subprocess
from pathlib import Path
from .config import settings, logger, fetch_safe_image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
EPISODE_IMAGE_MARKERS = ("cover", "still", "thumb")


async def download_and_compress_cover(url: str, cache_key: str, max_width: int = 500, quality: int = 80) -> str | None:
    cached_path = Path(settings.covers_dir) / f"{cache_key}.jpg"
    if cached_path.exists():
        return str(cached_path)

    try:
        fetched = await fetch_safe_image(url, timeout=30)
        if not fetched:
            return None
        raw, _ = fetched

        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(raw))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            w, h = img.size
            if w > max_width:
                ratio = max_width / w
                new_h = int(h * ratio)
                img = img.resize((max_width, new_h), Image.LANCZOS)
            img.save(str(cached_path), "JPEG", quality=quality, optimize=True)
            logger.info(f"Cover cached: {cache_key} ({os.path.getsize(str(cached_path))} bytes)")
            return str(cached_path)
        except ImportError:
            with open(cached_path, "wb") as f:
                f.write(raw)
            logger.warning("Pillow not installed, cover saved raw")
            return str(cached_path)
    except Exception as e:
        logger.warning(f"Cover download failed for {url}: {e}")
        return None


async def download_and_cache_still(url: str, cache_key: str, max_width: int = 300, quality: int = 75) -> str | None:
    stills_dir = Path(settings.data_dir) / "stills"
    stills_dir.mkdir(parents=True, exist_ok=True)
    cached_path = stills_dir / f"{cache_key}.jpg"
    if cached_path.exists():
        return str(cached_path)

    try:
        fetched = await fetch_safe_image(url, timeout=30)
        if not fetched:
            return None
        raw, _ = fetched

        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(raw))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            w, h = img.size
            if w > max_width:
                ratio = max_width / w
                new_h = int(h * ratio)
                img = img.resize((max_width, new_h), Image.LANCZOS)
            img.save(str(cached_path), "JPEG", quality=quality, optimize=True)
            logger.info(f"Still cached: {cache_key} ({os.path.getsize(str(cached_path))} bytes)")
            return str(cached_path)
        except ImportError:
            with open(cached_path, "wb") as f:
                f.write(raw)
            logger.warning("Pillow not installed, still saved raw")
            return str(cached_path)
    except Exception as e:
        logger.warning(f"Still download failed for {url}: {e}")
        return None


def find_local_episode_still(video_path: str) -> str | None:
    path = Path(video_path)
    folder = path.parent
    stem = path.stem
    if not folder.exists():
        return None

    candidates: list[Path] = []
    for ext in IMAGE_EXTS:
        candidates.append(folder / f"{stem}{ext}")
    for marker in EPISODE_IMAGE_MARKERS:
        for ext in IMAGE_EXTS:
            candidates.append(folder / f"{stem}.{marker}{ext}")

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


def generate_video_still(video_path: str, cache_key: str | None = None, at_seconds: float = 30.0) -> str | None:
    path = Path(video_path)
    if not path.exists():
        return None
    stills_dir = Path(settings.data_dir) / "stills"
    stills_dir.mkdir(parents=True, exist_ok=True)
    try:
        stat = path.stat()
        raw_key = cache_key or f"{path}:{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        raw_key = cache_key or str(path)
    key = hashlib.md5(raw_key.encode()).hexdigest()[:16]
    out_path = stills_dir / f"{key}.jpg"
    if out_path.exists():
        return str(out_path)
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{max(0.0, at_seconds):.3f}", "-i", str(path),
                "-frames:v", "1", "-vf", "scale='min(480,iw)':-2",
                str(out_path),
            ],
            capture_output=True, timeout=20
        )
        if result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return str(out_path)
        try:
            out_path.unlink()
        except OSError:
            pass
    except Exception as e:
        logger.debug(f"Generate video still failed for {video_path}: {e}")
    return None
