from __future__ import annotations

import os
import re
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from .config import settings, logger
from .anime_naming import (
    extract_episode_number as extract_anime_episode_number,
    is_language_tag,
    normalize_title_key,
    strip_language_suffix,
)

SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"}
TEXT_SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt"}
AUDIO_EXTS = {".mka", ".aac", ".flac", ".opus", ".ac3", ".eac3", ".dts"}
VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".ts", ".m2ts", ".mts", ".rmvb", ".rm", ".mpg", ".mpeg", ".ogv",
}
SUBTITLE_DIR_NAMES = ("Subs", "subs", "Subtitles", "subtitles", "Subtitle", "subtitle", "字幕")
FONT_EXTS = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}
CJK_FONT_RE = re.compile(
    r"(source\s*han|noto\s*sans\s*cjk|noto\s*serif\s*cjk|noto.*cjk|"
    r"wenquanyi|wqy|pingfang|hiragino|yu\s*gothic|meiryo|"
    r"simhei|simsun|yahei|microsoft\s*yahei|songti|heiti|"
    r"思源|宋体|黑体|微软雅黑|蘋方|苹方|ヒラギノ|游ゴシック|メイリオ)",
    re.I,
)
SYSTEM_FONT_PRIORITY = [
    "SourceHanSansCN-Bold.woff2",
    "SourceHanSansCN-Regular.woff2",
    "NotoSansCJK-Regular.ttc",
    "NotoSansCJK-Bold.ttc",
    "NotoSerifCJK-Regular.ttc",
    "NotoSerifCJK-Bold.ttc",
    "wqy-microhei.ttc",
]

ENCODING_GUESS = [
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "gb18030",
    "gbk",
    "big5",
    "shift_jis",
    "euc-jp",
    "cp949",
    "latin-1",
]
SUBTITLE_CONTENT_TYPES = {
    ".ass": "text/plain",
    ".ssa": "text/plain",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
}
EXTERNAL_SUB_CACHE_TTL = 5.0
_external_sub_cache: dict[str, tuple[float, list[dict]]] = {}
_external_audio_cache: dict[str, tuple[float, list[dict]]] = {}


def _detect_encoding(file_path: str) -> str:
    # Deterministic CJK fallbacks are more reliable for short subtitle files than
    # charset-normalizer, which can misread GBK/GB18030 as Big5.
    for enc in ENCODING_GUESS:
        try:
            with open(file_path, "r", encoding=enc, errors="strict") as f:
                f.read(8192)
            return enc
        except (UnicodeError, LookupError):
            continue
    try:
        from charset_normalizer import from_path
        best = from_path(file_path).best()
        if best and best.encoding:
            return best.encoding
    except Exception:
        pass
    logger.warning(f"Subtitle encoding detection failed for {file_path}, using utf-8 with replacement")
    return "utf-8"


def get_fonts_dir() -> Path:
    d = Path(settings.data_dir) / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_fonts() -> list[dict]:
    fonts_dir = get_fonts_dir()
    fonts = []
    default_path = get_default_subtitle_font_path()
    for f in fonts_dir.iterdir():
        if f.suffix.lower() in FONT_EXTS:
            fonts.append({
                "name": f.name,
                "size": f.stat().st_size,
                "family": _read_font_family(str(f)),
                "source": "uploaded",
                "default": default_path == f,
            })
    for f in _system_cjk_fonts():
        fonts.append({
            "name": f"system/{f.name}",
            "size": f.stat().st_size,
            "family": _read_font_family(str(f)),
            "source": "system",
            "default": default_path == f,
        })
    return fonts


