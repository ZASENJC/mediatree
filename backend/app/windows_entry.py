from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from app.windows_runtime import default_base_dir, default_bin_dir, default_data_dir, prepare_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the MediaTree Windows desktop backend.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Windows shell should use 127.0.0.1.")
    parser.add_argument("--port", type=int, required=True, help="Loopback port selected by the Windows shell.")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--base-dir", type=Path, default=default_base_dir())
    parser.add_argument("--bin-dir", type=Path, default=None)
    parser.add_argument("--media-root", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    host = (args.host or "127.0.0.1").strip()
    if host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Windows desktop backend must bind to 127.0.0.1 or localhost.")

    base_dir = args.base_dir.resolve()
    bin_dir = args.bin_dir.resolve() if args.bin_dir else default_bin_dir(base_dir)
    choice = prepare_environment(
        data_dir=args.data_dir,
        base_dir=base_dir,
        bin_dir=bin_dir,
        media_root=args.media_root,
    )
    print(f"Starting MediaTree {choice.version or 'unknown'} from {choice.source} ({choice.app_dir})", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
