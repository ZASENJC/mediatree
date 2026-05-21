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
from .scrapers.base import ScrapeCandidate, ScrapeResult, ScrapeStaff
from .scrapers.registry import get_scraper

CODE_PATTERN = re.compile(r"(?i)([A-Z]{1,})-?(\d{2,6})")
CODE_PATTERN_UNDERSCORE = re.compile(r"(?i)([A-Z]{1,})_(\d{2,6})")
TMDB_TYPED_PATTERN = re.compile(
    r"(?i)\btmdb(?:id)?[\s:=._-]*(movie|tv|m|t)[\s:=._-]+(\d{1,10})\b"
)
TMDB_ID_PATTERN = re.compile(r"(?i)\btmdb(?:id)?[\s:=._-]+(\d{1,10})\b")
TMDB_BRACKET_PATTERN = re.compile(
    r"(?i)[\[\(\{]\s*[^]\)\}]*\btmdb(?:id)?[\s:=._-]+(?:movie|tv|m|t)?[\s:=._-]*\d{1,10}\b[^]\)\}]*[\]\)\}]"
)
TMDB_MALFORMED_PATTERN = re.compile(r"(?i)\btmdb(?:id)?[\s:=._-]*(?:movie|tv|m|t)?[\s:=._-]*(?=$|[\s\]\)\}\-_])")
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
_global_scrape_semaphore: asyncio.Semaphore | None = None
_global_scrape_limit = 0
_sqlite_write_semaphore = asyncio.Semaphore(1)


