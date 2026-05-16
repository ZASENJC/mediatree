import os
import subprocess
import json
from pathlib import Path
from fastapi import Request, Query
from fastapi.responses import StreamingResponse, Response

MIME_MAP = {
    ".mp4": "video/mp4",
    ".mkv": "video/webm",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".m4v": "video/mp4",
    ".ts": "video/mp2t",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
}

BROWSER_SAFE = {"h264", "hevc", "h265", "avc1", "vp9", "av1", "vp8"}


def _probe_codec(file_path: str) -> str:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-select_streams", "v:0", file_path],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(r.stdout)
        for s in data.get("streams", []):
            codec = (s.get("codec_name") or "").lower()
            if codec:
                return codec
    except Exception:
        pass
    return ""


def get_video_stream(path: str, request: Request):
    file_path = Path(path)
    if not file_path.exists():
        return Response(status_code=404, content="File not found")

    ext = file_path.suffix.lower()
    content_type = MIME_MAP.get(ext, "video/mp4")
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")

    codec = _probe_codec(str(file_path)) if ext in (".mkv", ".webm") else "h264"
    decode_mode = request.query_params.get("decode", "") if hasattr(request, 'query_params') else ""
    need_transcode = False
    if codec and codec not in BROWSER_SAFE:
        need_transcode = True
    if decode_mode == "1":
        need_transcode = True
    if decode_mode == "0":
        need_transcode = False

    if need_transcode:
        return _transcode_stream(file_path, content_type, range_header)

    if not range_header:
        def iterfile():
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(8192 * 1024)
                    if not data:
                        break
                    yield data
        return StreamingResponse(
            iterfile(),
            headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size), "Content-Type": content_type},
            media_type=content_type
        )

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
        iterfile(),
        status_code=206,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": content_type,
        },
        media_type=content_type
    )


def _transcode_stream(file_path: Path, content_type: str, range_header: str | None = None) -> StreamingResponse:
    args = [
        "ffmpeg", "-y",
        "-i", str(file_path),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "mp4", "-"
    ]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def iter_transcode():
        try:
            while True:
                data = proc.stdout.read(8192 * 1024)
                if not data:
                    break
                yield data
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                proc.kill()

    return StreamingResponse(iter_transcode(), media_type="video/mp4")
