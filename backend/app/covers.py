import os
import hashlib
from pathlib import Path
import httpx
from .config import settings, logger


async def download_and_compress_cover(url: str, cache_key: str, max_width: int = 500, quality: int = 80) -> str | None:
    cached_path = Path(settings.covers_dir) / f"{cache_key}.jpg"
    if cached_path.exists():
        return str(cached_path)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.content

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
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            raw = resp.content

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
