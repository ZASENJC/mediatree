import re
from pathlib import Path
from xml.etree import ElementTree as ET

COVER_NAMES = {"poster.jpg", "poster.png", "cover.jpg", "cover.png", "folder.jpg", "folder.png",
               "movie-poster.jpg", "movie-poster.png", "season-poster.jpg", "season-poster.png",
               "banner.jpg", "banner.png", "fanart.jpg", "fanart.png", "backdrop.jpg", "backdrop.png"}
NFO_NAMES = {"movie.nfo", "tvshow.nfo"}
SKIP_DIRS = {".DS_Store", "__MACOSX", "Thumbs.db", ".Trashes"}

SPECIAL_DIR_NAMES = {
    "sp",
    "sps",
    "special",
    "specials",
    "extra",
    "extras",
    "bonus",
    "bonuses",
    "featurette",
    "featurettes",
    "behind the scenes",
    "cm",
    "cms",
    "menu",
    "menus",
    "ncop",
    "nced",
    "pv",
    "pvs",
    "映像特典",
    "特典",
    "花絮",
}


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


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
        parser = ET.XMLParser(resolve_entities=False)
        tree = ET.parse(filepath, parser=parser)
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


def detect_special_parent_levels(folder_levels: str) -> str | None:
    parts = [part.strip() for part in folder_levels.replace("\\", "/").split("/") if part.strip() and part.strip() != "."]
    for index, part in enumerate(parts):
        if part.lower() in SPECIAL_DIR_NAMES:
            return "/".join(parts[:index])
    return None
