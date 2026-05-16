import os
import subprocess
from pathlib import Path
from .config import settings, logger

SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"}


def get_subtitle_tracks(file_path: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path],
            capture_output=True, text=True, timeout=15
        )
        import json
        data = json.loads(result.stdout)
        tracks = []
        for i, stream in enumerate(data.get("streams", [])):
            if stream.get("codec_type") == "subtitle":
                tags = stream.get("tags", {})
                tracks.append({
                    "index": i,
                    "stream_index": stream.get("index", 0),
                    "codec": stream.get("codec_name", "unknown"),
                    "language": tags.get("language", "und"),
                    "title": tags.get("title", tags.get("language", "")),
                })
        return tracks
    except Exception as e:
        logger.warning(f"ffprobe subtitle detection failed for {file_path}: {e}")
        return []


def find_external_subtitles(file_path: str) -> list[dict]:
    folder = Path(file_path).parent
    stem = Path(file_path).stem
    if not folder.exists():
        return []
    subs = []
    for ext in SUBTITLE_EXTS:
        exact = folder / f"{stem}{ext}"
        if exact.exists():
            subs.append({"path": str(exact), "name": f"{stem}{ext}", "source": "external", "language": _guess_lang(exact)})
    for ext in SUBTITLE_EXTS:
        for f in sorted(folder.glob(f"*{ext}")):
            if not any(s["path"] == str(f) for s in subs):
                subs.append({"path": str(f), "name": f.name, "source": "external", "language": _guess_lang(f)})
    return subs


def _guess_lang(filepath: Path) -> str:
    name = filepath.stem.lower()
    if any(k in name for k in ("chs", "sc", "简", "cn", "zh-hans", "chi")):
        return "chi"
    if any(k in name for k in ("cht", "tc", "繁", "tw", "zh-hant")):
        return "chi"
    if any(k in name for k in ("eng", "en", "english", "英")):
        return "eng"
    if any(k in name for k in ("jpn", "jp", "ja", "日", "japanese")):
        return "jpn"
    return "und"


def extract_subtitle_stream(file_path: str, stream_index: int) -> str | None:
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", file_path, "-map", f"0:s:{stream_index}", "-f", "webvtt", "-"],
            capture_output=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Subtitle extraction failed for {file_path} stream {stream_index}: {e}")
    return None


def convert_external_to_webvtt(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    if ext == ".vtt":
        try:
            return Path(file_path).read_text(encoding="utf-8")
        except Exception:
            return None
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", file_path, "-f", "webvtt", "-"],
            capture_output=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"External subtitle conversion failed for {file_path}: {e}")
    return None
