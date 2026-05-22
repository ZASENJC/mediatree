"""
Title matching and search query utilities extracted from scanner.py.

Pure functions for cleaning titles, extracting patterns, building search queries,
and matching scraped results against folder/file names.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .scrapers.base import ScrapeCandidate

# ── Regex patterns ──────────────────────────────────────────────────────────

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
SEASON_PATTERN = re.compile(r'^(S|Season\s*|第)\s*\d{1,2}$', re.I)
LEADING_BRACKET_GROUP_PATTERN = re.compile(r"^\[[A-Za-z0-9\-_. ]{2,30}\]\s*")

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
STANDALONE_EPISODE_NUMBER_PATTERN = re.compile(r"(?<![a-zA-Z0-9_\u4e00-\u9fff\u3040-\u30ff])\b\d{1,3}\b(?!\d)")
GENERIC_SEARCH_QUERY_PATTERN = re.compile(r"(?i)^(?:s\s*\d{1,2}|e\s*\d{1,3}|ep\s*\d{1,3}|\d{1,3}|\d{3,4}p|ma\s*10|ma10p)$")
TRAILING_RELEASE_GROUP_PATTERN = re.compile(
    r'(?i)\s*[-–—@]\s*(?:[A-Z0-9]{2,10}|'
    r'[A-Z][a-z]*[A-Z][a-z]{0,10}(?:HD|Studio|Web|TV|Team|Group|Raw|Team|Sub)s?|'
    r'(?:[A-Z][a-z]*){1,2}HD|'
    r'mn?hd|cmctv|mp4ba|frds|sonyhd|batweb|byndr|qhstudio)\s*$'
)
SKIP_DIRS = {".DS_Store", "__MACOSX", "Thumbs.db", ".Trashes"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".webm", ".mpg", ".mpeg"}


# ── Dataclass ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TmdbIdToken:
    id: int
    media_type: Literal["movie", "tv"] | None
    raw: str
    source_name: str
    confidence: Literal["explicit", "unknown"]


# ── TMDB ID extraction ─────────────────────────────────────────────────────

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


def _first_tmdb_token(candidate_names: list[str], default_label: str = "candidate") -> TmdbIdToken | None:
    for idx, candidate in enumerate(candidate_names):
        label = ["folder", "parent", "filename", "title", "code", "search"][idx] if idx < 6 else default_label
        token = extract_tmdb_token_from_name(candidate or "", label)
        if token:
            return token
    return None


# ── Code extraction ─────────────────────────────────────────────────────────

def extract_code(name: str) -> str | None:
    match = CODE_PATTERN.search(name)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    match = CODE_PATTERN_UNDERSCORE.search(name)
    if match:
        return f"{match.group(1).upper()}-{match.group(2)}"
    return None


# ── Name cleaning ───────────────────────────────────────────────────────────

def remove_tmdb_id_token(name: str) -> str:
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


def generate_folder_identifier(folder_name: str) -> str:
    folder_name = remove_tmdb_id_token(folder_name)
    clean = re.sub(r'[\(\[\{][^\)\]\}]*[\)\]\}]', '', folder_name)
    clean = re.sub(r'\d{3,4}p', '', clean)
    clean = re.sub(r'[._\-]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean or folder_name.strip()


# ── CJK / Alpha / Romaji extraction ────────────────────────────────────────

def extract_cjk(text: str) -> str:
    return ''.join(c for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')


def extract_alpha(text: str) -> str:
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    return ''.join(c for c in text if c.isascii() and (c.isalpha() or c in "' ")).strip().lower()


def extract_romaji(text: str) -> str:
    t = text.replace('\u2019', "'").replace('\u2018', "'")
    return ' '.join(w.lower() for w in re.findall(r"[a-zA-Z'']{2,}", t))


# ── Title matching ──────────────────────────────────────────────────────────

def title_matches(scraped_title: str, folder_name: str, code: str | None = None) -> bool:
    """Multi-strategy title matching between scraped and local names."""
    if not scraped_title:
        return False

    s_clean = clean_folder_name(scraped_title)
    f_clean = clean_folder_name(folder_name)
    if not s_clean or not f_clean:
        return False

    # Exact match
    if s_clean == f_clean:
        return True
    # Substring match (length >= 4)
    if len(s_clean) >= 4 and len(f_clean) >= 4:
        if s_clean in f_clean or f_clean in s_clean:
            return True

    # CJK character matching
    s_cjk = extract_cjk(scraped_title)
    f_cjk = extract_cjk(folder_name)
    if s_cjk and f_cjk and len(s_cjk) >= 2 and len(f_cjk) >= 2:
        if s_cjk == f_cjk or s_cjk in f_cjk or f_cjk in s_cjk:
            return True

    # Romaji matching
    s_romaji = extract_romaji(scraped_title)
    f_romaji = extract_romaji(folder_name)
    if s_romaji and f_romaji and len(s_romaji) >= 3 and len(f_romaji) >= 3:
        if s_romaji == f_romaji or s_romaji in f_romaji or f_romaji in s_romaji:
            return True

    # Alpha token intersection
    s_alpha = extract_alpha(scraped_title)
    f_alpha = extract_alpha(folder_name)
    if s_alpha and f_alpha and len(s_alpha) >= 4 and len(f_alpha) >= 4:
        if s_alpha == f_alpha or s_alpha in f_alpha or f_alpha in s_alpha:
            return True
        stopwords = {"the", "a", "an", "of", "and", "or", "to", "in"}
        s_tokens = {w for w in s_alpha.split() if len(w) > 1 and w not in stopwords}
        f_tokens = {w for w in f_alpha.split() if len(w) > 1 and w not in stopwords}
        if s_tokens and f_tokens:
            overlap = len(s_tokens & f_tokens)
            smaller = min(len(s_tokens), len(f_tokens))
            if smaller >= 2 and overlap / smaller >= 0.75:
                return True

    if code:
        if code.upper() in scraped_title.upper():
            return True
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


# ── Search query building ───────────────────────────────────────────────────

def _strip_search_noise(value: str) -> str:
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
    if not clean or clean == name:
        return []
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


# ── Helper predicates ───────────────────────────────────────────────────────

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


def _meaningful_local_metadata(raw) -> bool:
    import json as _json
    if not raw or raw == "{}":
        return False
    metadata = raw
    if isinstance(raw, str):
        try:
            metadata = _json.loads(raw)
        except (_json.JSONDecodeError, TypeError):
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


# ── Media type inference ────────────────────────────────────────────────────

def _count_video_files_in_dir(path: str) -> tuple[int, bool]:
    try:
        folder = Path(path).parent
        files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    except OSError:
        return 0, False
    names = " ".join(p.stem for p in files)
    has_episode_pattern = bool(EPISODE_HINT_PATTERN.search(names))
    return len(files), has_episode_pattern


def _local_metadata(movie: dict) -> dict:
    import json
    raw = movie.get("local_metadata") if movie else None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


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
