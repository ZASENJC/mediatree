#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
PYTHONPATH=. python3.11 -m unittest discover -s tests -p 'test_*.py'

cd "$ROOT_DIR"
python3.11 -m compileall -q backend/app

cd "$ROOT_DIR/frontend"
npm run build
