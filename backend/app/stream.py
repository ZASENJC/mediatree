import subprocess
import json
import os
import signal
import time
import threading
from pathlib import Path
from fastapi import Request
from fastapi.responses import StreamingResponse, Response

MIME_MAP = {
    ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".webm": "video/webm",
    ".avi": "video/x-msvideo", ".mov": "video/quicktime", ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv", ".m4v": "video/mp4", ".ts": "video/mp2t",
    ".mpg": "video/mpeg", ".mpeg": "video/mpeg",
    ".ogv": "video/ogg", ".ogm": "video/ogg", ".divx": "video/x-msvideo",
    ".rmvb": "application/vnd.rn-realmedia", ".rm": "application/vnd.rn-realmedia",
    ".asf": "video/x-ms-asf", ".3gp": "video/3gpp", ".3g2": "video/3gpp2",
}


PROBE_CACHE_TTL = 30.0
_probe_cache_lock = threading.Lock()
_probe_cache: dict[str, tuple[float, dict]] = {}


def _cached_probe(file_path: str) -> dict:
    now = time.monotonic()
    stat_mtime = os.path.getmtime(file_path)
    cache_key = f"{file_path}:{stat_mtime}"
    with _probe_cache_lock:
        cached = _probe_cache.get(cache_key)
        if cached and now - cached[0] < PROBE_CACHE_TTL:
            return dict(cached[1])
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", file_path],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(r.stdout)
    except Exception:
        data = {}
    with _probe_cache_lock:
        _probe_cache[cache_key] = (now, data)
        if len(_probe_cache) > 128:
            oldest = min(_probe_cache.items(), key=lambda item: item[1][0])[0]
            _probe_cache.pop(oldest, None)
    return dict(data)


def _probe_duration(file_path: str) -> float:
    try:
        data = _cached_probe(file_path)
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def get_media_info(path: str) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {"duration": 0, "video_codec": "", "audio_codec": ""}
    try:
        data = _cached_probe(str(file_path))
        video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
        return {
            "duration": float(data.get("format", {}).get("duration") or 0),
            "video_codec": video.get("codec_name", ""),
            "audio_codec": audio.get("codec_name", ""),
            "audio_channels": audio.get("channels", 0),
            "container": file_path.suffix.lower().lstrip("."),
        }
    except Exception:
        return {"duration": 0, "video_codec": "", "audio_codec": "", "audio_channels": 0, "container": file_path.suffix.lower().lstrip(".")}


def get_video_stream(path: str, request: Request):
    file_path = Path(path)
    if not file_path.exists():
        return Response(status_code=404, content="File not found")

    ext = file_path.suffix.lower()
    content_type = MIME_MAP.get(ext, "video/mp4")
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    transcode_mode = request.query_params.get("transcode", "")

    if transcode_mode:
        try:
            start = max(0.0, float(request.query_params.get("start", "0") or 0))
        except ValueError:
            start = 0.0
        mode = "full" if transcode_mode == "full" else "audio"
        return _transcode_stream(file_path, start=start, mode=mode)

    if not range_header:
        return _full_stream(file_path, content_type, file_size)

    return _range_stream(file_path, content_type, file_size, range_header)


def _full_stream(file_path: Path, content_type: str, file_size: int):
    def iterfile():
        with open(file_path, "rb") as f:
            while True:
                data = f.read(8192 * 1024)
                if not data:
                    break
                yield data
    return StreamingResponse(
        iterfile(),
        headers={
            "Accept-Ranges": "bytes", "Content-Length": str(file_size),
            "Content-Type": content_type, "Access-Control-Allow-Origin": "*",
        },
        media_type=content_type
    )


def _range_stream(file_path: Path, content_type: str, file_size: int, range_header: str):
    start_str = range_header.replace("bytes=", "").split("-")[0]
    start = int(start_str)
    end = file_size - 1
    parts = range_header.replace("bytes=", "").split("-")
    if len(parts) > 1 and parts[1]:
        end = int(parts[1])
    if start >= file_size:
        return Response(status_code=416)
    chunk_size = end - start + 1

    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                data = f.read(min(8192 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iterfile(), status_code=206,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes", "Content-Length": str(chunk_size),
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Range, Content-Type",
            "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length",
        },
        media_type=content_type
    )


def _transcode_stream(file_path: Path, start: float = 0.0, mode: str = "audio"):
    total_duration = _probe_duration(str(file_path))
    args = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-fflags", "+genpts", "-analyzeduration", "100M", "-probesize", "100M", "-y"]
    if start > 0:
        args.extend(["-ss", f"{start:.3f}"])
    args.extend(["-i", str(file_path), "-map", "0:v:0", "-map", "0:a:0?", "-sn"])
    if mode == "full":
        args.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"])
    else:
        args.extend(["-c:v", "copy"])
    args.extend([
        "-c:a", "aac", "-b:a", "192k", "-ac", "2",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof+faststart",
        "-flush_packets", "1",
        "-f", "mp4", "-"
    ])
    proc = None
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        raise

    def _kill_proc():
        nonlocal proc
        if proc is None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def iter_transcode():
        try:
            while True:
                if proc.stdout is None:
                    break
                data = proc.stdout.read(1024 * 1024)
                if not data:
                    break
                yield data
        finally:
            _kill_proc()

    headers = {
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-store",
        "Content-Type": "video/mp4",
    }
    if total_duration:
        headers["X-Content-Duration"] = str(total_duration)
    headers["X-Transcode-Start"] = str(start)
    headers["X-Transcode-Mode"] = mode

    return StreamingResponse(iter_transcode(), media_type="video/mp4", headers=headers)
