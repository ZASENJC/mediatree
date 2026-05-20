import re
import os
import json
import hashlib
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET
from datetime import datetime
from .config import settings
from .anime_naming import parse_anime_filename

CODE_PATTERN = re.compile(r"(?i)([A-Z]{1,})-?(\d{2,6})")
CODE_PATTERN_UNDERSCORE = re.compile(r"(?i)([A-Z]{1,})_(\d{2,6})")
TMDB_TYPED_PATTERN = re.compile(
    r"(?i)\btmdb(?:id)?[\s:=._-]*(movie|tv|m|t)[\s:=._-]+(\d{1,10})\b"
)
TMDB_ID_PATTERN = re.compile(r"(?i)\btmdb(?:id)?[\s:=._-]+(\d{1,10})\b")
TMDB_BRACKET_PATTERN = re.compile(
    r"(?i)[\[\(\{]\s*[^]\)\}]*\btmdb(?:id)?[\s:=._-]+(?:movie|tv|m|t)?[\s:=._-]*\d{1,10}\b[^]\)\}]*[\]\)\}]"
)
EPISODE_HINT_PATTERN = re.compile(
    r"(?i)(?:\bS\d{1,2}E\d{1,3}\b|\bS\d{1,2}\s*[-_. ]?\s*E\d{1,3}\b|\b\d{1,2}x\d{1,3}\b|"
    r"\bEP(?:ISODE)?\s*\.?\s*\d{1,3}\b|\bE\d{1,3}\b|第\s*\d{1,3}\s*[集話话]|"
    r"\[\s*\d{1,3}\s*\](?=\[[^\]]+\]))"
)
SEASON_HINT_PATTERN = re.compile(r"(?i)(?:\bSeason\s*0?\d{1,2}\b|\bS\d{1,2}\b|第\s*\d{1,2}\s*季)")
DISC_HINT_PATTERN = re.compile(r"(?i)\b(?:CD|DVD|Disc|Disk|Part|Pt)\s*0?\d{1,2}\b")
YEAR_HINT_PATTERN = re.compile(r"[\(\[](?:19|20)\d{2}[\)\]]")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".webm", ".mpg", ".mpeg"}
COVER_NAMES = {"poster.jpg", "poster.png", "cover.jpg", "cover.png", "folder.jpg", "folder.png",
               "movie-poster.jpg", "movie-poster.png", "season-poster.jpg", "season-poster.png",
               "banner.jpg", "banner.png", "fanart.jpg", "fanart.png", "backdrop.jpg", "backdrop.png"}
NFO_NAMES = {"movie.nfo", "tvshow.nfo"}
SKIP_DIRS = {".DS_Store", "__MACOSX", "Thumbs.db", ".Trashes"}
SEASON_PATTERN = re.compile(r'^(S|Season\s*|第)\s*\d{1,2}$', re.I)

_scan_progress: dict[str, dict] = {}
_scan_locks: dict[str, asyncio.Lock] = {}
_scan_pending: set[str] = set()


@dataclass(frozen=True)
class TmdbIdToken:
    id: int
    media_type: Literal["movie", "tv"] | None
    raw: str
    source_name: str
    confidence: Literal["explicit", "unknown"]

def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")

def extract_code(name: str) -> str | None:
    match = CODE_PATTERN.search(name)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    match = CODE_PATTERN_UNDERSCORE.search(name)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    return None

def _normalize_tmdb_media_type(value: str | None) -> Literal["movie", "tv"] | None:
    value = (value or "").lower()
    if value in {"movie", "m"}:
        return "movie"
    if value in {"tv", "t"}:
        return "tv"
    return None


def extract_tmdb_token_from_name(name: str, source_name: str = "") -> TmdbIdToken | None:
    text = name or ""
    matches: list[tuple[int, int, re.Match, Literal["explicit", "unknown"]]] = []
    for match in TMDB_TYPED_PATTERN.finditer(text):
        matches.append((match.start(), 0, match, "explicit"))
    for match in TMDB_ID_PATTERN.finditer(text):
        if any(start <= match.start() < m.end() for start, _, m, _ in matches):
            continue
        matches.append((match.start(), 1, match, "unknown"))
    if len(matches) > 1:
        from .config import logger
        logger.warning(f"Multiple TMDB ID tokens found in '{text}', using the first")
    if not matches:
        return None
    _, _, match, confidence = sorted(matches, key=lambda item: (item[0], item[1]))[0]
    if confidence == "explicit":
        media_type = _normalize_tmdb_media_type(match.group(1))
        tmdb_id = match.group(2)
    else:
        media_type = None
        tmdb_id = match.group(1)
    try:
        value = int(tmdb_id)
    except (TypeError, ValueError):
        return None
    return TmdbIdToken(
        id=value,
        media_type=media_type,
        raw=match.group(0),
        source_name=source_name or text,
        confidence=confidence,
    )


def extract_tmdb_ref(name: str) -> tuple[str, str | None] | None:
    token = extract_tmdb_token_from_name(name or "")
    if not token:
        return None
    return str(token.id), token.media_type

def extract_tmdb_id_from_name(name: str) -> int | None:
    token = extract_tmdb_token_from_name(name or "")
    if not token:
        return None
    return token.id

def remove_tmdb_id_token(name: str) -> str:
    clean = TMDB_BRACKET_PATTERN.sub(" ", name or "")
    clean = TMDB_TYPED_PATTERN.sub(" ", clean)
    clean = TMDB_ID_PATTERN.sub(" ", clean)
    clean = re.sub(r"[\[\(\{]\s*[\]\)\}]", " ", clean)
    clean = re.sub(r"\s*[-_]\s*$", " ", clean)
    clean = re.sub(r"^\s*[-_]\s*", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" -_[](){}")
    return clean.strip()

def find_media_files(folder: Path) -> list[Path]:
    files = []
    for ext in VIDEO_EXTS:
        files.extend(folder.glob(f"*{ext}"))
        files.extend(folder.glob(f"*{ext.upper()}"))
    return sorted(set(files))

def find_cover(folder: Path) -> str | None:
    for name in COVER_NAMES:
        p = folder / name
        if p.exists():
            return str(p)
    for f in sorted(folder.glob("*.jpg")):
        return str(f)
    for f in sorted(folder.glob("*.png")):
        return str(f)
    return None

def find_cover_recursive(folder: Path, media_root: str) -> str | None:
    current = folder
    root = Path(media_root)
    while current >= root:
        cover = find_cover(current)
        if cover:
            return cover
        if current == root:
            break
        current = current.parent
    return None

def find_nfo_file(folder: Path) -> str | None:
    for name in NFO_NAMES:
        p = folder / name
        if p.exists():
            return str(p)
    for f in sorted(folder.glob("*.nfo")):
        return str(f)
    return None

def parse_nfo(filepath: str) -> dict:
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except Exception:
        return {}
    result = {"nfo_type": (root.tag or "").lower()}
    def _text(tag: str) -> str | None:
        el = root.find(tag)
        return el.text.strip() if el is not None and el.text else None
    title = _text("title")
    if title: result["title"] = title
    original_title = _text("originaltitle")
    if original_title: result["original_title"] = original_title
    plot = _text("plot")
    if plot: result["plot"] = plot
    year = _text("year")
    if year:
        try: result["year"] = int(year)
        except ValueError: pass
    premiered = _text("premiered") or _text("release_date")
    if premiered:
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", premiered)
        if date_match: result["premiered"] = date_match.group()
    rating = _text("rating")
    if rating:
        try: result["rating"] = float(rating)
        except ValueError: pass
    runtime = _text("runtime")
    if runtime:
        try: result["runtime"] = int(runtime)
        except ValueError: pass
    genres = [g.text.strip() for g in root.findall("genre") if g.text]
    if genres: result["genre"] = ", ".join(genres)
    actors = []
    for actor_el in root.findall("actor"):
        name_el = actor_el.find("name")
        if name_el is not None and name_el.text:
            actors.append(name_el.text.strip())
    if actors: result["actors"] = actors
    director = _text("director")
    if director: result["director"] = director
    studio = _text("studio")
    if studio: result["studio"] = studio
    return result

