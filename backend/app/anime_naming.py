from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


LANGUAGE_TAGS = {
    "zh", "chs", "cht", "sc", "tc", "chi", "cn", "hans", "hant",
    "zh-cn", "zh-tw", "ja", "jp", "jpn", "en", "eng",
}

_LANGUAGE_SUFFIX_RE = re.compile(
    r"(?i)(?:\.(?:zh-cn|zh-tw|chs|cht|sc|tc|chi|hans|hant|zh|cn|ja|jp|jpn|en|eng))+$"
)
_LEADING_GROUP_RE = re.compile(r"^\s*[\[【\(（][^\]】\)）]{1,80}[\]】\)）]\s*")
_BRACKET_RE = re.compile(r"[\[【\(（]([^\]】\)）]{1,120})[\]】\)）]")
_SXXEXX_RE = re.compile(r"(?i)\bS\d{1,3}\s*[-_. ]?\s*E(\d{1,4})(?:[-_. ]\d{2,4})?\b")
_ONE_X_RE = re.compile(r"(?i)\b\d{1,3}x(\d{1,4})\b")
_EP_RE = re.compile(r"(?i)\bEP(?:ISODE)?\s*[-_. ]?(\d{1,4})\b")
_E_RE = re.compile(r"(?i)(?:^|[\s._-])E(\d{1,4})(?:$|[\s._-])")
_E_DOUBLE_RE = re.compile(r"(?i)(?:^|[\s._-])E(\d{1,4})[-_.]?(\d{1,4})\b")
_CN_EP_RE = re.compile(r"第\s*(\d{1,4})\s*[集話话]")
_HASH_EP_RE = re.compile(r"[#＃]\s*(\d{1,4})\b")
_VOL_RE = re.compile(r"(?i)\bV[Oo][Ll]\.?\s*(\d{1,3})\b")


def _compact_tag(value: str) -> str:
    return re.sub(r"[\s._+\-]+", "", (value or "").lower())


_TECH_EXACT = {
    "720p", "1080p", "2160p", "4320p", "4k", "8k",
    "bdrip", "bluray", "webdl", "webrip", "web", "hdtv", "baha", "cr",
    "amzn", "amazon", "netflix", "nf", "bglobal",
    "ma10p1080p", "ma10p", "hi10p",
    "hevc", "avc", "av1", "h264", "h265", "x264", "x265",
    "aac", "flac", "opus", "ddp", "eac3", "ac3", "dts", "truehd",
    "aacavc", "hevcaac", "x265flac", "x264aac", "x265aac",
    "10bit", "8bit", "12bit",
}


def is_language_tag(value: str) -> bool:
    return (value or "").strip().lower() in LANGUAGE_TAGS


def is_year_token(value: str) -> bool:
    try:
        year = int((value or "").strip())
    except ValueError:
        return False
    return 1888 <= year <= 2099


def is_technical_tag(value: str) -> bool:
    raw = (value or "").strip()
    compact = _compact_tag(raw)
    if not compact:
        return False
    if compact in _TECH_EXACT:
        return True
    if re.fullmatch(r"(?:ma|hi)?\d{1,2}p\d{3,4}p", compact):
        return True
    if re.fullmatch(r"\d{3,4}p", compact):
        return True
    if re.fullmatch(r"(?:8|10|12)bit", compact):
        return True
    if re.fullmatch(r"x26[45](?:aac|flac|opus|ac3|eac3|dts)?", compact):
        return True
    if re.fullmatch(r"(?:aac|flac|opus|ddp|eac3|ac3|dts|truehd){1,3}", compact):
        return True
    if re.fullmatch(r"(?:hevc|avc|av1|h264|h265)(?:aac|flac|opus|ac3|eac3)?", compact):
        return True
    return False


def strip_known_extension(name: str) -> str:
    path = Path(name)
    if path.suffix:
        return path.stem
    return name


def strip_language_suffix(stem: str) -> str:
    return _LANGUAGE_SUFFIX_RE.sub("", stem or "")


def strip_release_group(stem: str) -> str:
    return _LEADING_GROUP_RE.sub("", stem or "", count=1).strip()


