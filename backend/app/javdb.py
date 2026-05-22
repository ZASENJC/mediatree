import json
import re
import time
import asyncio
from datetime import datetime, timedelta
from html import unescape
import httpx
from .config import settings, logger
from .database import get_db

_last_request = 0.0
_req_lock = asyncio.Lock()
_javdb_client: httpx.AsyncClient | None = None
_javdb_semaphore = asyncio.Semaphore(max(1, settings.scraper_api_concurrency))


def _clean_html_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


async def _rate_limit():
    global _last_request
    async with _req_lock:
        now = time.monotonic()
        wait = settings.javdb_request_interval - (now - _last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request = time.monotonic()


async def _get_client() -> httpx.AsyncClient:
    global _javdb_client
    if _javdb_client is not None and not _javdb_client.is_closed:
        return _javdb_client
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    _javdb_client = httpx.AsyncClient(
        headers=headers,
        timeout=settings.scraper_http_timeout,
        follow_redirects=True,
    )
    return _javdb_client


async def _get_cached(code: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT data, fetched_at FROM javdb_cache WHERE code=?", (code,))
    row = await cur.fetchone()
    if not row:
        return None
    fetched = datetime.fromisoformat(row["fetched_at"])
    if datetime.now() - fetched > timedelta(hours=settings.javdb_cache_hours):
        return None
    try:
        return json.loads(row["data"])
    except (json.JSONDecodeError, TypeError):
        return None


async def _set_cache(code: str, data: dict):
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO javdb_cache (code, data, fetched_at) VALUES (?, ?, datetime('now'))",
        (code, json.dumps(data, ensure_ascii=False))
    )
    await db.commit()


def _parse_movie_page(html: str, page_url: str) -> dict:
    result = {"javdb_url": page_url}

    def _labeled_single(label: str) -> str | None:
        pat = re.compile(
            rf"(?is)<(?:p|div|li)[^>]*>\s*<b[^>]*>[^<]*{re.escape(label)}[^<]*</b>\s*[:\-–]?\s*(.*?)</(?:p|div|li)>"
        )
        m = pat.search(html)
        if not m:
            return None
        block = m.group(1)
        block = re.split(r"<b[^>]*>.*?</b>", block, maxsplit=1)[0]
        block = re.sub(r"(?is)<br\s*/?>", "\n", block)
        first_line = next((ln for ln in block.splitlines() if ln.strip()), "")
        return _clean_html_text(first_line)

    def _labeled_links(label: str) -> list[str]:
        pat = re.compile(
            rf"(?is)<(?:p|div|li)[^>]*>[^<]*<b[^>]*>[^<]*{re.escape(label)}[^<]*</b>(.*?)</(?:p|div|li)>"
        )
        vals = []
        for m in pat.finditer(html):
            block = m.group(1)
            for a in re.findall(r"<a[^>]*>(.*?)</a>", block, flags=re.I | re.S):
                txt = _clean_html_text(a)
                if txt:
                    vals.append(txt)
        return vals

    title_m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if title_m:
        result["title"] = _clean_html_text(title_m.group(1))

    result["dvd_id"] = _labeled_single("DVD ID")

    date_str = _labeled_single("Release Date")
    if date_str:
        date_m = re.search(r"\d{4}-\d{2}-\d{2}", date_str)
        if date_m:
            result["release_date"] = date_m.group()

    runtime_str = _labeled_single("Runtime")
    if runtime_str:
        m = re.search(r"(\d+)", runtime_str)
        if m:
            result["duration"] = int(m.group(1))

    result["studio"] = _labeled_single("Studio")

    genres = set(_labeled_links("Genre"))
    if genres:
        result["genre"] = ", ".join(sorted(genres))

    actresses = set(_labeled_links("Idol"))
    if actresses:
        result["actress"] = ", ".join(sorted(actresses))

    result["director"] = _labeled_single("Director")
    result["series"] = _labeled_single("Series")

    # Rating: count rating_on.png stars from the entire page
    on_count = len(re.findall(r'rating_on\.png', html))
    half_count = len(re.findall(r'rating_half\.png', html))
    if on_count > 0 or half_count > 0:
        result["javdb_score"] = float(on_count) + float(half_count) * 0.5
    # Find votes in post-ratings section
    rblock = re.search(r'(?is)<div[^>]*id="post-ratings[^"]*".*?</div>\s*</div>', html)
    if rblock:
        rtext = re.sub(r'<[^>]+>', ' ', rblock.group(0))
        rtext = re.sub(r'\s+', ' ', rtext).strip()
        votes_m = re.search(r'(\d[\d,]*)\s*(?:votes|vote)', rtext, re.I)
        if votes_m:
            result["javdb_likes"] = int(votes_m.group(1).replace(",", ""))

    # Poster
    poster_m = re.search(r"(?is)<div[^>]+id=\"poster-container\"[^>]*>(.*?)</div>", html)
    if poster_m:
        img_m = re.search(r"<img[^>]+src=\"([^\"]+)\"", poster_m.group(1), flags=re.I)
        if img_m:
            result["cover_remote"] = img_m.group(1)
    if not result.get("cover_remote"):
        img_m = re.search(
            r"(?is)<div[^>]+class=\"[^\"]*\bposter\b[^\"]*\"[^>]*>.*?<img[^>]+src=\"([^\"]+)\"",
            html,
        )
        if img_m:
            result["cover_remote"] = img_m.group(1)

    # Preview thumbnails
    thumbs = []
    anchor_pat = re.compile(r"(?is)<a([^>]*data-image-(?:src|href)=\"[^\"]+\"[^>]*)>")
    for attrs_str in anchor_pat.findall(html):
        full_m = re.search(r"data-image-(?:src|href)=\"([^\"]+)\"", attrs_str, flags=re.I)
        if full_m:
            thumbs.append(full_m.group(1))
        else:
            prev_m = re.search(r"data-image-src=\"([^\"]+)\"", attrs_str, flags=re.I)
            if prev_m:
                thumbs.append(prev_m.group(1))
    if thumbs:
        result["javdb_thumbnails"] = json.dumps(thumbs[:16], ensure_ascii=False)

    # Comments from "About" section
    about_m = re.search(
        r"(?is)<h[1-6][^>]*>[^<]*About[^<]*JAV Movie[^<]*</h[1-6]>(.*?)(?:<h[1-6]|<div[^>]+class=\"[^\"]*\bcomments\b)",
        html,
    )
    if about_m:
        text = re.sub(r"<[^>]+>", " ", about_m.group(1))
        from html import unescape
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if text and len(text) > 10:
            result["overview"] = text
            result["javdb_comments"] = [text]

    return result


def _jav_code_variants(code: str) -> list[str]:
    """Generate fuzzy search variants for a JAV code.

    Returns alternative search strings to try when exact match fails.
    """
    variants = []
    normalized = code.upper().strip()

    # Variant 1: without dash (SSNI-888 → SSNI888)
    if '-' in normalized:
        no_dash = normalized.replace('-', '')
        if no_dash != normalized:
            variants.append(no_dash)

    # Variant 2: prefix/letters only (SSNI-888 → SSNI) for series search
    match = re.match(r'^([A-Z]+)', normalized)
    if match:
        prefix = match.group(1)
        if len(prefix) >= 2 and prefix != normalized:
            variants.append(prefix)

    return variants


async def search_javdb(code: str) -> dict | None:
    if not settings.javdb_enabled or not code:
        return None

    cached = await _get_cached(code)
    if cached is not None:
        logger.info(f"Javdatabase cache hit: code={code}")
        return cached or None

    try:
        client = await _get_client()
        await _rate_limit()
        search_url = f"{settings.javdb_base_url}/?post_type=movies%2Cuncensored&s={code}"
        logger.info(f"Javdatabase search endpoint: /?post_type=movies,uncensored code={code}")
        async with _javdb_semaphore:
            resp = await client.get(search_url)
        resp.raise_for_status()
        html = resp.text

        card_pat = re.compile(
            r"(?is)<div[^>]+class=\"[^\"]*\bcard\b[^\"]*\bborderlesscard\b[^\"]*\"[^>]*>(.*?)</div>"
        )
        found_url = None
        for m in card_pat.finditer(html):
            block = m.group(1)
            link_m = re.search(r"(?is)<a[^>]+href=\"(/movies/[^\"]+)\"[^>]*>(.*?)</a>", block)
            if link_m:
                link = link_m.group(1)
                link_code = _clean_html_text(link_m.group(2))
                if code.upper() in link_code.upper():
                    found_url = f"{settings.javdb_base_url}{link}"
                    break
                if not found_url:
                    found_url = f"{settings.javdb_base_url}{link}"

        # Fallback: try direct URL by lowercased code
        if not found_url:
            direct_url = f"{settings.javdb_base_url}/movies/{code.lower()}/"
            async with _javdb_semaphore:
                resp2 = await client.get(direct_url)
            if resp2.status_code == 200 and len(resp2.text) > 5000:
                found_url = direct_url
                html = resp2.text

        if not found_url:
            # ── Fuzzy search fallback ──────────────────────────
            for variant in _jav_code_variants(code):
                logger.info(f"Javdatabase fuzzy search: trying '{variant}' for '{code}'")

                # Check variant cache first
                variant_cached = await _get_cached(variant)
                if variant_cached is not None:
                    await _set_cache(code, variant_cached)
                    return variant_cached or None

                # Try direct URL with variant
                fuzzy_direct = f"{settings.javdb_base_url}/movies/{variant.lower()}/"
                async with _javdb_semaphore:
                    fuzzy_resp = await client.get(fuzzy_direct)
                if fuzzy_resp.status_code == 200 and len(fuzzy_resp.text) > 5000:
                    found_url = fuzzy_direct
                    html = fuzzy_resp.text
                    break

                # Try search page with variant
                await _rate_limit()
                fuzzy_search = f"{settings.javdb_base_url}/?post_type=movies%2Cuncensored&s={variant}"
                async with _javdb_semaphore:
                    fuzzy_resp = await client.get(fuzzy_search)
                fuzzy_resp.raise_for_status()
                fuzzy_html = fuzzy_resp.text

                # For series/prefix search, pick result closest to original number
                orig_num_m = re.search(r'(\d{2,6})', code)
                orig_num = int(orig_num_m.group(1)) if orig_num_m else 0

                best_url = None
                best_diff = float('inf')

                fuzzy_card_pat = re.compile(
                    r"(?is)<div[^>]+class=\"[^\"]*\bcard\b[^\"]*\bborderlesscard\b[^\"]*\"[^>]*>(.*?)</div>"
                )
                for fm in fuzzy_card_pat.finditer(fuzzy_html):
                    block = fm.group(1)
                    link_m = re.search(r"(?is)<a[^>]+href=\"(/movies/[^\"]+)\"[^>]*>(.*?)</a>", block)
                    if link_m:
                        link = link_m.group(1)
                        link_code = _clean_html_text(link_m.group(2))
                        code_num_m = re.search(r'(\d{2,6})', link_code)
                        if code_num_m:
                            code_num = int(code_num_m.group(1))
                            diff = abs(code_num - orig_num)
                            if diff < best_diff:
                                best_diff = diff
                                best_url = f"{settings.javdb_base_url}{link}"

                if best_url:
                    found_url = best_url
                    break

            if not found_url:
                await _set_cache(code, {})
                return None

        if not found_url.endswith("/"):
            found_url += "/"

        if "/movies/" not in html or len(html) < 5000:
            await _rate_limit()
            async with _javdb_semaphore:
                detail_resp = await client.get(found_url)
            detail_resp.raise_for_status()
            html = detail_resp.text

        result = _parse_movie_page(html, found_url)
        await _set_cache(code, result)
        return result
    except httpx.HTTPStatusError as e:
        logger.warning(f"Javdatabase HTTP error for '{code}': status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"Javdatabase search error for '{code}': {e}")
        return None


async def batch_fetch_metadata(codes: list[str], progress_callback=None):
    results = {}
    total = len(codes)
    db = await get_db()
    for i, code in enumerate(codes):
        data = await search_javdb(code)
        if data:
            results[code] = data
            try:
                await db.execute(
                    """UPDATE movies SET title=COALESCE(NULLIF(?, ''), title),
                       actress=COALESCE(NULLIF(?, ''), actress),
                       release_date=COALESCE(NULLIF(?, ''), release_date),
                       duration=COALESCE(?, duration),
                       javdb_url=COALESCE(NULLIF(?, ''), javdb_url),
                       javdb_score=COALESCE(?, javdb_score),
                       javdb_likes=COALESCE(?, javdb_likes),
                       javdb_thumbnails=COALESCE(NULLIF(?, ''), javdb_thumbnails),
                       cover_remote=COALESCE(NULLIF(?, ''), cover_remote),
                       updated_at=datetime('now')
                       WHERE code=?""",
                    (data.get("title", ""), data.get("actress", ""),
                     data.get("release_date", ""), data.get("duration"),
                     data.get("javdb_url", ""), data.get("javdb_score"),
                     data.get("javdb_likes"), data.get("javdb_thumbnails"),
                     data.get("cover_remote", ""), code)
                )
                await db.commit()
            except Exception:
                pass
        if progress_callback:
            progress_callback(i + 1, total)
        if i < total - 1:
            await asyncio.sleep(0.5)
    return results