def extract_year_from_name(name: str) -> int | None:
    match = re.search(r'[\(\[](\d{4})[\)\]]', name)
    if match: return int(match.group(1))
    match = re.search(r'(?:^|[._\-\s])(\d{4})(?:[._\-\s]|$)', name.replace('1080p', '').replace('2160p', '').replace('720p', ''))
    if match:
        year = int(match.group(1))
        if 1888 <= year <= 2030: return year
    return None

def build_local_metadata(folder: Path, folder_name: str, code: str) -> dict:
    metadata: dict = {}
    nfo_path = find_nfo_file(folder)
    if nfo_path:
        nfo_data = parse_nfo(nfo_path)
        if nfo_data: metadata["nfo"] = nfo_data
    year = extract_year_from_name(folder_name)
    if year: metadata["detected_year"] = year
    return metadata

def generate_folder_identifier(folder_name: str) -> str:
    folder_name = remove_tmdb_id_token(folder_name)
    clean = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]', '', folder_name)
    clean = re.sub(r'\d{3,4}p', '', clean)
    clean = re.sub(r'[._\-]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean or folder_name.strip()

def generate_keyword_queries(name: str) -> list[str]:
    name = remove_tmdb_id_token(name)
    clean = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]', '', name)
    clean = re.sub(r'\d{3,4}p', '', clean, flags=re.I)
    clean = re.sub(r'(?i)\b(bluray|bdrip|webrip|web-dl|brrip|dvdrip|hdtv|hdcam|x264|x265|hevc|h264|avc|av1)\b', '', clean)
    clean = clean.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    clean = re.sub(r'[._\-\[\]{}()!！?？：:．,、\'\"\u300c\u300d\u300e\u300f\u3010\u3011\u2019\u2018\u201c\u201d]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    if not clean or clean == name: return []
    return [clean]

def clean_folder_name(name: str) -> str:
    name = remove_tmdb_id_token(name)
    name = re.sub(r'\(?\d{4}\)?', '', name)
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\{.*?\}', '', name)
    name = re.sub(r'\d{3,4}p', '', name, flags=re.I)
    name = re.sub(r'(?i)\b(bluray|bdrip|webrip|web-dl|brrip|dvdrip|hdtv|hdcam|x264|x265|hevc|h264|avc|av1)\b', '', name)
    name = name.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    name = re.sub(r'[._\-!！?？：:．,、\'\"\u300c\u300d\u300e\u300f\u3010\u3011\u2019\u2018\u201c\u201d]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name

def extract_cjk(text: str) -> str:
    return ''.join(c for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')

def extract_alpha(text: str) -> str:
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    return ''.join(c for c in text if c.isascii() and (c.isalpha() or c in "' ")).strip().lower()

def extract_romaji(text: str) -> str:
    t = text.replace('\u2019', "'").replace('\u2018', "'")
    return ' '.join(w.lower() for w in re.findall(r"[a-zA-Z'']{2,}", t))

def title_matches(scraped_title: str, folder_name: str, code: str | None = None) -> bool:
    if not scraped_title: return False

    s_clean = clean_folder_name(scraped_title)
    f_clean = clean_folder_name(folder_name)
    if not s_clean or not f_clean: return False

    if s_clean == f_clean: return True
    if len(s_clean) >= 4 and len(f_clean) >= 4:
        if s_clean in f_clean or f_clean in s_clean: return True

    s_cjk = extract_cjk(scraped_title)
    f_cjk = extract_cjk(folder_name)
    if s_cjk and f_cjk and len(s_cjk) >= 2 and len(f_cjk) >= 2:
        if s_cjk == f_cjk or s_cjk in f_cjk or f_cjk in s_cjk: return True

    s_romaji = extract_romaji(scraped_title)
    f_romaji = extract_romaji(folder_name)
    if s_romaji and f_romaji and len(s_romaji) >= 3 and len(f_romaji) >= 3:
        if s_romaji == f_romaji or s_romaji in f_romaji or f_romaji in s_romaji: return True

    s_alpha = extract_alpha(scraped_title)
    f_alpha = extract_alpha(folder_name)
    if s_alpha and f_alpha and len(s_alpha) >= 4 and len(f_alpha) >= 4:
        if s_alpha == f_alpha or s_alpha in f_alpha or f_alpha in s_alpha: return True

    if code:
        if code.upper() in scraped_title.upper(): return True
    return False


def _local_metadata(movie: dict) -> dict:
    raw = movie.get("local_metadata") if movie else None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _count_video_files_in_dir(path: str) -> tuple[int, bool]:
    try:
        folder = Path(path).parent
        files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    except OSError:
        return 0, False
    names = " ".join(p.stem for p in files)
    has_episode_pattern = bool(EPISODE_HINT_PATTERN.search(names))
    return len(files), has_episode_pattern


def infer_tmdb_media_type(movie: dict, candidate_names: list[str]) -> tuple[Literal["movie", "tv"] | None, dict]:
    movie = movie or {}
    names = [n for n in candidate_names if n]
    path = str(movie.get("path") or "")
    folder_levels = str(movie.get("folder_levels") or "")
    haystack = " / ".join([path, folder_levels, *names])
    movie_score = 0
    tv_score = 0
    reasons: list[str] = []

    if EPISODE_HINT_PATTERN.search(haystack):
        tv_score += 5
        reasons.append("episode_pattern:+5tv")
    if SEASON_HINT_PATTERN.search(haystack):
        tv_score += 4
        reasons.append("season_pattern:+4tv")

    if movie.get("tmdb_type") == "tv":
        tv_score += 5
        reasons.append("existing_tmdb_type_tv:+5tv")
    elif movie.get("tmdb_type") == "movie":
        movie_score += 5
        reasons.append("existing_tmdb_type_movie:+5movie")

    if movie.get("tmdb_season") is not None or movie.get("tmdb_episode") is not None:
        tv_score += 5
        reasons.append("existing_tmdb_episode:+5tv")

    local_meta = _local_metadata(movie)
    nfo_type = str((local_meta.get("nfo") or {}).get("nfo_type") or local_meta.get("nfo_type") or "").lower()
    if nfo_type in {"tvshow", "episodedetails", "episode"}:
        tv_score += 5
        reasons.append(f"nfo_{nfo_type}:+5tv")
    elif nfo_type == "movie":
        movie_score += 5
        reasons.append("nfo_movie:+5movie")

    file_count = 0
    has_episode_pattern = False
    if path:
        file_count, has_episode_pattern = _count_video_files_in_dir(path)
        if file_count > 1 and has_episode_pattern:
            tv_score += 4
            reasons.append("multi_episode_dir:+4tv")
        elif file_count == 1 and not EPISODE_HINT_PATTERN.search(haystack) and not SEASON_HINT_PATTERN.search(haystack):
            movie_score += 2
            reasons.append("single_video_no_episode:+2movie")
        elif file_count > 1 and DISC_HINT_PATTERN.search(haystack) and not has_episode_pattern:
            movie_score += 3
            reasons.append("disc_part_multi_file:+3movie")

    if YEAR_HINT_PATTERN.search(haystack) and not EPISODE_HINT_PATTERN.search(haystack):
        movie_score += 2
        reasons.append("year_no_episode:+2movie")
    if not EPISODE_HINT_PATTERN.search(haystack) and not SEASON_HINT_PATTERN.search(haystack):
        movie_score += 2
        reasons.append("no_season_episode_structure:+2movie")

    inferred: Literal["movie", "tv"] | None
    if tv_score >= movie_score + 2:
        inferred = "tv"
    elif movie_score >= tv_score + 2:
        inferred = "movie"
    else:
        inferred = None
    debug = {
        "movie_score": movie_score,
        "tv_score": tv_score,
        "reasons": reasons,
        "file_count": file_count,
        "inferred": inferred,
    }
    return inferred, debug

def scan_media(root: str = None) -> list[dict]:
    from .covers import find_local_episode_still
    from .subtitles import find_external_audio_tracks

    if root is None:
        roots = settings.get_all_media_roots()
    else:
        roots = [root]
    results = []
    for media_root in roots:
        base = Path(media_root)
        if not base.exists(): continue
        trigger = _scan_progress.get(media_root, {}).get("trigger")
        _scan_progress[media_root] = {"status": "scanning", "done": 0, "total": 0, "trigger": trigger}
        for dirpath, dirnames, filenames in os.walk(base):
            folder = Path(dirpath)
            media_files = find_media_files(folder)
            if not media_files: continue
            detected_code = extract_code(folder.name)
            code = detected_code
            if not code and filenames:
                for f in filenames:
                    code = extract_code(Path(f).stem)
                    if code:
                        detected_code = code
                        break
            if not code:
                code = generate_folder_identifier(folder.name)
            rel_path = str(folder.relative_to(base))
            folder_levels = rel_path.replace("\\", "/")
            cover_local = find_cover_recursive(folder, media_root)
            try:
                folder_mtime = os.path.getmtime(str(folder))
            except OSError:
                folder_mtime = None
            local_meta = build_local_metadata(folder, folder.name, code)
            nfo_data = local_meta.get("nfo", {})
            title = nfo_data.get("title") or None
            release_date = nfo_data.get("premiered") or None
            duration = nfo_data.get("runtime") or None
            for mf in media_files:
                anime_info = parse_anime_filename(mf.name)
                clean_title = anime_info.clean_title or title or ""
                item_code = code
                if not detected_code and clean_title:
                    item_code = clean_title
                local_still = find_local_episode_still(str(mf))
                external_audio_tracks = find_external_audio_tracks(str(mf))
                item_meta = dict(local_meta)
                item_meta["anime_naming"] = anime_info.as_dict()
                item_meta_json = json.dumps(item_meta, ensure_ascii=False) if item_meta else "{}"
                item = {
                    "path": str(mf), "code": item_code, "title": title or clean_title or None,
                    "folder_levels": folder_levels, "cover_local": cover_local,
                    "media_root": media_root, "local_metadata": item_meta_json,
                    "clean_title": clean_title or None,
                    "episode_number": anime_info.episode,
                    "display_title": anime_info.display_title or clean_title or None,
                    "external_audio_tracks": json.dumps(external_audio_tracks, ensure_ascii=False),
                }
                if anime_info.episode is not None:
                    item["tmdb_type"] = "tv"
                    item["tmdb_season"] = 1
                    item["tmdb_episode"] = anime_info.episode
                if local_still:
                    item["episode_still"] = local_still
                    item["episode_still_local"] = local_still
                if release_date: item["release_date"] = release_date
                if duration: item["duration"] = duration
                if folder_mtime:
                    item["created_at"] = datetime.fromtimestamp(folder_mtime).strftime("%Y-%m-%d %H:%M:%S")
                results.append(item)
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        _scan_progress[media_root] = {"status": "scanned", "done": 0, "total": 0, "trigger": trigger}
    return results

def normalize_scraper_name(scraper: str | None) -> str:
    value = (scraper or "auto").strip().lower()
    if value == "tmdb":
        return "tmdb_movie"
    if value in {"tmdb_movie", "tmdb_tv", "bangumi", "javdatabase", "auto", "none"}:
        return value
    return "auto"


def build_fallback_chain(preferred: str) -> list[str]:
    preferred = normalize_scraper_name(preferred)
    if preferred == "none":
        return []
    if preferred == "javdatabase":
        return ["javdatabase"]
    if preferred == "auto":
        return ["auto"]
    if preferred == "tmdb_movie":
        return ["tmdb_movie"]
    if preferred == "tmdb_tv":
        return ["tmdb_tv"]
    if preferred == "bangumi":
        return ["bangumi", "tmdb_tv_search"]
    return ["auto"]

async def try_scrape_javdb(code: str) -> dict | None:
    from .javdb import search_javdb
    data = await search_javdb(code)
    if data and data.get("title"):
        cast = [
            {"name": name.strip(), "role": "", "source": "javdb"}
            for name in re.split(r"[,，、/]", data.get("actress", "") or "")
            if name.strip()
        ]
        crew = []
        if data.get("director"):
            crew.append({"name": data["director"], "job": "Director", "source": "javdb"})
        if data.get("studio"):
            crew.append({"name": data["studio"], "job": "Studio", "source": "javdb"})
        return {
            "source": "javdatabase", "title": data.get("title", ""),
            "actress": data.get("actress", ""), "release_date": data.get("release_date", ""),
            "duration": data.get("duration"), "cover_remote": data.get("cover_remote", ""),
            "javdb_url": data.get("javdb_url", ""), "javdb_score": data.get("javdb_score"),
            "javdb_likes": data.get("javdb_likes"), "javdb_thumbnails": data.get("javdb_thumbnails", ""),
            "cast": cast, "crew": crew,
        }
    return None

def _tmdb_scrape_data(detail: dict, source_id: str, media_type: str, exact: bool = False) -> dict:
    return {
        "source": "tmdb", "title": detail.get("title", ""),
        "release_date": detail.get("release_date", ""),
        "duration": detail.get("runtime") or detail.get("duration", 0),
        "cover_remote": detail.get("poster_url", ""),
        "backdrop_url": detail.get("backdrop_url", ""),
        "javdb_score": detail.get("score"), "javdb_likes": detail.get("votes"),
        "tmdb_id": int(source_id), "tmdb_type": media_type,
        "seasons": detail.get("seasons", []), "cast": detail.get("cast", []),
        "crew": detail.get("crew", []), "imdb_id": detail.get("imdb_id"),
        "_exact_match": exact,
    }

def _first_tmdb_token(candidate_names: list[str], default_label: str = "candidate") -> TmdbIdToken | None:
    for idx, candidate in enumerate(candidate_names):
        label = ["folder", "parent", "filename", "title", "code", "search"][idx] if idx < 6 else default_label
        token = extract_tmdb_token_from_name(candidate or "", label)
        if token:
            return token
    return None


async def try_scrape_tmdb_title(
    folder_name: str,
    code: str,
    media_type: Literal["movie", "tv"] | None = None,
) -> dict | None:
    from .tmdb import search_tmdb, fetch_tmdb_detail
    from .config import logger
    if not settings.tmdb_api_key and not settings.tmdb_access_token:
        logger.warning(f"TMDB credentials not configured, skipping for '{folder_name}'")
        return None
    clean_name = remove_tmdb_id_token(folder_name)
    queries = [clean_name, clean_folder_name(clean_name), generate_folder_identifier(clean_name)]
    queries.extend(generate_keyword_queries(folder_name))
    best = None
    for query in queries:
        if not query: continue
        results = await search_tmdb(query, media_type=media_type)
        if results:
            for candidate in results[:3]:
                if title_matches(candidate.get("title", ""), clean_name, code):
                    best = candidate
                    break
            if best: break
    if not best:
        scope = f" {media_type}" if media_type else ""
        logger.info(f"  TMDB{scope}: no match for '{folder_name}'")
        return None
    detail = await fetch_tmdb_detail(best["source_id"], best["media_type"])
    if not detail: return None
    data = _tmdb_scrape_data(detail, best["source_id"], best["media_type"])
    if not data.get("title"):
        data["title"] = best.get("title", "")
    return data


async def try_scrape_tmdb_typed(
    search_name: str,
    code: str,
    media_type: Literal["movie", "tv"],
    candidate_names: list[str] | None = None,
) -> dict | None:
    from .tmdb import fetch_tmdb_by_id
    from .config import logger
    candidates = candidate_names or [search_name, code]
    token = _first_tmdb_token(candidates)
    scraper_name = "tmdb_movie" if media_type == "movie" else "tmdb_tv"
    clean_title = remove_tmdb_id_token(search_name)

    if token:
        logger.info(
            f"  {scraper_name}: detected tmdbid={token.id} from {token.source_name}; "
            f"using /{media_type}/{token.id}"
        )
        if settings.tmdb_api_key or settings.tmdb_access_token:
            detail = await fetch_tmdb_by_id(token.id, media_type)
            if detail and detail.get("title"):
                logger.info(f"  {scraper_name}: TMDB ID exact match success /{media_type}/{token.id}")
                return _tmdb_scrape_data(detail, str(token.id), media_type, exact=True)
            logger.warning("  TMDB ID 精确匹配失败，fallback 到标题搜索")
        else:
            logger.warning(f"  {scraper_name}: TMDB credentials not configured, fallback to title search")

    logger.info(f"  {scraper_name}: fallback to Bangumi title search for '{clean_title}'")
    data = await try_scrape_bangumi(clean_title, code)
    if data:
        return data

    logger.info(f"  {scraper_name}: fallback to TMDB {media_type} title search for '{clean_title}'")
    return await try_scrape_tmdb_title(clean_title, code, media_type)


async def try_scrape_tmdb_movie(
    search_name: str,
    code: str,
    candidate_names: list[str] | None = None,
    movie: dict | None = None,
) -> dict | None:
    return await try_scrape_tmdb_typed(search_name, code, "movie", candidate_names)


async def try_scrape_tmdb_tv(
    search_name: str,
    code: str,
    candidate_names: list[str] | None = None,
    movie: dict | None = None,
) -> dict | None:
    return await try_scrape_tmdb_typed(search_name, code, "tv", candidate_names)


async def try_scrape_tmdb(folder_name: str, code: str) -> dict | None:
    """Compatibility path for old internal callers: TMDB title search across movie and tv."""
    return await try_scrape_tmdb_title(folder_name, code)

async def resolve_tmdb_id_candidate(
    token: TmdbIdToken,
    movie: dict | None,
    candidate_names: list[str],
) -> dict | None:
    from .tmdb import fetch_tmdb_by_id, fetch_tmdb_candidates_by_id
    from .config import logger
    if token.media_type:
        logger.info(f"  TMDB ID explicit {token.media_type}: only requesting /{token.media_type}/{token.id}")
        return await fetch_tmdb_by_id(token.id, token.media_type)

    inferred, scores = infer_tmdb_media_type(movie or {}, candidate_names)
    movie_score = scores["movie_score"]
    tv_score = scores["tv_score"]
    logger.info(
        f"  TMDB ID local type scores for {token.id}: "
        f"movie={movie_score}, tv={tv_score}, inferred={inferred}, reasons={','.join(scores['reasons'][:6])}"
    )

    if tv_score >= movie_score + 4:
        logger.info(f"  TMDB ID strong local inference: tv; only requesting /tv/{token.id}")
        return await fetch_tmdb_by_id(token.id, "tv")
    if movie_score >= tv_score + 4:
        logger.info(f"  TMDB ID strong local inference: movie; only requesting /movie/{token.id}")
        return await fetch_tmdb_by_id(token.id, "movie")

    logger.info(f"  TMDB ID type unclear: concurrently requesting movie/tv candidates for {token.id}")
    candidates = await fetch_tmdb_candidates_by_id(token.id)
    movie_detail = candidates.get("movie")
    tv_detail = candidates.get("tv")
    if movie_detail and not tv_detail:
        if tv_score >= movie_score + 4:
            logger.warning(f"  TMDB ID movie exists but local score strongly suggests tv; rejecting movie/{token.id}")
            return None
        return movie_detail
    if tv_detail and not movie_detail:
        if movie_score >= tv_score + 4:
            logger.warning(f"  TMDB ID tv exists but local score strongly suggests movie; rejecting tv/{token.id}")
            return None
        return tv_detail
    if movie_detail and tv_detail:
        if tv_score >= movie_score + 2:
            return tv_detail
        if movie_score >= tv_score + 2:
            return movie_detail
        logger.warning(f"  TMDB ID {token.id} exists as both movie and tv but local scores are unclear; fallback to title search")
        return None
    return None


async def try_scrape_tmdb_id(
    tmdb_id: int,
    media_type: Literal["movie", "tv"] | None = None,
    movie: dict | None = None,
    candidate_names: list[str] | None = None,
) -> dict | None:
    from .config import logger
    token = TmdbIdToken(
        id=tmdb_id,
        media_type=media_type,
        raw=f"tmdbid={tmdb_id}",
        source_name="",
        confidence="explicit" if media_type else "unknown",
    )
    detail = await resolve_tmdb_id_candidate(token, movie or {}, candidate_names or [])
    if not detail or not detail.get("title"):
        logger.info(f"  TMDB ID exact match failed for tmdbid={tmdb_id}")
        return None
    resolved_type = detail.get("media_type") or media_type
    if resolved_type not in {"movie", "tv"}:
        logger.warning(f"  TMDB ID {tmdb_id} returned without safe media type")
        return None
    return _tmdb_scrape_data(detail, str(tmdb_id), resolved_type, exact=True)

async def try_scrape_bangumi(folder_name: str, code: str) -> dict | None:
    from .bangumi import search_bangumi, fetch_bangumi_detail
    from .config import logger
    folder_name = remove_tmdb_id_token(folder_name)
    queries = [folder_name, clean_folder_name(folder_name), generate_folder_identifier(folder_name)]
    queries.extend(generate_keyword_queries(folder_name))
    best = None
    for query in queries:
        if not query: continue
        results = await search_bangumi(query)
        if results:
            for candidate in results[:3]:
                if title_matches(candidate.get("title", ""), folder_name, code):
                    best = candidate
                    break
            if best: break
    if not best:
        logger.info(f"  Bangumi: no match for '{folder_name}'")
        return None
    detail = await fetch_bangumi_detail(best["source_id"])
    if not detail: return None
    return {
        "source": "bangumi", "title": detail.get("title", best.get("title", "")),
        "release_date": detail.get("release_date", ""),
        "cover_remote": detail.get("poster_url", ""),
        "javdb_score": detail.get("score"),
        "javdb_likes": detail.get("votes") or detail.get("collection_total"),
        "cast": detail.get("cast", []),
        "crew": detail.get("crew", []),
    }

async def try_scrape_auto(
    search_name: str,
    code: str,
    candidate_names: list[str] | None = None,
    movie: dict | None = None,
) -> dict | None:
    from .config import logger
    logger.info(f"  Auto scraper started for '{search_name}'")
    candidates = candidate_names or [search_name, code]
    token = None
    for idx, candidate in enumerate(candidates):
        label = ["folder", "parent", "filename", "title", "code", "search"][idx] if idx < 6 else "candidate"
        token = extract_tmdb_token_from_name(candidate or "", label)
        if token:
            break

    if token:
        logger.info(f"  Auto scraper detected tmdbid={token.id} from {token.source_name} ({token.raw})")
        logger.info(f"  Auto scraper using TMDB ID exact match: tmdbid={token.id}")
        data = await try_scrape_tmdb_id(token.id, media_type=token.media_type, movie=movie or {}, candidate_names=candidates)
        if data:
            logger.info(f"  Auto scraper TMDB ID success: tmdbid={token.id} type={data.get('tmdb_type')}")
            return data
        logger.warning("  TMDB ID 精确匹配失败，fallback 到标题搜索")

    clean_title = remove_tmdb_id_token(search_name)
    logger.info(f"  Auto scraper trying Bangumi for '{clean_title}'")
    data = await try_scrape_bangumi(clean_title, code)
    if data:
        return data
    logger.info(f"  Auto scraper Bangumi failed, trying TMDB title search for '{clean_title}'")
    data = await try_scrape_tmdb(clean_title, code)
    if data:
        return data
    logger.info(f"  Auto scraper failed all sources for '{clean_title}'")
    return None


async def try_scrape_tmdb_movie_search(search_name: str, code: str) -> dict | None:
    return await try_scrape_tmdb_title(search_name, code, "movie")


async def try_scrape_tmdb_tv_search(search_name: str, code: str) -> dict | None:
    return await try_scrape_tmdb_title(search_name, code, "tv")


FALLBACK_HANDLERS = {
    "javdatabase": try_scrape_javdb,
    "tmdb": try_scrape_tmdb_movie,
    "tmdb_movie": try_scrape_tmdb_movie,
    "tmdb_tv": try_scrape_tmdb_tv,
    "tmdb_movie_search": try_scrape_tmdb_movie_search,
    "tmdb_tv_search": try_scrape_tmdb_tv_search,
    "bangumi": try_scrape_bangumi,
    "auto": try_scrape_auto,
}

def has_local_data(movie_row: dict) -> bool:
    local_metadata = movie_row.get("local_metadata")
    has_metadata = bool(local_metadata and local_metadata != "{}")
    cover = movie_row.get("cover_local")
    has_cover = bool(cover and (len(str(cover)) <= 64 or Path(str(cover)).exists()))
    return has_metadata and has_cover

async def _apply_scraped_data(folder_levels: str, data: dict, media_root: str = "", replace: bool = False) -> int:
    from .database import get_db
    from .config import logger
    db = await get_db()
    fields = {
        "title": data.get("title") or "",
        "actress": data.get("actress") or "",
        "release_date": data.get("release_date") or "",
        "duration": data.get("duration"),
        "javdb_url": data.get("javdb_url") or "",
        "javdb_score": data.get("javdb_score"),
        "javdb_likes": data.get("javdb_likes"),
        "javdb_thumbnails": data.get("javdb_thumbnails") or "",
        "cover_remote": data.get("cover_remote") or "",
        "fanart_local": data.get("backdrop_url") or data.get("fanart_local") or "",
        "tmdb_id": data.get("tmdb_id"),
        "tmdb_type": data.get("tmdb_type") or "",
        "cast": json.dumps(data.get("cast") or [], ensure_ascii=False),
        "crew": json.dumps(data.get("crew") or [], ensure_ascii=False),
    }
    if replace:
        set_sql = """
               title=NULLIF(?, ''),
               actress=NULLIF(?, ''),
               release_date=NULLIF(?, ''),
               duration=?,
               javdb_url=NULLIF(?, ''),
               javdb_score=?,
               javdb_likes=?,
               javdb_thumbnails=NULLIF(?, ''),
               cover_remote=NULLIF(?, ''),
               fanart_local=NULLIF(?, ''),
               tmdb_id=?,
               tmdb_type=NULLIF(?, ''),
               "cast"=NULLIF(?, '[]'),
               crew=NULLIF(?, '[]'),
               tmdb_season=NULL,
               tmdb_episode=NULL,
               episode_title=NULL,
               episode_overview=NULL,
               episode_still=NULL,
               episode_still_local=NULL,
               updated_at=datetime('now')
        """
    else:
        set_sql = """
               title=COALESCE(NULLIF(?, ''), title),
               actress=COALESCE(NULLIF(?, ''), actress),
               release_date=COALESCE(NULLIF(?, ''), release_date),
               duration=COALESCE(?, duration),
               javdb_url=COALESCE(NULLIF(?, ''), javdb_url),
               javdb_score=COALESCE(?, javdb_score),
               javdb_likes=COALESCE(?, javdb_likes),
               javdb_thumbnails=COALESCE(NULLIF(?, ''), javdb_thumbnails),
               cover_remote=COALESCE(NULLIF(?, ''), cover_remote),
               fanart_local=COALESCE(NULLIF(?, ''), fanart_local),
               tmdb_id=COALESCE(?, tmdb_id),
               tmdb_type=COALESCE(NULLIF(?, ''), tmdb_type),
               "cast"=COALESCE(NULLIF(?, '[]'), "cast"),
               crew=COALESCE(NULLIF(?, '[]'), crew),
               updated_at=datetime('now')
        """
    values = (
        fields["title"], fields["actress"], fields["release_date"], fields["duration"],
        fields["javdb_url"], fields["javdb_score"], fields["javdb_likes"],
        fields["javdb_thumbnails"], fields["cover_remote"], fields["fanart_local"],
        fields["tmdb_id"], fields["tmdb_type"], fields["cast"], fields["crew"],
    )
    if media_root:
        cur = await db.execute(
            f"UPDATE movies SET {set_sql} WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=?",
            (*values, folder_levels, f"{folder_levels}/%", media_root)
        )
    else:
        cur = await db.execute(
            f"UPDATE movies SET {set_sql} WHERE (folder_levels=? OR folder_levels LIKE ?)",
            (*values, folder_levels, f"{folder_levels}/%")
        )
    affected = cur.rowcount
    logger.info(f"  _apply_scraped_data: folder='{folder_levels}' media_root='{media_root}' affected={affected} rows")

    folder_name = Path(folder_levels).name if folder_levels else ""
    if is_season_folder(folder_name) and data.get("cover_remote"):
        parent = str(Path(folder_levels).parent) if str(Path(folder_levels).parent) != "." else ""
        if parent:
            await db.execute(
                """UPDATE movies SET
                   cover_remote=COALESCE(NULLIF(?, ''), cover_remote),
                   updated_at=datetime('now')
                   WHERE folder_levels LIKE ?""",
                (data.get("cover_remote", ""), parent + "/%")
            )

    if data.get("cover_remote") or replace:
        if media_root:
            await db.execute(
                "UPDATE movies SET cover_local=NULL WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=?",
                (folder_levels, f"{folder_levels}/%", media_root),
            )
        else:
            await db.execute(
                "UPDATE movies SET cover_local=NULL WHERE (folder_levels=? OR folder_levels LIKE ?)",
                (folder_levels, f"{folder_levels}/%"),
            )
    if data.get("cover_remote"):
        try:
            from .covers import download_and_compress_cover
            cache_key = hashlib.md5(data["cover_remote"].encode()).hexdigest()[:16]
            cached = await download_and_compress_cover(data["cover_remote"], cache_key)
            if cached:
                if media_root:
                    await db.execute(
                        "UPDATE movies SET cover_local=? WHERE (folder_levels=? OR folder_levels LIKE ?) AND media_root=?",
                        (cache_key, folder_levels, f"{folder_levels}/%", media_root),
                    )
                else:
                    await db.execute(
                        "UPDATE movies SET cover_local=? WHERE (folder_levels=? OR folder_levels LIKE ?)",
                        (cache_key, folder_levels, f"{folder_levels}/%"),
                    )
        except Exception:
            pass

    await db.commit()
    return affected

def is_season_folder(name: str) -> bool:
    return bool(SEASON_PATTERN.match(name))


def infer_season_number(folder_name: str, data: dict) -> int | None:
    if is_season_folder(folder_name):
        match = re.search(r'\d+', folder_name)
        if match:
            return int(match.group())
    if data.get("tmdb_type") == "tv":
        seasons = data.get("seasons") or []
        numbered = [
            s.get("season_number") for s in seasons
            if isinstance(s, dict) and isinstance(s.get("season_number"), int) and s.get("season_number") > 0
        ]
        if len(numbered) == 1:
            return numbered[0]
        return 1
    return None

async def scrape_for_library(media_root: str):
    from .database import get_library_settings, get_db
    from .config import logger

    lib_setting = await get_library_settings(media_root)
    scraper = lib_setting.get("scraper", "auto") if lib_setting else "auto"
    trigger = _scan_progress.get(media_root, {}).get("trigger")
    if scraper == "none":
        logger.info(f"Scraping disabled for {media_root}")
        _scan_progress[media_root] = {"status": "disabled", "done": 0, "total": 0, "trigger": trigger}
        return

    chain = build_fallback_chain(scraper)
    logger.info(f"Scraping {media_root}: scraper={normalize_scraper_name(scraper)} chain={' → '.join(chain)}")

    db = await get_db()
    cur = await db.execute(
        """SELECT DISTINCT code, folder_levels, path, title, cover_local, local_metadata,
                  tmdb_type, tmdb_season, tmdb_episode, clean_title, episode_number, display_title
           FROM movies WHERE media_root=?""",
        (media_root,)
    )
    rows = await cur.fetchall()
    if not rows:
        _scan_progress[media_root] = {"status": "done", "done": 0, "total": 0, "trigger": trigger}
        return

    total_folders = len(set(r["folder_levels"] for r in rows if r["folder_levels"]))
    _scan_progress[media_root] = {"status": "scraping", "done": 0, "total": total_folders, "trigger": trigger}

    scraped_folders = set()
    done_count = 0
    for r in rows:
        folder_levels = r["folder_levels"] or ""
        folder_name = Path(folder_levels).name if folder_levels else ""
        code = r["code"] or ""
        movie_path = r["path"] or ""
        row_clean_title = (r["clean_title"] or "").strip()

        if not folder_name: continue
        if folder_levels in scraped_folders: continue

        if has_local_data(dict(r)):
            logger.info(f"  Skip (local data exists): {folder_name}")
            scraped_folders.add(folder_levels)
            done_count += 1
            _scan_progress[media_root] = {"status": "scraping", "done": done_count, "total": total_folders, "trigger": trigger}
            continue

        search_name = row_clean_title or folder_name
        search_levels = folder_levels
        if is_season_folder(folder_name):
            parent = Path(folder_levels).parent
            parent_name = parent.name if str(parent) != "." else ""
            if row_clean_title:
                search_name = row_clean_title
                search_levels = str(parent) if parent_name else folder_levels
            elif parent_name:
                search_name = parent_name
                search_levels = str(parent)

        if search_levels != folder_levels:
            logger.info(f"  Season folder detected: '{folder_name}' → searching as '{search_name}'")

        candidate_names = [
            row_clean_title,
            folder_name,
            Path(folder_levels).parent.name if folder_levels and str(Path(folder_levels).parent) != "." else "",
            Path(movie_path).stem if movie_path else "",
            r["title"] or "",
            r["display_title"] or "",
            code,
            search_name,
        ]

        scraped = False
        for sb in chain:
            handler = FALLBACK_HANDLERS.get(sb)
            if not handler: continue
            try:
                if sb == "javdatabase":
                    data = await handler(code)
                elif sb in {"auto", "tmdb_movie", "tmdb_tv", "tmdb"}:
                    data = await handler(search_name, code, candidate_names, dict(r))
                else:
                    data = await handler(search_name, code)
                if not data or not data.get("title"):
                    logger.info(f"  {sb}: no result for '{search_name}'")
                    continue
                if sb in {"javdatabase", "auto"} and data.get("_exact_match"):
                    passed = True
                elif sb == "javdatabase":
                    passed = True
                else:
                    passed = bool(data.get("_exact_match")) or title_matches(data.get("title", ""), search_name, code)
                if passed:
                    await _apply_scraped_data(folder_levels, data, media_root)
                    logger.info(f"  {sb}: {search_name} → {data.get('title', search_name)}")

                    if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                        season_num = infer_season_number(folder_name, data)
                        if season_num:
                            try:
                                from .tmdb import match_episodes_in_folder
                                matched = await match_episodes_in_folder(
                                    str(data["tmdb_id"]), season_num, folder_levels, media_root
                                )
                                if matched:
                                    logger.info(f"  TMDB: matched {matched} episodes in '{folder_levels}'")
                            except Exception as e:
                                logger.warning(f"  TMDB: episode matching error: {e}")

                    scraped = True
                    break
                else:
                    logger.info(f"  {sb}: title mismatch '{data.get('title', '')}' vs '{search_name}', trying fallback")
            except Exception as e:
                logger.warning(f"  {sb}: error for '{folder_name}': {e}")

        if not scraped:
            logger.info(f"  All scrapers failed for '{search_name}'")
        scraped_folders.add(folder_levels)
        done_count += 1
        _scan_progress[media_root] = {"status": "scraping", "done": done_count, "total": total_folders, "trigger": trigger}

    _scan_progress[media_root] = {"status": "done", "done": total_folders, "total": total_folders, "trigger": trigger}


def _scan_lock_for(media_root: str) -> asyncio.Lock:
    lock = _scan_locks.get(media_root)
    if lock is None:
        lock = asyncio.Lock()
        _scan_locks[media_root] = lock
    return lock


async def cleanup_deleted_files(media_root: str) -> int:
    from .database import get_db
    from .config import logger
    db = await get_db()
    cur = await db.execute("SELECT id, path FROM movies WHERE media_root=?", (media_root,))
    removed = 0
    for row in await cur.fetchall():
        if not Path(row["path"]).exists():
            await db.execute("DELETE FROM movies WHERE id=?", (row["id"],))
            removed += 1
    if removed:
        await db.commit()
        logger.info(f"Scan cleanup: removed {removed} deleted files from {media_root}")
    return removed


async def run_scan_for_root(media_root: str, trigger: str = "manual") -> dict:
    from .database import upsert_movie
    from .config import logger
    lock = _scan_lock_for(media_root)
    if lock.locked():
        _scan_pending.add(media_root)
        logger.info(f"Scan skipped/queued for {media_root}: another scan is already running")
        return {"media_root": media_root, "queued": True, "trigger": trigger}

    total_results = 0
    removed_total = 0
    runs = 0
    async with lock:
        while True:
            _scan_pending.discard(media_root)
            runs += 1
            _scan_progress[media_root] = {"status": "scanning", "done": 0, "total": 0, "trigger": trigger}
            logger.info(f"Scan started for {media_root} trigger={trigger}")
            results = await asyncio.to_thread(scan_media, root=media_root)
            for item in results:
                await upsert_movie(item)
            removed_total += await cleanup_deleted_files(media_root)
            total_results += len(results)
            _scan_progress[media_root] = {
                "status": "scraping",
                "done": 0,
                "total": 0,
                "trigger": trigger,
            }
            await scrape_for_library(media_root)
            logger.info(f"Scan and scrape complete for {media_root} trigger={trigger} files={len(results)}")
            if media_root not in _scan_pending:
                break
            logger.info(f"Queued changes detected during scan for {media_root}; running one follow-up scan")
            trigger = "queued"

    return {
        "media_root": media_root,
        "queued": False,
        "trigger": trigger,
        "runs": runs,
        "total": total_results,
        "removed": removed_total,
    }


async def clear_library_scraped_data(media_root: str):
    from .database import get_db
    from .config import logger
    import shutil

    db = await get_db()
    await db.execute(
        """UPDATE movies SET title=NULL, actress=NULL, release_date=NULL,
           duration=NULL, cover_remote=NULL, javdb_url=NULL, javdb_score=NULL,
           javdb_likes=NULL, javdb_thumbnails=NULL,
           tmdb_id=NULL, tmdb_type=NULL, tmdb_season=NULL, tmdb_episode=NULL,
           episode_title=NULL, episode_overview=NULL, episode_still=NULL,
           "cast"='[]', crew='[]',
           updated_at=datetime('now')
           WHERE media_root=? AND local_metadata='{}'""",
        (media_root,)
    )
    await db.execute(
        """UPDATE movies SET cover_remote=NULL, javdb_url=NULL, javdb_score=NULL,
           javdb_likes=NULL, javdb_thumbnails=NULL,
           tmdb_id=NULL, tmdb_type=NULL, tmdb_season=NULL, tmdb_episode=NULL,
           episode_title=NULL, episode_overview=NULL, episode_still=NULL,
           "cast"='[]', crew='[]',
           updated_at=datetime('now')
           WHERE media_root=? AND local_metadata!='{}'""",
        (media_root,)
    )
    await db.execute("DELETE FROM scraper_cache WHERE query LIKE ?", (f"%{media_root}%",))
    await db.execute("DELETE FROM javdb_cache WHERE code IN (SELECT code FROM movies WHERE media_root=?)", (media_root,))
    await db.commit()

    covers_dir = Path(settings.covers_dir)
    if covers_dir.exists():
        for f in covers_dir.glob("*.jpg"):
            try: f.unlink()
            except Exception: pass

    logger.info(f"Cleared all scraped data for {media_root}")


async def rescrape_movie(movie_id: int) -> dict:
    from .database import get_db
    from .config import logger

    db = await get_db()
    cur = await db.execute("SELECT * FROM movies WHERE id=?", (movie_id,))
    row = await cur.fetchone()
    if not row:
        return {"ok": False, "error": "Movie not found"}

    movie = dict(row)
    folder_levels = movie.get("folder_levels", "")
    folder_name = Path(folder_levels).name if folder_levels else ""
    code = movie.get("code", "")
    media_root = movie.get("media_root", "")

    if not folder_name:
        return {"ok": False, "error": "No folder name"}

    lib_setting = await get_library_settings(media_root)
    scraper = lib_setting.get("scraper", "auto") if lib_setting else "auto"
    if scraper == "none":
        return {"ok": False, "error": "Scraper not configured for this library"}

    chain = build_fallback_chain(scraper)

    row_clean_title = (movie.get("clean_title") or "").strip()
    search_name = row_clean_title or folder_name
    search_levels = folder_levels
    if is_season_folder(folder_name):
        parent = Path(folder_levels).parent
        parent_name = parent.name if str(parent) != "." else ""
        if row_clean_title:
            search_name = row_clean_title
            search_levels = str(parent) if parent_name else folder_levels
        elif parent_name:
            search_name = parent_name
            search_levels = str(parent)

    candidate_names = [
        row_clean_title,
        folder_name,
        Path(folder_levels).parent.name if folder_levels and str(Path(folder_levels).parent) != "." else "",
        Path(movie.get("path", "")).stem,
        movie.get("title") or "",
        movie.get("display_title") or "",
        code,
        search_name,
    ]

    for sb in chain:
        handler = FALLBACK_HANDLERS.get(sb)
        if not handler:
            continue
        try:
            if sb == "javdatabase":
                data = await handler(code)
            elif sb in {"auto", "tmdb_movie", "tmdb_tv", "tmdb"}:
                data = await handler(search_name, code, candidate_names, movie)
            else:
                data = await handler(search_name, code)
            if not data or not data.get("title"):
                continue
            if sb in {"javdatabase", "auto"} and data.get("_exact_match"):
                passed = True
            elif sb == "javdatabase":
                passed = True
            else:
                passed = bool(data.get("_exact_match")) or title_matches(data.get("title", ""), search_name, code)
            if passed:
                await _apply_scraped_data(folder_levels, data, media_root)
                if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                    season_num = infer_season_number(folder_name, data)
                    if season_num:
                        try:
                            from .tmdb import match_episodes_in_folder
                            await match_episodes_in_folder(
                                str(data["tmdb_id"]), season_num, folder_levels, media_root
                            )
                        except Exception:
                            pass
                return {"ok": True, "source": sb, "title": data.get("title", search_name)}
            else:
                logger.info(f"  rescrape: {sb} title mismatch")
        except Exception as e:
            logger.warning(f"  rescrape: {sb} error: {e}")

    return {"ok": False, "error": "All scrapers failed"}


async def rescrape_movie_manual(movie_id: int, query: str, preferred_scraper: str = None, source_id: str = None, media_type: str = "movie") -> dict:
    from .database import get_db
    from .config import logger

    db = await get_db()
    cur = await db.execute("SELECT * FROM movies WHERE id=?", (movie_id,))
    row = await cur.fetchone()
    if not row:
        return {"ok": False, "error": "Movie not found"}

    movie = dict(row)
    folder_levels = movie.get("folder_levels", "")
    code = movie.get("code", "")
    media_root = movie.get("media_root", "")

    preferred = normalize_scraper_name(preferred_scraper)

    if source_id and preferred_scraper:
        data = None
        if preferred in {"tmdb_movie", "tmdb_tv"}:
            from .tmdb import fetch_tmdb_detail
            forced_media_type = "tv" if preferred == "tmdb_tv" else "movie"
            detail = await fetch_tmdb_detail(source_id, forced_media_type)
            if detail:
                data = {
                    "source": "tmdb", "title": detail.get("title") or "",
                    "release_date": detail.get("release_date") or "",
                    "duration": detail.get("runtime") or detail.get("duration", 0),
                    "cover_remote": detail.get("poster_url") or "",
                    "backdrop_url": detail.get("backdrop_url") or "",
                    "tmdb_id": int(source_id), "tmdb_type": forced_media_type,
                    "cast": detail.get("cast", []), "crew": detail.get("crew", []),
                    "seasons": detail.get("seasons", []),
                    "imdb_id": detail.get("imdb_id") or "",
                }
        elif preferred_scraper == "bangumi":
            from .bangumi import fetch_bangumi_detail
            detail = await fetch_bangumi_detail(source_id)
            if detail:
                data = {
                    "source": "bangumi", "title": detail.get("title") or "",
                    "release_date": detail.get("release_date") or "",
                    "cover_remote": detail.get("poster_url") or "",
                }
        elif preferred_scraper == "javdatabase":
            data = await try_scrape_javdb(source_id)

        if data and data.get("title"):
            await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                folder_name = Path(folder_levels).name if folder_levels else ""
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        await match_episodes_in_folder(
                            str(data["tmdb_id"]), season_num, folder_levels, media_root
                        )
                    except Exception:
                        pass
            return {"ok": True, "source": preferred, "title": data.get("title", query)}
        else:
            return {"ok": False, "error": f"Failed to fetch detail from {preferred_scraper}"}

    if preferred_scraper and preferred in FALLBACK_HANDLERS:
        chain = [preferred]
    else:
        lib_setting = await get_library_settings(media_root)
        scraper = lib_setting.get("scraper", "auto") if lib_setting else "auto"
        chain = build_fallback_chain(scraper) if scraper != "none" else ["tmdb_movie", "bangumi"]

    for sb in chain:
        handler = FALLBACK_HANDLERS.get(sb)
        if not handler:
            continue
        try:
            if sb == "javdatabase":
                data = await handler(code)
            elif sb in {"auto", "tmdb_movie", "tmdb_tv", "tmdb"}:
                data = await handler(query, code, [query, movie.get("title") or "", code], movie)
            else:
                data = await handler(query, code)
            if not data or not data.get("title"):
                continue
            await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                folder_name = Path(folder_levels).name if folder_levels else ""
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        await match_episodes_in_folder(
                            str(data["tmdb_id"]), season_num, folder_levels, media_root
                        )
                    except Exception:
                        pass
            return {"ok": True, "source": sb, "title": data.get("title", query)}
        except Exception as e:
            logger.warning(f"  manual scrape: {sb} error: {e}")

    return {"ok": False, "error": "All scrapers failed"}


async def rescrape_folder(folder_levels: str, media_root: str) -> dict:
    from .database import get_db
    from .config import logger

    db = await get_db()
    if media_root:
        cur = await db.execute("SELECT id FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    else:
        cur = await db.execute("SELECT id FROM movies WHERE folder_levels=?", (folder_levels,))
    rows = await cur.fetchall()
    if not rows:
        return {"ok": False, "error": "No movies found in folder"}

    count = 0
    for row in rows:
        result = await rescrape_movie(row["id"])
        if result.get("ok"):
            count += 1

    logger.info(f"Folder rescrape: {count}/{len(rows)} movies updated in {folder_levels}")
    return {"ok": True, "rescraped": count, "total": len(rows)}


async def search_for_scrape(query: str, scraper: str = "tmdb") -> list[dict]:
    results = []
    scraper = normalize_scraper_name(scraper)
    if scraper in {"tmdb_movie", "tmdb_tv"}:
        from .tmdb import search_tmdb
        media_type = "tv" if scraper == "tmdb_tv" else "movie"
        items = await search_tmdb(query, media_type=media_type)
        for item in items[:10]:
            results.append({
                "source": "tmdb",
                "source_id": item.get("source_id", ""),
                "media_type": item.get("media_type", ""),
                "title": item.get("title", ""),
                "original_title": item.get("original_title", ""),
                "year": item.get("release_date", "")[:4] if item.get("release_date") else "",
                "poster_url": item.get("poster_url"),
                "overview": item.get("overview", ""),
            })
    elif scraper == "bangumi":
        from .bangumi import search_bangumi
        items = await search_bangumi(query)
        for item in items[:10]:
            results.append({
                "source": "bangumi",
                "source_id": item.get("source_id", ""),
                "media_type": "tv",
                "title": item.get("title", ""),
                "original_title": item.get("original_title", ""),
                "year": item.get("release_date", "")[:4] if item.get("release_date") else "",
                "poster_url": item.get("poster_url"),
                "overview": item.get("overview", ""),
            })
    elif scraper == "javdatabase":
        from .javdb import search_javdb
        data = await search_javdb(query)
        if data and data.get("title"):
            results.append({
                "source": "javdatabase",
                "source_id": query,
                "media_type": "movie",
                "title": data.get("title", ""),
                "original_title": "",
                "year": data.get("release_date", "")[:4] if data.get("release_date") else "",
                "poster_url": data.get("cover_remote"),
                "overview": "",
            })
    return results


async def fetch_search_backdrops(results: list[dict]) -> list[dict]:
    backdrops = []
    seen = set()
    for r in results:
        sid = r.get("source_id", "")
        src = r.get("source", "")
        mtype = r.get("media_type", "movie")
        key = f"{src}:{sid}"
        if not sid or key in seen:
            continue
        seen.add(key)
        backdrop = None
        detail = None
        if src == "tmdb":
            from .tmdb import fetch_tmdb_detail
            detail = await fetch_tmdb_detail(sid, mtype)
        elif src == "bangumi":
            from .bangumi import fetch_bangumi_detail
            detail = await fetch_bangumi_detail(sid)
        backdrop = detail.get("backdrop_url") if detail else None
        backdrops.append({"source_id": sid, "source": src, "backdrop_url": backdrop, "poster_url": r.get("poster_url")})
    return backdrops


async def change_folder_backdrop(folder_levels: str, media_root: str, fanart_url: str) -> dict:
    from .database import get_db
    from .config import logger
    if not fanart_url:
        return {"ok": False, "error": "No URL provided"}
    db = await get_db()
    if media_root:
        await db.execute("UPDATE movies SET fanart_local=?, updated_at=datetime('now') WHERE folder_levels=? AND media_root=?", (fanart_url, folder_levels, media_root))
    else:
        await db.execute("UPDATE movies SET fanart_local=?, updated_at=datetime('now') WHERE folder_levels=?", (fanart_url, folder_levels))
    await db.commit()
    logger.info(f"Backdrop changed for folder {folder_levels}")
    return {"ok": True}


async def rescrape_folder_manual(folder_levels: str, media_root: str, query: str, preferred_scraper: str = "") -> dict:
    from .database import get_db, get_library_settings
    from .config import logger

    db = await get_db()
    folder_name = Path(folder_levels).name if folder_levels else ""
    search_name = folder_name

    if is_season_folder(folder_name):
        parent = Path(folder_levels).parent
        parent_name = parent.name if str(parent) != "." else ""
        if parent_name:
            search_name = parent_name

    preferred = normalize_scraper_name(preferred_scraper)
    if preferred_scraper and preferred in FALLBACK_HANDLERS:
        chain = [preferred]
    else:
        lib_setting = await get_library_settings(media_root)
        scraper = lib_setting.get("scraper", "auto") if lib_setting else "auto"
        chain = build_fallback_chain(scraper) if scraper != "none" else ["tmdb_movie", "bangumi"]

    if media_root:
        cur = await db.execute("SELECT code FROM movies WHERE folder_levels=? AND media_root=? LIMIT 1", (folder_levels, media_root))
    else:
        cur = await db.execute("SELECT code FROM movies WHERE folder_levels=? LIMIT 1", (folder_levels,))
    row = await cur.fetchone()
    code = row["code"] if row else ""

    for sb in chain:
        handler = FALLBACK_HANDLERS.get(sb)
        if not handler:
            continue
        try:
            if sb == "javdatabase":
                data = await handler(code or query)
            elif sb in {"auto", "tmdb_movie", "tmdb_tv", "tmdb"}:
                data = await handler(query, code or query, [folder_name, search_name, query, code or ""], {})
            else:
                data = await handler(query, code or query)
            if not data or not data.get("title"):
                continue
            await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        await match_episodes_in_folder(str(data["tmdb_id"]), season_num, folder_levels, media_root)
                    except Exception:
                        pass
            return {"ok": True, "source": sb, "title": data.get("title", search_name)}
        except Exception as e:
            logger.warning(f"  folder manual scrape {sb}: {e}")
    return {"ok": False, "error": "All scrapers failed"}


async def apply_folder_scrape_result(folder_levels: str, media_root: str, source_id: str, source: str, media_type: str = "movie") -> dict:
    from .config import logger
    from pathlib import Path

    data = None
    if source == "tmdb":
        from .tmdb import fetch_tmdb_detail
        detail = await fetch_tmdb_detail(source_id, media_type)
        if detail:
            data = {
                "source": "tmdb", "title": detail.get("title") or "",
                "release_date": detail.get("release_date") or "",
                "duration": detail.get("runtime") or detail.get("duration", 0),
                "cover_remote": detail.get("poster_url") or "",
                "backdrop_url": detail.get("backdrop_url") or "",
                "tmdb_id": int(source_id), "tmdb_type": media_type,
                "cast": detail.get("cast", []), "crew": detail.get("crew", []),
                "seasons": detail.get("seasons", []),
                "imdb_id": detail.get("imdb_id") or "",
            }
    elif source == "bangumi":
        from .bangumi import fetch_bangumi_detail
        detail = await fetch_bangumi_detail(source_id)
        if detail:
            data = {
                "source": "bangumi", "title": detail.get("title") or "",
                "release_date": detail.get("release_date") or "",
                "cover_remote": detail.get("poster_url") or "",
            }
    elif source == "javdatabase":
        data = await try_scrape_javdb(source_id)

    if not data or not data.get("title"):
        return {"ok": False, "error": f"Failed to fetch detail from {source}"}

    folder_name = Path(folder_levels).name if folder_levels else ""
    affected = await _apply_scraped_data(folder_levels, data, media_root, replace=True)

    if source == "tmdb" and media_type == "tv" and data.get("tmdb_id"):
        season_num = infer_season_number(folder_name, data)
        if season_num:
            try:
                from .tmdb import match_episodes_in_folder
                await match_episodes_in_folder(str(data["tmdb_id"]), season_num, folder_levels, media_root)
            except Exception:
                pass

    logger.info(f"apply_folder_scrape: source={source} folder='{folder_levels}' media_root='{media_root}' affected={affected} rows title='{data.get('title')}'")
    return {"ok": True, "source": source, "title": data.get("title", ""), "affected": affected}


async def change_folder_cover(folder_levels: str, media_root: str, cover_url: str) -> dict:
    from .database import get_db
    from .config import logger
    import hashlib

    db = await get_db()
    try:
        from .covers import download_and_compress_cover
        cache_key = hashlib.md5(cover_url.encode()).hexdigest()[:16]
        await download_and_compress_cover(cover_url, cache_key)
        if media_root:
            await db.execute(
                "UPDATE movies SET cover_remote=?, cover_local=?, updated_at=datetime('now') WHERE folder_levels=? AND media_root=?",
                (cover_url, cache_key, folder_levels, media_root)
            )
        else:
            await db.execute(
                "UPDATE movies SET cover_remote=?, cover_local=?, updated_at=datetime('now') WHERE folder_levels=?",
                (cover_url, cache_key, folder_levels)
            )
        await db.commit()
        logger.info(f"Cover changed for folder {folder_levels}")
        return {"ok": True}
    except Exception as e:
        logger.warning(f"Change folder cover error: {e}")
        return {"ok": False, "error": str(e)}


async def edit_folder_movies(folder_levels: str, media_root: str, fields: dict) -> dict:
    from .database import get_db
    from .config import logger

    db = await get_db()
    sets = []
    values = []
    for f in ("title", "release_date", "duration"):
        if f in fields and fields[f]:
            sets.append(f"{f}=?")
            values.append(fields[f])
    if not sets:
        return {"ok": False, "error": "No fields to update"}
    sets.append("updated_at=datetime('now')")
    if media_root:
        values.extend([folder_levels, media_root])
        await db.execute(
            f"UPDATE movies SET {', '.join(sets)} WHERE folder_levels=? AND media_root=?",
            values
        )
    else:
        values.append(folder_levels)
        await db.execute(
            f"UPDATE movies SET {', '.join(sets)} WHERE folder_levels=?",
            values
        )
    await db.commit()
    logger.info(f"Edited {len(sets)-1} fields for folder {folder_levels}")
    return {"ok": True}


async def delete_folder_movies(folder_levels: str, media_root: str) -> dict:
    from .database import get_db
    from .config import logger

    db = await get_db()
    if media_root:
        cur = await db.execute("SELECT id FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    else:
        cur = await db.execute("SELECT id FROM movies WHERE folder_levels=?", (folder_levels,))
    rows = await cur.fetchall()
    count = len(rows)
    for r in rows:
        await db.execute("DELETE FROM tags WHERE movie_id=?", (r["id"],))
    if media_root:
        await db.execute("DELETE FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    else:
        await db.execute("DELETE FROM movies WHERE folder_levels=?", (folder_levels,))
    await db.commit()
    logger.info(f"Deleted {count} movies from folder {folder_levels}")
    return {"ok": True, "deleted": count}