def _parse_episode_token(token: str) -> int | None:
    value = (token or "").strip()
    if not value or is_technical_tag(value) or is_year_token(value):
        return None
    if re.fullmatch(r"\d{1,4}", value):
        num = int(value)
        return num if 0 < num < 10000 else None
    for pattern in (
        r"(?i)^EP(?:ISODE)?\s*[-_. ]?(\d{1,4})$",
        r"(?i)^E\s*[-_. ]?(\d{1,4})$",
        r"^第\s*(\d{1,4})\s*[集話话]$",
        r"(?i)^V[Oo][Ll]\.?\s*(\d{1,3})$",
    ):
        match = re.match(pattern, value)
        if match:
            num = int(match.group(1))
            return num if 0 < num < 10000 else None
    return None


def extract_episode_number(name: str) -> int | None:
    stem = strip_language_suffix(strip_known_extension(name))
    text = strip_release_group(stem)
    for pattern in (_SXXEXX_RE, _ONE_X_RE, _EP_RE, _E_DOUBLE_RE, _E_RE, _CN_EP_RE, _HASH_EP_RE, _VOL_RE):
        match = pattern.search(text)
        if match:
            num = int(match.group(1))
            if 0 < num < 10000:
                return num

    candidates: list[tuple[int, int]] = []
    for match in _BRACKET_RE.finditer(text):
        token = match.group(1)
        num = _parse_episode_token(token)
        if num is None:
            continue
        before = text[:match.start()].strip(" -_.")
        after = text[match.end():]
        next_bracket = _BRACKET_RE.search(after)
        next_is_tech = bool(next_bracket and is_technical_tag(next_bracket.group(1)))
        score = 50
        if before:
            score += 20
        if next_is_tech:
            score += 20
        candidates.append((score, num))
    if candidates:
        return sorted(candidates, key=lambda item: -item[0])[0][1]
    return None


def episode_label(episode: int | None) -> str:
    if episode is None:
        return ""
    return f"EP{episode:02d}" if episode < 100 else f"EP{episode}"


def clean_anime_title(name: str) -> str:
    stem = strip_language_suffix(strip_known_extension(name))
    text = strip_release_group(stem)

    def replace_bracket(match: re.Match) -> str:
        token = match.group(1)
        if _parse_episode_token(token) is not None or is_technical_tag(token) or is_language_tag(token) or is_year_token(token):
            return " "
        return f" {token} "

    text = _BRACKET_RE.sub(replace_bracket, text)
    text = _SXXEXX_RE.sub(" ", text)
    text = _ONE_X_RE.sub(" ", text)
    text = _EP_RE.sub(" ", text)
    text = _E_DOUBLE_RE.sub(" ", text)
    text = _E_RE.sub(" ", text)
    text = _CN_EP_RE.sub(" ", text)
    text = _HASH_EP_RE.sub(" ", text)
    text = _VOL_RE.sub(" ", text)
    text = re.sub(
        r"(?i)\b(?:720p|1080p|2160p|4320p|4k|8k|bdrip|bluray|web-dl|webdl|webrip|"
        r"hevc|avc|h\.?264|h\.?265|x264|x265|aac|flac|opus|ddp|eac3|ac3|dts|"
        r"10bit|8bit|12bit|ma10p)\b",
        " ",
        text,
    )
    text = re.sub(r"[\u3000\t]+", " ", text)
    text = re.sub(r"[._]+", " ", text)
    text = re.sub(r"\s*[-–—]+\s*$", " ", text)
    text = re.sub(r"^\s*[-–—]+\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_[](){}【】（）")
    return text


def normalize_title_key(name: str) -> str:
    title = clean_anime_title(name)
    title = title.lower()
    title = re.sub(r"[\[\]【】()（）{}]", " ", title)
    title = re.sub(r"[\s._\-–—:：,，、]+", " ", title)
    return re.sub(r"\s+", " ", title).strip()


@dataclass(frozen=True)
class AnimeNameInfo:
    clean_title: str
    episode: int | None
    episode_label: str
    display_title: str

    @property
    def is_episode(self) -> bool:
        return self.episode is not None

    def as_dict(self) -> dict:
        return {
            "clean_title": self.clean_title,
            "episode": self.episode,
            "episode_label": self.episode_label,
            "display_title": self.display_title,
        }


def parse_anime_filename(name: str) -> AnimeNameInfo:
    title = clean_anime_title(name)
    episode = extract_episode_number(name)
    label = episode_label(episode)
    display = f"{title} - {label}" if title and label else title
    return AnimeNameInfo(title, episode, label, display)