def _font_rank(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    for index, preferred in enumerate(SYSTEM_FONT_PRIORITY):
        if name == preferred.lower():
            return index, name
    if "notosanscjk" in name and "regular" in name:
        return 20, name
    if "sourcehansans" in name:
        return 30, name
    if "wqy" in name or "wenquanyi" in name:
        return 40, name
    if "pingfang" in name or "hiragino" in name or "meiryo" in name:
        return 50, name
    if "notoserifcjk" in name:
        return 60, name
    return 100, name


@lru_cache(maxsize=1)
def _system_cjk_fonts() -> list[Path]:
    roots = [
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/share/fonts/truetype/noto"),
        Path("/usr/share/fonts/truetype/wqy"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
    ]
    result = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for f in root.rglob("*"):
                if f.is_file() and f.suffix.lower() in FONT_EXTS and CJK_FONT_RE.search(f.name):
                    result.append(f)
        except OSError:
            continue
    return sorted(result, key=_font_rank)[:32]


def get_default_subtitle_font_path() -> Path | None:
    fonts_dir = get_fonts_dir()
    uploaded = []
    for f in fonts_dir.iterdir():
        if f.suffix.lower() not in FONT_EXTS:
            continue
        family = _read_font_family(str(f))
        if CJK_FONT_RE.search(f.name) or CJK_FONT_RE.search(family):
            uploaded.append(f)
    if uploaded:
        return sorted(uploaded, key=_font_rank)[0]
    system_fonts = _system_cjk_fonts()
    return system_fonts[0] if system_fonts else None


def resolve_font_path(name: str) -> Path:
    if name.startswith("system/"):
        basename = Path(name).name
        for f in _system_cjk_fonts():
            if f.name == basename:
                return f
        return Path("")
    return get_fonts_dir() / Path(name).name


def _font_family_from_ttfont(font) -> str | None:
    name_records = font["name"].names
    for name_id in (16, 1):
        for record in name_records:
            if record.nameID == name_id:
                try:
                    value = record.toUnicode()
                except Exception:
                    continue
                if value:
                    return value
    return None


def _read_font_family(file_path: str) -> str:
    try:
        from fontTools.ttLib import TTCollection, TTFont
        if Path(file_path).suffix.lower() == ".ttc":
            collection = TTCollection(file_path)
            families = []
            for font in collection.fonts:
                family = _font_family_from_ttfont(font)
                if family:
                    families.append(family)
            for marker in ("SC", "CN", "GB", "TC", "HK", "JP", "KR"):
                for family in families:
                    if re.search(rf"(\b|CJK\s*){marker}(\b|$)", family, re.I):
                        return family
            if families:
                return families[0]
        else:
            font = TTFont(file_path)
            family = _font_family_from_ttfont(font)
            if family:
                return family
    except ImportError:
        pass
    except Exception as exc:
        logger.debug(f"Unable to read font family from {file_path}: {exc}")
    return Path(file_path).stem


def install_font(file_path: str) -> dict:
    fonts_dir = get_fonts_dir()
    name = Path(file_path).name
    dest = fonts_dir / name
    with open(file_path, "rb") as src:
        with open(dest, "wb") as dst:
            dst.write(src.read())
    return {"name": name, "family": _read_font_family(str(dest))}


def remove_font(name: str) -> bool:
    fonts_dir = get_fonts_dir()
    target = fonts_dir / name
    if target.exists():
        target.unlink()
        return True
    return False


def get_subtitle_tracks(file_path: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", file_path],
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
    now = time.monotonic()
    cached = _external_sub_cache.get(file_path)
    if cached and now - cached[0] <= EXTERNAL_SUB_CACHE_TTL:
        # Return a shallow copy to avoid external mutation of cached objects.
        return [dict(item) for item in cached[1]]

    video_path = Path(file_path)
    folder = video_path.parent
    stem = video_path.stem
    if not folder.exists():
        return []
    video_episode = _extract_episode_number(stem)
    video_series = _series_key(stem)
    single_video_folder = _count_video_files(folder) <= 1
    all_subs = _collect_external_subtitle_files(folder)
    scored: list[tuple[int, Path]] = []
    for f in all_subs:
        score = _subtitle_match_score(stem, video_episode, video_series, f)
        sub_episode = _extract_episode_number(f.stem)
        episode_compatible = sub_episode is None or video_episode is None or sub_episode == video_episode
        if score <= 0 and episode_compatible and _is_openlist_related_subtitle(video_path, f, single_video_folder):
            score = 35
        if score > 0:
            scored.append((score, f))

    if not scored and len(all_subs) == 1:
        scored.append((10, all_subs[0]))

    subs = []
    seen = set()
    for _, f in sorted(scored, key=lambda item: (-item[0], item[1].name.lower())):
        if str(f) in seen:
            continue
        seen.add(str(f))
        fmt = f.suffix.lower().lstrip(".")
        language = _guess_lang(f)
        subs.append({
            "path": str(f),
            "name": f.name,
            "source": "external",
            "language": language,
            "codec": fmt,
            "format": fmt,
            "title": f.stem,
            "is_external": True,
            "web_supported": f.suffix.lower() in TEXT_SUBTITLE_EXTS,
        })
        logger.info(
            f"Matched external subtitle: video='{video_path.name}' path='{f}' "
            f"format={fmt} language={language}"
        )
    logger.info(
        f"Subtitle scan: video='{video_path.name}' candidates={len(all_subs)} matched={len(subs)}"
    )
    _external_sub_cache[file_path] = (now, [dict(item) for item in subs])
    if len(_external_sub_cache) > 256:
        # Avoid unbounded growth on long-running instances.
        oldest = min(_external_sub_cache.items(), key=lambda item: item[1][0])[0]
        _external_sub_cache.pop(oldest, None)
    return subs


def find_external_audio_tracks(file_path: str) -> list[dict]:
    now = time.monotonic()
    cached = _external_audio_cache.get(file_path)
    if cached and now - cached[0] <= EXTERNAL_SUB_CACHE_TTL:
        return [dict(item) for item in cached[1]]

    video_path = Path(file_path)
    folder = video_path.parent
    stem = video_path.stem
    if not folder.exists():
        return []
    video_episode = _extract_episode_number(stem)
    video_series = _series_key(stem)
    single_video_folder = _count_video_files(folder) <= 1
    all_audio = _collect_external_audio_files(folder)
    scored: list[tuple[int, Path]] = []
    for f in all_audio:
        score = _related_file_match_score(stem, video_episode, video_series, f)
        if score <= 0 and single_video_folder and f.parent == folder and _extract_episode_number(f.stem) is None:
            score = 20
        if score > 0:
            scored.append((score, f))

    tracks = []
    seen = set()
    for _, f in sorted(scored, key=lambda item: (-item[0], item[1].name.lower())):
        if str(f) in seen:
            continue
        seen.add(str(f))
        fmt = f.suffix.lower().lstrip(".")
        tracks.append({
            "path": str(f),
            "name": f.name,
            "source": "external",
            "language": _guess_lang(f),
            "codec": fmt,
            "format": fmt,
            "title": f.stem,
            "is_external": True,
        })
    logger.info(
        f"External audio scan: video='{video_path.name}' candidates={len(all_audio)} matched={len(tracks)}"
    )
    _external_audio_cache[file_path] = (now, [dict(item) for item in tracks])
    if len(_external_audio_cache) > 256:
        oldest = min(_external_audio_cache.items(), key=lambda item: item[1][0])[0]
        _external_audio_cache.pop(oldest, None)
    return tracks


def _collect_external_subtitle_files(folder: Path) -> list[Path]:
    candidates: list[Path] = []
    scan_dirs: list[Path] = []
    scan_seen = set()

    def add_scan_dir(path: Path) -> None:
        key = _path_identity(path)
        if key not in scan_seen:
            scan_seen.add(key)
            scan_dirs.append(path)

    add_scan_dir(folder)
    for base in (folder, folder.parent):
        for name in SUBTITLE_DIR_NAMES:
            p = base / name
            if p.is_dir():
                add_scan_dir(p)
                nested_by_folder = p / folder.name
                if nested_by_folder.is_dir():
                    add_scan_dir(nested_by_folder)
    for d in scan_dirs:
        try:
            entries = list(d.iterdir())
            candidates.extend(
                p for p in entries
                if p.is_file() and p.suffix.lower() in SUBTITLE_EXTS
            )
            for p in entries:
                if p.is_dir():
                    candidates.extend(
                        s for s in p.iterdir()
                        if s.is_file() and s.suffix.lower() in SUBTITLE_EXTS
                    )
        except OSError:
            continue
    return sorted(_unique_paths(candidates), key=lambda p: (p.parent.name.lower(), p.name.lower()))


def _collect_external_audio_files(folder: Path) -> list[Path]:
    candidates: list[Path] = []
    scan_dirs: list[Path] = []
    scan_seen = set()

    def add_scan_dir(path: Path) -> None:
        key = _path_identity(path)
        if key not in scan_seen:
            scan_seen.add(key)
            scan_dirs.append(path)

    add_scan_dir(folder)
    for base in (folder, folder.parent):
        for name in SUBTITLE_DIR_NAMES:
            p = base / name
            if p.is_dir():
                add_scan_dir(p)
                nested_by_folder = p / folder.name
                if nested_by_folder.is_dir():
                    add_scan_dir(nested_by_folder)
    for d in scan_dirs:
        try:
            candidates.extend(
                p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() in AUDIO_EXTS
            )
        except OSError:
            continue
    return sorted(_unique_paths(candidates), key=lambda p: (p.parent.name.lower(), p.name.lower()))


def _path_identity(path: Path) -> tuple[int, int] | str:
    try:
        stat = path.stat()
        return (stat.st_dev, stat.st_ino)
    except OSError:
        return str(path).casefold()


def _unique_paths(paths: list[Path]) -> list[Path]:
    result: list[Path] = []
    seen = set()
    for path in paths:
        key = _path_identity(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _count_video_files(folder: Path) -> int:
    try:
        return sum(1 for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    except OSError:
        return 0


def _is_subtitle_dir(path: Path) -> bool:
    return path.name in SUBTITLE_DIR_NAMES


def _is_openlist_related_subtitle(video_path: Path, subtitle_path: Path, single_video_folder: bool) -> bool:
    """Mirror OpenList's related-file feel for single-video folders without polluting season folders."""
    ext = subtitle_path.suffix.lower()
    if ext not in TEXT_SUBTITLE_EXTS:
        return False
    parent = subtitle_path.parent
    video_folder = video_path.parent
    if single_video_folder:
        if parent == video_folder:
            return True
        if _is_subtitle_dir(parent) and parent.parent in {video_folder, video_folder.parent}:
            return True
        if _is_subtitle_dir(parent.parent) and parent.parent.parent in {video_folder, video_folder.parent}:
            return True
    parent_key = _normalize_name(parent.name)
    video_key = _normalize_name(video_path.stem)
    folder_key = _normalize_name(video_folder.name)
    return bool(parent_key and parent_key in {video_key, folder_key})


def _subtitle_match_score(video_stem: str, video_episode: int | None, video_series: str, subtitle_path: Path) -> int:
    return _related_file_match_score(video_stem, video_episode, video_series, subtitle_path)


def _related_file_match_score(video_stem: str, video_episode: int | None, video_series: str, related_path: Path) -> int:
    raw_related_stem = related_path.stem
    if raw_related_stem == video_stem:
        return 120
    if strip_language_suffix(raw_related_stem) == video_stem:
        return 116

    sub_stem = raw_related_stem
    sub_episode = _extract_episode_number(sub_stem)
    if video_episode is not None and sub_episode is not None and sub_episode != video_episode:
        return 0
    if video_episode is not None and sub_episode is None:
        return 0
    if video_episode is None and sub_episode is not None:
        return 0
    v = _normalize_name(video_stem)
    s = _normalize_name(sub_stem)
    if s == v:
        return 100
    if _strip_lang_suffix(s) == v:
        return 96
    if s.startswith(v + " "):
        return 90
    if s.startswith(v):
        return 80
    v_tokens = set(v.split())
    s_tokens = set(s.split())
    if v_tokens and len(v_tokens & s_tokens) >= max(1, min(3, len(v_tokens))):
        return 60 + min(20, len(v_tokens & s_tokens) * 4)
    sub_series = _series_key(sub_stem)
    if video_episode is not None and sub_episode == video_episode:
        if video_series and sub_series and (video_series in sub_series or sub_series in video_series):
            return 88
        return 72
    return 0


def _strip_lang_suffix(name: str) -> str:
    tokens = name.split()
    while tokens and (tokens[-1] in {
        "chi", "cn", "gb", "big5", "english", "japanese", "简体", "繁体", "中文",
    } or is_language_tag(tokens[-1])):
        tokens.pop()
    return " ".join(tokens)


def _normalize_name(name: str) -> str:
    name = strip_language_suffix(name)
    name = re.sub(r'\[[^\]]*\]|\([^\)]*\)', ' ', name.lower())
    name = re.sub(r'[\._\-]+', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def _series_key(name: str) -> str:
    key = normalize_title_key(name)
    if key:
        return key
    clean = re.sub(r'\[[^\]]*\]|\([^\)]*\)', ' ', name)
    clean = re.sub(r'(?i)\b(?:S\d{1,2}E\d{1,3}|EP(?:ISODE)?\s*\.?\s*\d{1,3}|E\d{1,3})\b', ' ', clean)
    clean = re.sub(r'第\s*\d{1,3}\s*[集話话]', ' ', clean)
    clean = re.sub(r'\b\d{3,4}p\b|\b(?:x264|x265|h264|h265|hevc|avc|aac|flac|web-dl|bdrip|bluray)\b', ' ', clean, flags=re.I)
    clean = re.sub(r'[\[\(\s._-]\d{1,3}[\]\)\s._-]', ' ', clean)
    return _normalize_name(clean)


def _extract_episode_number(name: str) -> int | None:
    anime_episode = extract_anime_episode_number(name)
    if anime_episode is not None:
        return anime_episode
    patterns = [
        r'\[(\d{1,3})\](?=\[[^\]]+\])',
        r'(?i)\bS\d{1,2}E(\d{1,3})\b',
        r'(?i)\bEP(?:ISODE)?\s*\.?\s*(\d{1,3})\b',
        r'(?i)\bE(\d{1,3})\b',
        r'第\s*(\d{1,3})\s*[集話话]',
        r'[\[\(\s._-](\d{1,3})[\]\)\s._-]',
    ]
    for pattern in patterns:
        m = re.search(pattern, name)
        if m:
            try:
                num = int(m.group(1))
                if 0 < num < 1000:
                    return num
            except ValueError:
                pass
    return None


def _guess_lang(filepath: Path) -> str:
    name = filepath.stem.lower()
    normalized = re.sub(r'[\._]+', ' ', name)
    parts = set(re.split(r'[\s._-]+', name))
    if re.search(r'(?<![a-z0-9])zh[-_ ]?(?:cn|hans|sg)(?![a-z0-9])', normalized) or parts & {"chs", "sc", "hans", "gb", "简体"}:
        return "zh-cn"
    if re.search(r'(?<![a-z0-9])zh[-_ ]?(?:tw|hant|hk)(?![a-z0-9])', normalized) or parts & {"cht", "tc", "hant", "big5", "繁", "繁体"}:
        return "zh-tw"
    if parts & {"chi", "zh", "cn", "中文", "chinese"}:
        return "zh"
    if parts & {"jpn", "jp", "ja", "japanese", "日"}:
        return "jpn"
    if parts & {"kor", "ko", "kr", "korean", "韩"}:
        return "kor"
    if parts & {"eng", "en", "english", "英"}:
        return "eng"
    return "und"


def extract_subtitle_stream(file_path: str, stream_index: int) -> str | None:
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", file_path,
             "-map", f"0:{stream_index}",
             "-c:s", "webvtt",
             "-f", "webvtt",
             "-"],
            capture_output=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            vtt = result.stdout.decode("utf-8", errors="replace")
            vtt = _post_process_vtt(vtt)
            return vtt
    except Exception as e:
        logger.warning(f"Subtitle extraction failed for {file_path} stream {stream_index}: {e}")
    return None


def extract_subtitle_stream_raw(file_path: str, stream_index: int, codec: str = "") -> tuple[str | None, str]:
    codec_l = (codec or "").lower()
    if codec_l in {"ass", "ssa"}:
        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", file_path,
                 "-map", f"0:{stream_index}",
                 "-c:s", "copy",
                 "-f", codec_l,
                 "-"],
                capture_output=True, timeout=30
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.decode("utf-8", errors="replace"), "text/plain"
            if result.returncode != 0:
                logger.warning(
                    f"ASS subtitle extraction failed for {file_path} stream {stream_index}: "
                    f"ffmpeg exit={result.returncode} stderr={result.stderr.decode('utf-8', errors='replace')[:500]}"
                )
        except Exception as e:
            logger.warning(f"ASS subtitle extraction failed for {file_path} stream {stream_index}: {e}")
    return extract_subtitle_stream(file_path, stream_index), "text/vtt"


def convert_external_to_webvtt(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    if ext == ".vtt":
        enc = _detect_encoding(file_path)
        try:
            text = Path(file_path).read_text(encoding=enc, errors="replace")
            logger.info(f"Subtitle read encoding: path='{file_path}' encoding={enc} format=vtt")
            return _ensure_webvtt(text)
        except Exception as e:
            logger.warning(f"Read VTT subtitle failed for {file_path}: {e}")
            return None

    if ext == ".srt":
        raw = get_subtitle_content(file_path)
        if raw:
            return _srt_to_webvtt(raw)
        return None

    enc = _detect_encoding(file_path)
    try:
        args = ["ffmpeg", "-y"]
        if ext == ".sub":
            args.extend(["-sub_charenc", enc])
        args.extend([
             "-i", file_path,
             "-c:s", "webvtt",
             "-f", "webvtt",
             "-"
        ])
        result = subprocess.run(
            args,
            capture_output=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            vtt = result.stdout.decode("utf-8", errors="replace")
            vtt = _post_process_vtt(vtt)
            logger.info(f"Subtitle read encoding: path='{file_path}' encoding={enc} format={ext.lstrip('.')} converted=vtt")
            return vtt
        logger.warning(
            f"External subtitle conversion failed for {file_path}: "
            f"ffmpeg exit={result.returncode} stderr={result.stderr.decode('utf-8', errors='replace')[:500]}"
        )
    except Exception as e:
        logger.warning(f"External subtitle conversion failed for {file_path}: {e}")
    return None


def load_external_subtitle(file_path: str) -> tuple[str | None, str]:
    ext = Path(file_path).suffix.lower()
    if ext in {".ass", ".ssa"}:
        return get_subtitle_content(file_path), SUBTITLE_CONTENT_TYPES[ext]
    if ext == ".vtt":
        content = get_subtitle_content(file_path)
        return (_ensure_webvtt(content) if content else None), SUBTITLE_CONTENT_TYPES[ext]
    return convert_external_to_webvtt(file_path), "text/vtt"


def get_subtitle_content(file_path: str) -> str | None:
    if not Path(file_path).exists():
        logger.warning(f"Read subtitle failed for {file_path}: file does not exist")
        return None
    enc = _detect_encoding(file_path)
    try:
        text = Path(file_path).read_text(encoding=enc, errors="replace")
        logger.info(
            f"Subtitle read encoding: path='{file_path}' encoding={enc} "
            f"format={Path(file_path).suffix.lower().lstrip('.')}"
        )
        if "\ufffd" in text:
            logger.warning(f"Subtitle decoded with replacement characters: {file_path} ({enc})")
        return text
    except Exception as e:
        logger.warning(f"Read subtitle failed for {file_path}: {e}")
        return None


def _post_process_vtt(vtt: str) -> str:
    return _ensure_webvtt(_normalize_ass_styles_in_text(vtt))


def _ensure_webvtt(text: str) -> str:
    cleaned = text.lstrip("\ufeff")
    if cleaned.startswith("WEBVTT"):
        return cleaned
    return "WEBVTT\n\n" + cleaned


def _srt_to_webvtt(text: str) -> str:
    vtt = text.lstrip("\ufeff")
    vtt = re.sub(r'(?m)^(\d{2}:\d{2}:\d{2}),(\d{1,3})', lambda m: f"{m.group(1)}.{m.group(2).ljust(3, '0')[:3]}", vtt)
    vtt = re.sub(r'(?m)(-->\s*\d{2}:\d{2}:\d{2}),(\d{1,3})', lambda m: f"{m.group(1)}.{m.group(2).ljust(3, '0')[:3]}", vtt)
    return _ensure_webvtt(_normalize_ass_styles_in_text(vtt))


def _normalize_ass_styles_in_text(text: str) -> str:
    text = re.sub(r'\{\\[^}]*\}', '', text)
    text = re.sub(r'<font[^>]*>', '', text)
    text = text.replace('</font>', '')
    return text


def _normalize_ass_styles(text: str) -> str:
    return _normalize_ass_styles_in_text(text)