def _bounded_int(value, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def _get_global_scrape_semaphore() -> asyncio.Semaphore:
    global _global_scrape_semaphore, _global_scrape_limit
    limit = _bounded_int(settings.scrape_global_concurrency, 8)
    if _global_scrape_semaphore is None or _global_scrape_limit != limit:
        _global_scrape_semaphore = asyncio.Semaphore(limit)
        _global_scrape_limit = limit
    return _global_scrape_semaphore


def _set_scan_progress(media_root: str, **fields):
    current = dict(_scan_progress.get(media_root, {}))
    current.update(fields)
    current.setdefault("media_root", media_root)
    current.setdefault("done", 0)
    current.setdefault("total", 0)
    current.setdefault("success", 0)
    current.setdefault("failed", 0)
    current.setdefault("skipped", 0)
    current.setdefault("active_concurrency", 0)
    current.setdefault("trigger", current.get("trigger"))
    _scan_progress[media_root] = current


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

LEADING_BRACKET_GROUP_PATTERN = re.compile(r"^\[[A-Za-z0-9\-_. ]{2,30}\]\s*")

def remove_tmdb_id_token(name: str) -> str:
    # 先去开发布组标签 [GROUP] 如 [Snow-Raws]、[VCB-Studio]、[ANi]
    clean = LEADING_BRACKET_GROUP_PATTERN.sub(" ", name or "")
    clean = TMDB_BRACKET_PATTERN.sub(" ", clean)
    clean = TMDB_TYPED_PATTERN.sub(" ", clean)
    clean = TMDB_ID_PATTERN.sub(" ", clean)
    clean = TMDB_MALFORMED_PATTERN.sub(" ", clean)
    clean = re.sub(r"[\[\(\{]\s*[\]\)\}]", " ", clean)
    clean = re.sub(r"\s*[-_]\s*$", " ", clean)
    clean = re.sub(r"^\s*[-_]\s*", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" -_[](){}")
    return clean.strip()

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

RELEASE_GROUP_TOKENS = {
    "lolihouse", "vcb", "vcb-studio", "tone", "tone-studio", "喵萌", "桜都", "动漫国",
}
MEDIA_NOISE_PATTERN = re.compile(
    r"(?ix)\b(?:"
    r"bluray|blu-ray|bdrip|webrip|web-dl|webdl|brrip|dvdrip|hdtv|hdcam|"
    r"x264|x265|hevc|h264|avc|av1|ma10p|hi10p|10bit|8bit|12bit|"
    r"aac|flac|opus|ac3|eac3|dts|truehd|atmos|\d+flac|\d+aac|"
    r"chs|cht|sc|tc|gb|big5|zh(?:[-_ ]?(?:hans|hant|cn|tw))?|jpn?|eng?|multi|字幕组|"
    r"japanese|english|chinese|korean|french|german|"
    r"imax|uhd|hdr|hdr10\+?|hdrplus|dovi|dv|remux|60fps|"
    r"hq|itunes|it\b|nf\b|netflix|amazon|hulu|"
    r"ddp\d?(?:[\s_]*\d+)?|dts[\s-]?hd|dts[\s-]?x|atmos|"
    r"truehd\d?(?:[\s_]*\d+)?|pcm|eac3|ac3|mp4|avi|mkv|"
    r"baha|cr|funi|hidive|bglobal|"
    r"ddp5[._\s]*1|truehd7[._\s]*1|ma5[._\s]*1|dts5[._\s]*1|"
    r"数字修复|内封|内嵌|简繁|简日|繁日|双语|中字|外挂|硬字幕"
    r")\b"
)
LANGUAGE_COMBO_PATTERN = re.compile(r"(?i)\b(?:chs|cht|sc|tc|zh[-_ ]?(?:hans|hant|cn|tw))(?:\s*&\s*(?:chs|cht|sc|tc|zh[-_ ]?(?:hans|hant|cn|tw)))+\b")
# 修复：不在字母/CJK字符后面的数字不应被当作集数去除（如 "Ne Zha 2" 中的 2、"5 Centimeters" 中的 5）
STANDALONE_EPISODE_NUMBER_PATTERN = re.compile(r"(?<![a-zA-Z0-9_\u4e00-\u9fff\u3040-\u30ff])\b\d{1,3}\b(?!\d)")
GENERIC_SEARCH_QUERY_PATTERN = re.compile(r"(?i)^(?:s\s*\d{1,2}|e\s*\d{1,3}|ep\s*\d{1,3}|\d{1,3}|\d{3,4}p|ma\s*10|ma10p)$")


TRAILING_RELEASE_GROUP_PATTERN = re.compile(
    r'(?i)\s*[-–—@]\s*(?:[A-Z0-9]{2,10}|'
    r'[A-Z][a-z]*[A-Z][a-z]{0,10}(?:HD|Studio|Web|TV|Team|Group|Raw|Team|Sub)s?|'
    r'(?:[A-Z][a-z]*){1,2}HD|'
    r'mn?hd|cmctv|mp4ba|frds|sonyhd|batweb|byndr|qhstudio)\s*$'
)


def _strip_search_noise(value: str) -> str:
    # 去除开头的发布组标签 [GROUPNAME] 如 [VCB-Studio]、[Snow-Raws]、[ANi]
    # 必须在 remove_tmdb_id_token 之前执行，因为后者会 strip 掉开头的 [
    clean = re.sub(r'^\[[A-Za-z0-9\-\_. ]{2,30}\]\s*', '', value)
    clean = remove_tmdb_id_token(clean)
    clean = clean.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    clean = LANGUAGE_COMBO_PATTERN.sub(' ', clean)
    clean = EPISODE_HINT_PATTERN.sub(' ', clean)
    clean = DISC_HINT_PATTERN.sub(' ', clean)
    clean = re.sub(r'\d{3,4}p', ' ', clean, flags=re.I)
    clean = MEDIA_NOISE_PATTERN.sub(' ', clean)
    clean = re.sub(r'(?i)(?:^|\s)-\s*(' + '|'.join(re.escape(t) for t in RELEASE_GROUP_TOKENS) + r')\b', ' ', clean)
    clean = re.sub(r'[._\-\[\]{}()!！?？：:．,、\'\"\u300c\u300d\u300e\u300f\u3010\u3011\u2019\u2018\u201c\u201d]', ' ', clean)
    clean = MEDIA_NOISE_PATTERN.sub(' ', clean)
    # 去除末尾的发布组标签（如：-FGT, -BATWEB, @ADWeb, -CMCTV）
    clean = TRAILING_RELEASE_GROUP_PATTERN.sub(' ', clean)
    clean = STANDALONE_EPISODE_NUMBER_PATTERN.sub(' ', clean)
    tokens = [token for token in re.split(r'\s+', clean.strip()) if token]
    tokens = [token for token in tokens if token.lower() not in RELEASE_GROUP_TOKENS]
    return re.sub(r'\s+', ' ', ' '.join(tokens)).strip()


def _is_useful_search_query(query: str) -> bool:
    clean = re.sub(r"\s+", " ", str(query or "")).strip()
    if not clean or GENERIC_SEARCH_QUERY_PATTERN.match(clean):
        return False
    cjk = extract_cjk(clean)
    alpha = extract_alpha(clean)
    if cjk:
        return len(cjk) >= 2
    if alpha:
        return len(alpha.replace(" ", "")) >= 3
    return False


def generate_keyword_queries(name: str) -> list[str]:
    clean = _strip_search_noise(name)
    if not clean or clean == name: return []
    return [clean]


def _dedupe_queries(values: list[str]) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for value in values:
        query = re.sub(r"\s+", " ", str(value or "")).strip()
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(query)
    return queries


def build_search_queries(raw_title: str, fallback_names: list[str] | None = None) -> list[str]:
    """Return cleaned title-search queries, with the strongest cleaned title first."""
    values = [raw_title, *(fallback_names or [])]
    variants: list[str] = []
    for value in values:
        base = remove_tmdb_id_token(str(value or ""))
        if not base.strip():
            continue
        variants.extend(generate_keyword_queries(base))
        variants.append(_strip_search_noise(generate_folder_identifier(base)))
        variants.append(_strip_search_noise(clean_folder_name(base)))
    return [query for query in _dedupe_queries(variants) if _is_useful_search_query(query)]


def clean_search_title(raw_title: str, fallback_names: list[str] | None = None) -> str:
    queries = build_search_queries(raw_title, fallback_names)
    return queries[0] if queries else ""


def _meaningful_local_metadata(raw) -> bool:
    if not raw or raw == "{}":
        return False
    metadata = raw
    if isinstance(raw, str):
        try:
            metadata = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False
    if not isinstance(metadata, dict):
        return False
    ignored = {"anime_naming"}
    meaningful = {k: v for k, v in metadata.items() if k not in ignored and v not in (None, "", {}, [])}
    if not meaningful:
        return False
    nfo = meaningful.get("nfo")
    if isinstance(nfo, dict) and nfo:
        return True
    return any(key in meaningful for key in ("title", "original_title", "plot", "year", "premiered"))

def clean_folder_name(name: str) -> str:
    name = remove_tmdb_id_token(name)
    name = re.sub(r'\(?\d{4}\)?', '', name)
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\{.*?\}', '', name)
    name = re.sub(r'\d{3,4}p', '', name, flags=re.I)
    name = EPISODE_HINT_PATTERN.sub(' ', name)
    name = DISC_HINT_PATTERN.sub(' ', name)
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
        stopwords = {"the", "a", "an", "of", "and", "or", "to", "in"}
        s_tokens = {w for w in s_alpha.split() if len(w) > 1 and w not in stopwords}
        f_tokens = {w for w in f_alpha.split() if len(w) > 1 and w not in stopwords}
        if s_tokens and f_tokens:
            overlap = len(s_tokens & f_tokens)
            smaller = min(len(s_tokens), len(f_tokens))
            if smaller >= 2 and overlap / smaller >= 0.75:
                return True

    if code:
        if code.upper() in scraped_title.upper(): return True
    return False


def candidate_title_matches(candidate: ScrapeCandidate, folder_name: str, query: str, code: str | None = None) -> bool:
    for title in (candidate.title, candidate.original_title or ""):
        if title_matches(title, folder_name, code) or title_matches(title, query, code):
            return True
    return False


def _is_specific_search_query(query: str) -> bool:
    clean = clean_folder_name(query)
    alpha = extract_alpha(clean)
    if alpha and len(alpha.replace(" ", "")) >= 4:
        return True
    cjk = extract_cjk(clean)
    return len(cjk) >= 2


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
        _set_scan_progress(media_root, status="scanning", done=0, total=0, trigger=trigger)
        for dirpath, dirnames, filenames in os.walk(base):
            folder = Path(dirpath)
            media_files = sorted({folder / f for f in filenames if Path(f).suffix.lower() in VIDEO_EXTS})
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
        _set_scan_progress(media_root, status="scanned", done=0, total=0, trigger=trigger)
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
        return ["bangumi", "tmdb_tv_search", "tmdb_movie_search"]
    return ["auto"]


def _staff_to_dict(staff: ScrapeStaff) -> dict:
    return {
        "name": staff.name,
        "role": staff.role or "",
        "job": staff.job or "",
        "department": staff.department or "",
        "person_id": staff.person_id or "",
        "source": staff.source or "",
    }


def _candidate_to_dict(candidate: ScrapeCandidate) -> dict:
    return {
        "source": candidate.source,
        "source_id": candidate.source_id,
        "media_type": candidate.media_type or "",
        "title": candidate.title,
        "original_title": candidate.original_title or "",
        "year": str(candidate.year or ""),
        "poster_url": candidate.poster_url,
        "backdrop_url": candidate.backdrop_url,
        "overview": candidate.overview or "",
        "score": candidate.score,
    }


def _thumbnail_json(result: ScrapeResult) -> str:
    raw = result.raw or {}
    existing = raw.get("javdb_thumbnails")
    if existing:
        return existing if isinstance(existing, str) else json.dumps(existing, ensure_ascii=False)
    thumbs = []
    for url in (result.thumbnail_url, result.still_url, result.episode_still_url):
        if url and url not in thumbs:
            thumbs.append(url)
    return json.dumps(thumbs, ensure_ascii=False) if thumbs else ""


def _scrape_result_to_legacy(result: ScrapeResult, *, exact: bool = False) -> dict:
    raw = result.raw or {}
    source = result.source
    cover = result.cover_url or result.poster_url or raw.get("cover_remote") or raw.get("poster_url") or ""
    media_type = result.media_type or raw.get("media_type") or ""
    source_id = str(result.source_id or raw.get("source_id") or "")
    release_date = raw.get("release_date") or raw.get("date") or (str(result.year) if result.year else "")
    duration = raw.get("runtime") or raw.get("duration")
    cast = [_staff_to_dict(item) for item in result.cast]
    crew = [_staff_to_dict(item) for item in result.crew]
    actress = raw.get("actress") or ""
    if not actress and source == "javdatabase" and cast:
        actress = ", ".join(item["name"] for item in cast if item.get("name"))

    data = {
        "source": source,
        "scraper_source": source,
        "source_id": source_id,
        "title": result.title or raw.get("title", ""),
        "original_title": result.original_title or raw.get("original_title") or "",
        "overview": result.overview or raw.get("overview") or "",
        "actress": actress,
        "release_date": release_date,
        "duration": duration,
        "cover_remote": cover,
        "backdrop_url": result.backdrop_url or raw.get("backdrop_url") or "",
        "javdb_url": raw.get("javdb_url") or raw.get("bgm_url") or "",
        "javdb_score": raw.get("score") or raw.get("javdb_score"),
        "javdb_likes": raw.get("votes") or raw.get("collection_total") or raw.get("javdb_likes"),
        "javdb_thumbnails": _thumbnail_json(result),
        "tmdb_id": int(result.tmdb_id) if result.tmdb_id and str(result.tmdb_id).isdigit() else raw.get("tmdb_id"),
        "tmdb_type": media_type if source == "tmdb" else "",
        "bangumi_id": result.bangumi_id,
        "javdb_id": result.javdb_id,
        "seasons": raw.get("seasons", []),
        "cast": cast,
        "crew": crew,
        "imdb_id": raw.get("imdb_id"),
        "episode_title": result.episode_title or raw.get("episode_title") or "",
        "episode_still": result.episode_still_url or raw.get("episode_still") or "",
        "_exact_match": exact,
        "_raw": raw,
        "scraper_raw": json.dumps(raw, ensure_ascii=False) if raw else "",
    }
    if result.season is not None:
        data["tmdb_season"] = result.season
    if result.episode is not None:
        data["tmdb_episode"] = result.episode
    return data


def _scraper_name_for_source(source: str | None, media_type: str | None = None) -> str:
    value = (source or "auto").strip().lower()
    if value in {"tmdb", "tmdb_movie", "tmdb_tv"}:
        return "tmdb_tv" if media_type == "tv" or value == "tmdb_tv" else "tmdb_movie"
    return normalize_scraper_name(value)


async def _fetch_detail_legacy(
    source: str,
    source_id: str,
    media_type: str | None = None,
    *,
    exact: bool = True,
) -> dict | None:
    scraper_name = _scraper_name_for_source(source, media_type)
    try:
        scraper = get_scraper(scraper_name)
        result = await scraper.get_detail(source_id, media_type=media_type)
    except Exception as e:
        from .config import logger
        logger.warning(f"  {scraper_name}: detail error for {source_id}: {e}")
        return None
    if not result or not result.title:
        return None
    return _scrape_result_to_legacy(result, exact=exact)


async def _search_scraper_candidates(scraper_name: str, query: str, media_type: str | None = None, limit: int = 10) -> list[ScrapeCandidate]:
    try:
        scraper = get_scraper(scraper_name)
        return await scraper.search(query, media_type=media_type, limit=limit)
    except Exception as e:
        from .config import logger
        logger.warning(f"  {scraper_name}: search error for '{query}': {e}")
        return []

async def try_scrape_javdb(code: str) -> dict | None:
    return await _fetch_detail_legacy("javdatabase", code, "movie")

def _tmdb_scrape_data(detail: dict, source_id: str, media_type: str, exact: bool = False) -> dict:
    return {
        "source": "tmdb", "scraper_source": "tmdb", "source_id": str(source_id),
        "title": detail.get("title", ""),
        "original_title": detail.get("original_title", ""),
        "overview": detail.get("overview", ""),
        "release_date": detail.get("release_date", ""),
        "duration": detail.get("runtime") or detail.get("duration", 0),
        "cover_remote": detail.get("poster_url", ""),
        "backdrop_url": detail.get("backdrop_url", ""),
        "javdb_score": detail.get("score"), "javdb_likes": detail.get("votes"),
        "tmdb_id": int(source_id), "tmdb_type": media_type,
        "seasons": detail.get("seasons", []), "cast": detail.get("cast", []),
        "crew": detail.get("crew", []), "imdb_id": detail.get("imdb_id"),
        "_raw": detail,
        "scraper_raw": json.dumps(detail, ensure_ascii=False) if detail else "",
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
    from .config import logger
    clean_title = clean_search_title(folder_name, [code])
    scope = media_type or "movie+tv"
    if not clean_title:
        logger.info(f"  TMDB {scope}: no clean title for raw_title='{folder_name}', skipping search")
        return None
    if not settings.tmdb_api_key and not settings.tmdb_access_token:
        logger.warning(f"  TMDB {scope}: API key/access token missing, cannot search clean_title='{clean_title}'")
        return None
    queries = build_search_queries(clean_title, [folder_name, code])
    best: ScrapeCandidate | None = None
    scraper_names = ["tmdb_tv" if media_type == "tv" else "tmdb_movie"] if media_type else ["tmdb_movie", "tmdb_tv"]
    failures: list[str] = []
    primary_query = queries[0] if queries else clean_title
    for query in queries:
        if not query: continue
        for scraper_name in scraper_names:
            endpoint_type = "tv" if scraper_name == "tmdb_tv" else "movie"
            api_type = "tmdb_search_tv" if endpoint_type == "tv" else "tmdb_search_movie"
            logger.info(
                f"  fallback step={api_type} raw_title='{folder_name}' clean_title='{clean_title}' "
                f"query='{query}' cache_key='tmdb_search:{endpoint_type}:{query}'"
            )
            results = await _search_scraper_candidates(scraper_name, query, media_type=media_type, limit=5)
            logger.info(f"  {api_type}: candidates={len(results)} query='{query}'")
            if not results:
                failures.append(f"{scraper_name}:{query}: no results")
                continue
            rejected = []
            for candidate in results[:3]:
                matched = candidate_title_matches(candidate, clean_title, query, code)
                if (
                    not matched
                    and query == primary_query
                    and len(results) <= 2
                    and _is_specific_search_query(query)
                ):
                    matched = True
                    logger.info(
                        f"  {api_type}: title_matches relaxed accept (candidates={len(results)}) "
                        f"query='{query}' source_id='{candidate.source_id}'"
                    )
                logger.info(
                    f"  {api_type}: title_matches={matched} source_id='{candidate.source_id}' "
                    f"title='{candidate.title}' original_title='{candidate.original_title or ''}'"
                )
                if matched:
                    best = candidate
                    break
                rejected.append(candidate.title)
            if not best:
                logger.info(
                    f"  {scraper_name}: title_matches rejected query='{query}' "
                    f"candidates={rejected[:3]}"
                )
                failures.append(f"{scraper_name}:{query}: title mismatch")
            if best: break
        if best: break
    if not best:
        logger.info(f"  TMDB {scope}: no match for clean_title='{clean_title}', failures={'; '.join(failures)}")
        return None
    logger.info(
        f"  TMDB {best.media_type}: selected source_id={best.source_id} "
        f"title='{best.title}' original_title='{best.original_title or ''}'"
    )
    data = await _fetch_detail_legacy("tmdb", best.source_id, best.media_type, exact=False)
    if not data:
        return None
    if not data.get("title"):
        data["title"] = best.title
    data["_search_match_passed"] = True
    return data


async def try_scrape_tmdb_typed(
    search_name: str,
    code: str,
    media_type: Literal["movie", "tv"],
    candidate_names: list[str] | None = None,
    movie: dict | None = None,
) -> dict | None:
    from .config import logger
    candidates = candidate_names or [search_name, code]
    token = _first_tmdb_token(candidates)
    scraper_name = "tmdb_movie" if media_type == "movie" else "tmdb_tv"
    clean_title = clean_search_title(search_name, candidates)
    existing_tmdb_id = str((movie or {}).get("tmdb_id") or "").strip()
    existing_tmdb_type = str((movie or {}).get("tmdb_type") or "").strip()
    if not token and existing_tmdb_id and (not existing_tmdb_type or existing_tmdb_type == media_type):
        try:
            token = TmdbIdToken(int(existing_tmdb_id), media_type, existing_tmdb_id, f"{media_type}.tmdb_id", "explicit")
        except ValueError:
            logger.warning(f"  {scraper_name}: invalid stored tmdb_id='{existing_tmdb_id}', fallback to title search")

    logger.info(
        f"  {scraper_name}: raw_title='{search_name}' clean_title='{clean_title}' "
        f"tmdb_token={'yes' if token else 'no'}"
    )

    if token:
        logger.info(
            f"  {scraper_name}: detected tmdbid={token.id} from {token.source_name}; "
            f"using /{media_type}/{token.id}"
        )
        if settings.tmdb_api_key or settings.tmdb_access_token:
            data = await _fetch_detail_legacy("tmdb", str(token.id), media_type, exact=True)
            if data and data.get("title"):
                logger.info(f"  {scraper_name}: TMDB ID exact match success /{media_type}/{token.id}")
                return data
            logger.warning("  TMDB ID 精确匹配失败，fallback 到标题搜索")
        else:
            logger.warning(f"  {scraper_name}: TMDB credentials not configured, fallback to title search")

    if not clean_title:
        logger.info(f"  {scraper_name}: no clean title after TMDB ID fallback, cannot run search APIs")
        return None

    # 顺序 fallback：先 Bangumi 搜索 API，失败则 TMDB 标题搜索 API
    logger.info(f"  {scraper_name}: sequential fallback to Bangumi for '{clean_title}'")
    data = await try_scrape_bangumi(clean_title, code)
    if data and data.get("title"):
        logger.info(f"  {scraper_name}: sequential fallback Bangumi success for '{clean_title}'")
        return data

    logger.info(f"  {scraper_name}: sequential fallback to TMDB {media_type} title search for '{clean_title}'")
    data = await try_scrape_tmdb_title(clean_title, code, media_type)
    if data and data.get("title"):
        logger.info(f"  {scraper_name}: sequential fallback TMDB title search success for '{clean_title}'")
        return data

    logger.info(f"  {scraper_name}: all sequential fallbacks failed for '{clean_title}'")
    return None


async def try_scrape_tmdb_movie(
    search_name: str,
    code: str,
    candidate_names: list[str] | None = None,
    movie: dict | None = None,
) -> dict | None:
    return await try_scrape_tmdb_typed(search_name, code, "movie", candidate_names, movie)


async def try_scrape_tmdb_tv(
    search_name: str,
    code: str,
    candidate_names: list[str] | None = None,
    movie: dict | None = None,
) -> dict | None:
    return await try_scrape_tmdb_typed(search_name, code, "tv", candidate_names, movie)


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
    if media_type in {"movie", "tv"}:
        data = await _fetch_detail_legacy("tmdb", str(tmdb_id), media_type, exact=True)
        if data and data.get("title"):
            return data
        logger.info(f"  TMDB ID exact match failed for tmdbid={tmdb_id}")
        return None

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
    from .config import logger
    raw_title = folder_name
    clean_title = clean_search_title(folder_name, [code])
    if not clean_title:
        logger.info(f"  Bangumi: no clean title for raw_title='{raw_title}', skipping search")
        return None
    queries = build_search_queries(clean_title, [raw_title, code])
    best: ScrapeCandidate | None = None
    failures: list[str] = []
    primary_query = queries[0] if queries else clean_title
    for query in queries:
        if not query: continue
        logger.info(
            f"  fallback step=bangumi_search raw_title='{raw_title}' clean_title='{clean_title}' "
            f"query='{query}' cache_key='bangumi_search:anime:{query}'"
        )
        results = await _search_scraper_candidates("bangumi", query, limit=5)
        logger.info(f"  bangumi_search: candidates={len(results)} query='{query}'")
        if not results:
            failures.append(f"{query}: no results")
            continue
        rejected = []
        for candidate in results[:3]:
            matched = candidate_title_matches(candidate, clean_title, query, code)
            if (
                not matched
                and query == primary_query
                and len(results) <= 2
                and _is_specific_search_query(query)
            ):
                matched = True
                logger.info(
                    f"  bangumi_search: title_matches relaxed accept (candidates={len(results)}) "
                    f"query='{query}' source_id='{candidate.source_id}'"
                )
            logger.info(
                f"  bangumi_search: title_matches={matched} source_id='{candidate.source_id}' "
                f"title='{candidate.title}' original_title='{candidate.original_title or ''}'"
            )
            if matched:
                best = candidate
                break
            rejected.append(candidate.title)
        if not best:
            failures.append(f"{query}: title mismatch {rejected[:3]}")
        if best: break
    if not best:
        logger.info(f"  Bangumi: no match for clean_title='{clean_title}', failures={'; '.join(failures)}")
        return None
    data = await _fetch_detail_legacy("bangumi", best.source_id, best.media_type, exact=False)
    if not data:
        return None
    if not data.get("title"):
        data["title"] = best.title
    data["_search_match_passed"] = True
    return data

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

    clean_title = clean_search_title(search_name, candidates)
    logger.info(
        f"  Auto scraper fallback title search raw_title='{search_name}' "
        f"clean_title='{clean_title}' tmdb_token={'yes' if token else 'no'}"
    )
    if not clean_title:
        logger.info(f"  Auto scraper failed: no clean title for '{search_name}'")
        return None

    # 顺序 fallback：先 Bangumi 搜索 API，失败则 TMDB 标题搜索 API
    logger.info(f"  Auto scraper: sequential fallback to Bangumi for '{clean_title}'")
    data = await try_scrape_bangumi(clean_title, code)
    if data and data.get("title"):
        logger.info(f"  Auto scraper: sequential fallback Bangumi success for '{clean_title}'")
        return data

    logger.info(f"  Auto scraper: sequential fallback to TMDB title search for '{clean_title}'")
    data = await try_scrape_tmdb(clean_title, code)
    if data and data.get("title"):
        logger.info(f"  Auto scraper: sequential fallback TMDB title search success for '{clean_title}'")
        return data

    logger.info(f"  Auto scraper: all sequential fallbacks failed for '{clean_title}'")
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
    has_metadata = _meaningful_local_metadata(movie_row.get("local_metadata"))
    cover = movie_row.get("cover_local")
    has_cover = bool(cover and (len(str(cover)) <= 64 or Path(str(cover)).exists()))
    return has_metadata and has_cover


def has_complete_scraped_data(movie_row: dict) -> bool:
    title = bool((movie_row.get("title") or "").strip())
    cover = bool(movie_row.get("cover_local") or movie_row.get("cover_remote"))
    source_id = bool(
        movie_row.get("tmdb_id")
        or movie_row.get("source_id")
        or movie_row.get("bangumi_id")
        or movie_row.get("javdb_id")
        or movie_row.get("javdb_url")
    )
    return title and cover and source_id

async def _apply_scraped_data(folder_levels: str, data: dict, media_root: str = "", replace: bool = False) -> int:
    from .database import get_db
    from .config import logger
    db = await get_db()
    fields = {
        "title": data.get("title") or "",
        "original_title": data.get("original_title") or "",
        "overview": data.get("overview") or "",
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
        "tmdb_season": data.get("tmdb_season"),
        "tmdb_episode": data.get("tmdb_episode"),
        "episode_title": data.get("episode_title") or "",
        "episode_still": data.get("episode_still") or "",
        "scraper_source": data.get("scraper_source") or data.get("source") or "",
        "source_id": data.get("source_id") or "",
        "bangumi_id": data.get("bangumi_id") or "",
        "javdb_id": data.get("javdb_id") or "",
        "scraper_raw": data.get("scraper_raw") or (json.dumps(data.get("_raw"), ensure_ascii=False) if data.get("_raw") else ""),
        "cast": json.dumps(data.get("cast") or [], ensure_ascii=False),
        "crew": json.dumps(data.get("crew") or [], ensure_ascii=False),
    }
    if replace:
        set_sql = """
               title=NULLIF(?, ''),
               original_title=NULLIF(?, ''),
               overview=NULLIF(?, ''),
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
               scraper_source=NULLIF(?, ''),
               source_id=NULLIF(?, ''),
               bangumi_id=NULLIF(?, ''),
               javdb_id=NULLIF(?, ''),
               scraper_raw=NULLIF(?, ''),
               tmdb_season=?,
               tmdb_episode=?,
               episode_title=NULLIF(?, ''),
               episode_overview=NULL,
               episode_still=NULLIF(?, ''),
               episode_still_local=NULL,
               updated_at=datetime('now')
        """
    else:
        set_sql = """
               title=COALESCE(NULLIF(?, ''), title),
               original_title=COALESCE(NULLIF(?, ''), original_title),
               overview=COALESCE(NULLIF(?, ''), overview),
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
               scraper_source=COALESCE(NULLIF(?, ''), scraper_source),
               source_id=COALESCE(NULLIF(?, ''), source_id),
               bangumi_id=COALESCE(NULLIF(?, ''), bangumi_id),
               javdb_id=COALESCE(NULLIF(?, ''), javdb_id),
               scraper_raw=COALESCE(NULLIF(?, ''), scraper_raw),
               tmdb_season=COALESCE(?, tmdb_season),
               tmdb_episode=COALESCE(?, tmdb_episode),
               episode_title=COALESCE(NULLIF(?, ''), episode_title),
               episode_still=COALESCE(NULLIF(?, ''), episode_still),
               updated_at=datetime('now')
        """
    values = (
        fields["title"], fields["original_title"], fields["overview"],
        fields["actress"], fields["release_date"], fields["duration"],
        fields["javdb_url"], fields["javdb_score"], fields["javdb_likes"],
        fields["javdb_thumbnails"], fields["cover_remote"], fields["fanart_local"],
        fields["tmdb_id"], fields["tmdb_type"], fields["cast"], fields["crew"],
        fields["scraper_source"], fields["source_id"], fields["bangumi_id"], fields["javdb_id"],
        fields["scraper_raw"],
        fields["tmdb_season"], fields["tmdb_episode"], fields["episode_title"], fields["episode_still"],
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
            if media_root:
                await db.execute(
                    """UPDATE movies SET
                       cover_remote=COALESCE(NULLIF(?, ''), cover_remote),
                       updated_at=datetime('now')
                       WHERE folder_levels LIKE ? AND media_root=?""",
                    (data.get("cover_remote", ""), parent + "/%", media_root)
                )
            else:
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
        _set_scan_progress(media_root, status="disabled", done=0, total=0, trigger=trigger)
        return

    chain = build_fallback_chain(scraper)
    logger.info(f"Scraping {media_root}: scraper={normalize_scraper_name(scraper)} chain={' → '.join(chain)}")

    db = await get_db()
    cur = await db.execute(
        """SELECT DISTINCT id, code, folder_levels, path, title, cover_local, cover_remote,
                  javdb_url, local_metadata, tmdb_id, tmdb_type, tmdb_season, tmdb_episode,
                  clean_title, episode_number, display_title, source_id, bangumi_id, javdb_id
           FROM movies WHERE media_root=?""",
        (media_root,)
    )
    rows = await cur.fetchall()
    if not rows:
        _set_scan_progress(media_root, status="done", done=0, total=0, trigger=trigger)
        return

    folder_rows: list[dict] = []
    seen_folders = set()
    for r in rows:
        folder_levels = r["folder_levels"] or ""
        if not folder_levels or folder_levels in seen_folders:
            continue
        seen_folders.add(folder_levels)
        folder_rows.append(dict(r))

    total_folders = len(folder_rows)
    if not total_folders:
        _set_scan_progress(media_root, status="done", done=0, total=0, trigger=trigger)
        return

    per_library_limit = _bounded_int(settings.scrape_concurrency_per_library, 4)
    per_library_sem = asyncio.Semaphore(per_library_limit)
    global_sem = _get_global_scrape_semaphore()
    done_count = 0
    success_count = 0
    failed_count = 0
    skipped_count = 0
    active_count = 0
    progress_lock = asyncio.Lock()

    _set_scan_progress(
        media_root,
        status="scraping",
        done=0,
        total=total_folders,
        success=0,
        failed=0,
        skipped=0,
        active_concurrency=0,
        trigger=trigger,
        per_library_concurrency=per_library_limit,
        global_concurrency=_global_scrape_limit,
    )

    async def process_folder(r: dict):
        nonlocal done_count, success_count, failed_count, skipped_count, active_count
        folder_levels = r.get("folder_levels") or ""
        folder_name = Path(folder_levels).name if folder_levels else ""
        code = r.get("code") or ""
        movie_path = r.get("path") or ""
        row_clean_title = (r.get("clean_title") or "").strip()

        if not folder_name:
            async with progress_lock:
                skipped_count += 1
                done_count += 1
                _set_scan_progress(media_root, done=done_count, skipped=skipped_count)
            return

        if has_local_data(r):
            logger.info(f"  Skip (local data exists): {folder_name}")
            async with progress_lock:
                skipped_count += 1
                done_count += 1
                _set_scan_progress(media_root, done=done_count, skipped=skipped_count)
            return

        if has_complete_scraped_data(r):
            logger.info(f"  Skip (complete scraped data exists): {folder_name}")
            async with progress_lock:
                skipped_count += 1
                done_count += 1
                _set_scan_progress(media_root, done=done_count, skipped=skipped_count)
            return

        # 使用源文件夹名进行搜索（参考 Jellyfin 刮削逻辑），而非视频文件名
        search_name = folder_name
        search_levels = folder_levels
        if is_season_folder(folder_name):
            parent = Path(folder_levels).parent
            parent_name = parent.name if str(parent) != "." else ""
            if parent_name:
                search_name = parent_name
                search_levels = str(parent)

        if search_levels != folder_levels:
            logger.info(f"  Season folder detected: '{folder_name}' → searching as '{search_name}'")

        candidate_names = [
            row_clean_title,
            folder_name,
            Path(folder_levels).parent.name if folder_levels and str(Path(folder_levels).parent) != "." else "",
            Path(movie_path).stem if movie_path else "",
            r.get("title") or "",
            r.get("display_title") or "",
            code,
            search_name,
        ]
        clean_title_for_log = clean_search_title(search_name, candidate_names)
        token_for_log = _first_tmdb_token(candidate_names)
        logger.info(
            f"Scrape item: media_root='{media_root}' movie_id={r.get('id') or ''} "
            f"scraper='{normalize_scraper_name(scraper)}' raw_title='{search_name}' "
            f"clean_title='{clean_title_for_log}' tmdb_token={'yes' if token_for_log else 'no'} "
            f"tmdb_id='{r.get('tmdb_id') or ''}'"
        )

        scraped = False
        async with per_library_sem:
            async with global_sem:
                async with progress_lock:
                    active_count += 1
                    _set_scan_progress(media_root, active_concurrency=active_count)
                try:
                    for sb in chain:
                        handler = FALLBACK_HANDLERS.get(sb)
                        if not handler:
                            continue
                        try:
                            if sb == "javdatabase":
                                data = await handler(code)
                            elif sb in {"auto", "tmdb_movie", "tmdb_tv", "tmdb"}:
                                data = await handler(search_name, code, candidate_names, r)
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
                                passed = (
                                    bool(data.get("_exact_match"))
                                    or bool(data.get("_search_match_passed"))
                                    or title_matches(data.get("title", ""), search_name, code)
                                    or title_matches(data.get("original_title", ""), search_name, code)
                                )
                            if passed:
                                async with _sqlite_write_semaphore:
                                    await _apply_scraped_data(folder_levels, data, media_root)
                                logger.info(
                                    f"  {sb}: applied source='{data.get('source') or data.get('scraper_source') or sb}' "
                                    f"source_id='{data.get('source_id') or data.get('tmdb_id') or data.get('bangumi_id') or data.get('javdb_id') or ''}' "
                                    f"clean_title='{clean_title_for_log}' title='{data.get('title', search_name)}'"
                                )

                                if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                                    season_num = infer_season_number(folder_name, data)
                                    if season_num:
                                        try:
                                            from .tmdb import match_episodes_in_folder
                                            async with _sqlite_write_semaphore:
                                                matched = await match_episodes_in_folder(
                                                    str(data["tmdb_id"]), season_num, folder_levels, media_root
                                                )
                                            if matched:
                                                logger.info(f"  TMDB: matched {matched} episodes in '{folder_levels}'")
                                        except Exception as e:
                                            logger.warning(f"  TMDB: episode matching error: {e}")

                                scraped = True
                                break
                            logger.info(f"  {sb}: title mismatch '{data.get('title', '')}' vs '{search_name}', trying fallback")
                        except Exception:
                            logger.exception(
                                f"  {sb}: error for media_root='{media_root}' folder='{folder_name}' "
                                f"cleaned_title='{search_name}'"
                            )
                finally:
                    async with progress_lock:
                        active_count -= 1
                        _set_scan_progress(media_root, active_concurrency=active_count)

        async with progress_lock:
            if scraped:
                success_count += 1
            else:
                failed_count += 1
                logger.info(f"  All scrapers failed for '{search_name}'")
            done_count += 1
            _set_scan_progress(
                media_root,
                done=done_count,
                success=success_count,
                failed=failed_count,
                skipped=skipped_count,
            )

    results = await asyncio.gather(*(process_folder(row) for row in folder_rows), return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.warning(f"Scrape task failed for {media_root}: {result}")
            failed_count += 1

    _set_scan_progress(
        media_root,
        status="done",
        done=total_folders,
        total=total_folders,
        success=success_count,
        failed=failed_count,
        skipped=skipped_count,
        active_concurrency=0,
        trigger=trigger,
    )


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
            _set_scan_progress(
                media_root,
                status="scanning",
                done=0,
                total=0,
                success=0,
                failed=0,
                skipped=0,
                active_concurrency=0,
                trigger=trigger,
            )
            logger.info(f"Scan started for {media_root} trigger={trigger}")
            results = await asyncio.to_thread(scan_media, root=media_root)
            for item in results:
                async with _sqlite_write_semaphore:
                    await upsert_movie(item)
            async with _sqlite_write_semaphore:
                removed_total += await cleanup_deleted_files(media_root)
            total_results += len(results)
            _set_scan_progress(media_root, status="scraping", done=0, total=0, trigger=trigger)
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

    if not media_root:
        logger.warning("clear_library_scraped_data rejected: media_root is required")
        raise ValueError("media_root required")

    db = await get_db()
    cur = await db.execute(
        """UPDATE movies SET title=NULL, actress=NULL, release_date=NULL,
           duration=NULL, cover_local=NULL, cover_remote=NULL, fanart_local=NULL,
           javdb_url=NULL, javdb_score=NULL, javdb_likes=NULL, javdb_thumbnails=NULL,
           tmdb_id=NULL, tmdb_type=NULL, tmdb_season=NULL, tmdb_episode=NULL,
           scraper_source=NULL, source_id=NULL, bangumi_id=NULL, javdb_id=NULL,
           original_title=NULL, overview=NULL, scraper_raw=NULL,
           episode_title=NULL, episode_overview=NULL, episode_still=NULL, episode_still_local=NULL,
           "cast"='[]', crew='[]',
           updated_at=datetime('now')
           WHERE media_root=?""",
        (media_root,)
    )
    await db.commit()

    affected = cur.rowcount if cur.rowcount is not None else 0
    logger.info(
        f"Cleared scraped fields for media_root='{media_root}', affected={affected}; "
        "scraper_cache/javdb_cache and other media roots preserved"
    )


async def rescrape_movie(movie_id: int) -> dict:
    from .database import get_db, get_library_settings
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
    search_name = folder_name
    search_levels = folder_levels
    if is_season_folder(folder_name):
        parent = Path(folder_levels).parent
        parent_name = parent.name if str(parent) != "." else ""
        if parent_name:
            search_name = parent_name
            search_levels = str(parent)

    logger.info(
        f"rescrape_movie start: media_root='{media_root}' movie_id={movie_id} "
        f"scraper='{scraper}' chain={chain} folder='{folder_levels}' clean_title='{row_clean_title}' "
        f"search_name='{search_name}' tmdb_id='{movie.get('tmdb_id') or ''}'"
    )

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
    clean_title_for_log = clean_search_title(search_name, candidate_names)
    token_for_log = _first_tmdb_token(candidate_names)
    logger.info(
        f"rescrape_movie item: media_root='{media_root}' movie_id={movie_id} "
        f"scraper='{normalize_scraper_name(scraper)}' raw_title='{search_name}' "
        f"clean_title='{clean_title_for_log}' tmdb_token={'yes' if token_for_log else 'no'} "
        f"tmdb_id='{movie.get('tmdb_id') or ''}'"
    )

    failures: list[str] = []
    for sb in chain:
        handler = FALLBACK_HANDLERS.get(sb)
        if not handler:
            failures.append(f"{sb}: handler missing")
            continue
        try:
            if sb == "javdatabase":
                data = await handler(code)
            elif sb in {"auto", "tmdb_movie", "tmdb_tv", "tmdb"}:
                data = await handler(search_name, code, candidate_names, movie)
            else:
                data = await handler(search_name, code)
            if not data or not data.get("title"):
                failures.append(f"{sb}: no result")
                logger.info(
                    f"rescrape_movie no result: media_root='{media_root}' movie_id={movie_id} "
                    f"scraper='{sb}' search='{search_name}'"
                )
                continue
            if sb in {"javdatabase", "auto"} and data.get("_exact_match"):
                passed = True
            elif sb == "javdatabase":
                passed = True
            else:
                passed = (
                    bool(data.get("_exact_match"))
                    or bool(data.get("_search_match_passed"))
                    or title_matches(data.get("title", ""), search_name, code)
                    or title_matches(data.get("original_title", ""), search_name, code)
                )
            if passed:
                async with _sqlite_write_semaphore:
                    affected = await _apply_scraped_data(folder_levels, data, media_root)
                if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                    season_num = infer_season_number(folder_name, data)
                    if season_num:
                        try:
                            from .tmdb import match_episodes_in_folder
                            async with _sqlite_write_semaphore:
                                await match_episodes_in_folder(
                                    str(data["tmdb_id"]), season_num, folder_levels, media_root
                                )
                        except Exception:
                            pass
                logger.info(
                    f"rescrape_movie success: media_root='{media_root}' movie_id={movie_id} "
                    f"scraper='{sb}' title='{data.get('title', search_name)}' affected={affected}"
                )
                return {"ok": True, "source": sb, "title": data.get("title", search_name), "affected": affected}
            else:
                failures.append(f"{sb}: title mismatch '{data.get('title', '')}'")
                logger.info(
                    f"rescrape_movie title mismatch: media_root='{media_root}' movie_id={movie_id} "
                    f"scraper='{sb}' cleaned_title='{search_name}' result_title='{data.get('title', '')}' "
                    f"source_id='{data.get('source_id') or data.get('tmdb_id') or data.get('bangumi_id') or data.get('javdb_id') or ''}'"
                )
        except Exception as e:
            failures.append(f"{sb}: {e}")
            logger.exception(
                f"rescrape_movie error: media_root='{media_root}' movie_id={movie_id} "
                f"scraper='{sb}' cleaned_title='{search_name}'"
            )

    failure_text = "; ".join(failures) if failures else "no handlers tried"
    logger.warning(
        f"rescrape_movie failed: media_root='{media_root}' movie_id={movie_id} "
        f"library_scraper='{scraper}' cleaned_title='{search_name}' failures={failure_text}"
    )
    return {"ok": False, "error": f"All scrapers failed: {failure_text}"}


async def rescrape_movie_manual(movie_id: int, query: str, preferred_scraper: str = None, source_id: str = None, media_type: str = "movie") -> dict:
    from .database import get_db, get_library_settings
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
            forced_media_type = "tv" if preferred == "tmdb_tv" else "movie"
            data = await _fetch_detail_legacy("tmdb", source_id, forced_media_type)
        elif preferred == "bangumi":
            data = await _fetch_detail_legacy("bangumi", source_id, "tv")
        elif preferred == "javdatabase":
            data = await _fetch_detail_legacy("javdatabase", source_id, "movie")

        if data and data.get("title"):
            async with _sqlite_write_semaphore:
                await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                folder_name = Path(folder_levels).name if folder_levels else ""
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        async with _sqlite_write_semaphore:
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
            async with _sqlite_write_semaphore:
                await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                folder_name = Path(folder_levels).name if folder_levels else ""
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        async with _sqlite_write_semaphore:
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

    if not media_root:
        return {"ok": False, "error": "media_root required"}

    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) AS total FROM movies WHERE folder_levels=? AND media_root=?",
        (folder_levels, media_root),
    )
    count_row = await cur.fetchone()
    total = int(count_row["total"] or 0) if count_row else 0
    if total <= 0:
        return {"ok": False, "error": "No movies found in folder"}

    cur = await db.execute(
        "SELECT id FROM movies WHERE folder_levels=? AND media_root=? ORDER BY id LIMIT 1",
        (folder_levels, media_root),
    )
    row = await cur.fetchone()
    if not row:
        return {"ok": False, "error": "No movies found in folder"}

    logger.info(
        f"Folder rescrape start: media_root='{media_root}' folder='{folder_levels}' "
        f"movie_count={total} representative_movie_id={row['id']}"
    )
    result = await rescrape_movie(row["id"])
    if not result.get("ok"):
        logger.warning(
            f"Folder rescrape failed: media_root='{media_root}' folder='{folder_levels}' "
            f"movie_count={total} error='{result.get('error', '')}'"
        )
        return result

    affected = int(result.get("affected") or total)
    logger.info(
        f"Folder rescrape complete: media_root='{media_root}' folder='{folder_levels}' "
        f"affected={affected} total={total} source='{result.get('source')}'"
    )
    return {"ok": True, "rescraped": affected, "total": total, "source": result.get("source"), "title": result.get("title")}


async def search_for_scrape(query: str, scraper: str = "tmdb") -> list[dict]:
    scraper = normalize_scraper_name(scraper)
    if scraper in {"tmdb_movie", "tmdb_tv"}:
        media_type = "tv" if scraper == "tmdb_tv" else "movie"
        items = await _search_scraper_candidates(scraper, query, media_type=media_type, limit=10)
        return [_candidate_to_dict(item) for item in items]
    elif scraper == "bangumi":
        items = await _search_scraper_candidates("bangumi", query, limit=10)
        return [_candidate_to_dict(item) for item in items]
    elif scraper == "javdatabase":
        items = await _search_scraper_candidates("javdatabase", query, media_type="movie", limit=10)
        return [_candidate_to_dict(item) for item in items]
    return []


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
        if src == "tmdb":
            detail = await _fetch_detail_legacy("tmdb", sid, mtype)
        elif src == "bangumi":
            detail = await _fetch_detail_legacy("bangumi", sid, "tv")
        else:
            detail = None
        backdrop = detail.get("backdrop_url") if detail else None
        backdrops.append({"source_id": sid, "source": src, "backdrop_url": backdrop, "poster_url": r.get("poster_url")})
    return backdrops


async def change_folder_backdrop(folder_levels: str, media_root: str, fanart_url: str) -> dict:
    from .database import get_db
    from .config import logger
    if not fanart_url:
        return {"ok": False, "error": "No URL provided"}
    if not media_root:
        return {"ok": False, "error": "media_root required"}
    db = await get_db()
    await db.execute("UPDATE movies SET fanart_local=?, updated_at=datetime('now') WHERE folder_levels=? AND media_root=?", (fanart_url, folder_levels, media_root))
    await db.commit()
    logger.info(f"Backdrop changed for folder {folder_levels}")
    return {"ok": True}


async def rescrape_folder_manual(folder_levels: str, media_root: str, query: str, preferred_scraper: str = "") -> dict:
    from .database import get_db, get_library_settings
    from .config import logger

    if not media_root:
        return {"ok": False, "error": "media_root required"}

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

    cur = await db.execute("SELECT code FROM movies WHERE folder_levels=? AND media_root=? LIMIT 1", (folder_levels, media_root))
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
            async with _sqlite_write_semaphore:
                await _apply_scraped_data(folder_levels, data, media_root, replace=True)
            if data.get("source") == "tmdb" and data.get("tmdb_type") == "tv" and data.get("tmdb_id"):
                season_num = infer_season_number(folder_name, data)
                if season_num:
                    try:
                        from .tmdb import match_episodes_in_folder
                        async with _sqlite_write_semaphore:
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

    if not media_root:
        return {"ok": False, "error": "media_root required"}

    data = None
    if source == "tmdb":
        data = await _fetch_detail_legacy("tmdb", source_id, media_type)
    elif source == "bangumi":
        data = await _fetch_detail_legacy("bangumi", source_id, "tv")
    elif source == "javdatabase":
        data = await _fetch_detail_legacy("javdatabase", source_id, "movie")

    if not data or not data.get("title"):
        return {"ok": False, "error": f"Failed to fetch detail from {source}"}

    folder_name = Path(folder_levels).name if folder_levels else ""
    async with _sqlite_write_semaphore:
        affected = await _apply_scraped_data(folder_levels, data, media_root, replace=True)

    if source == "tmdb" and media_type == "tv" and data.get("tmdb_id"):
        season_num = infer_season_number(folder_name, data)
        if season_num:
            try:
                from .tmdb import match_episodes_in_folder
                async with _sqlite_write_semaphore:
                    await match_episodes_in_folder(str(data["tmdb_id"]), season_num, folder_levels, media_root)
            except Exception:
                pass

    logger.info(f"apply_folder_scrape: source={source} folder='{folder_levels}' media_root='{media_root}' affected={affected} rows title='{data.get('title')}'")
    return {"ok": True, "source": source, "title": data.get("title", ""), "affected": affected}


async def change_folder_cover(folder_levels: str, media_root: str, cover_url: str) -> dict:
    from .database import get_db
    from .config import logger
    import hashlib

    if not media_root:
        return {"ok": False, "error": "media_root required"}
    db = await get_db()
    try:
        from .covers import download_and_compress_cover
        cache_key = hashlib.md5(cover_url.encode()).hexdigest()[:16]
        await download_and_compress_cover(cover_url, cache_key)
        await db.execute(
            "UPDATE movies SET cover_remote=?, cover_local=?, updated_at=datetime('now') WHERE folder_levels=? AND media_root=?",
            (cover_url, cache_key, folder_levels, media_root)
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

    if not media_root:
        return {"ok": False, "error": "media_root required"}
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
    values.extend([folder_levels, media_root])
    await db.execute(
        f"UPDATE movies SET {', '.join(sets)} WHERE folder_levels=? AND media_root=?",
        values
    )
    await db.commit()
    logger.info(f"Edited {len(sets)-1} fields for folder {folder_levels}")
    return {"ok": True}


async def delete_folder_movies(folder_levels: str, media_root: str) -> dict:
    from .database import get_db
    from .config import logger

    if not media_root:
        return {"ok": False, "error": "media_root required"}
    db = await get_db()
    cur = await db.execute("SELECT id FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    rows = await cur.fetchall()
    count = len(rows)
    for r in rows:
        await db.execute("DELETE FROM tags WHERE movie_id=?", (r["id"],))
    await db.execute("DELETE FROM movies WHERE folder_levels=? AND media_root=?", (folder_levels, media_root))
    await db.commit()
    logger.info(f"Deleted {count} movies from folder {folder_levels}")
    return {"ok": True, "deleted": count}
