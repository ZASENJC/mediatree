# 開発ガイド

## プロジェクト構成

```text
mediatree/
├── backend/               # Python 3.12 + FastAPI
│   ├── app/
│   │   ├── main.py        # FastAPI app and route handlers
│   │   ├── scanner.py     # scanning and scraping engine
│   │   ├── database.py    # SQLite CRUD
│   │   ├── config.py      # pydantic-settings + JSON persistence
│   │   ├── stream.py      # video stream, Range, transcoding
│   │   ├── subtitles.py   # subtitle detection and conversion
│   │   └── scrapers/      # scraper plugin system
│   └── tests/
├── frontend/              # React 18 + TypeScript + Vite
├── docs-site/             # VitePress documentation site
└── Dockerfile
```

## ローカル開発

本番環境ではバックエンドがビルド済みフロントエンドを配信します。開発時は通常 2 つのプロセスを起動します。

```bash
# Backend
cd backend
pip install -r requirements.txt -c constraints.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# Frontend
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to `localhost:80`.

## ドキュメントサイト開発

```bash
cd docs-site
npm ci
npm run dev
```

ビルド:

```bash
cd docs-site
npm run build
```

ドキュメントサイトは GitHub Pages の `/mediatree/` にデプロイされます。ドキュメントのデプロイ workflow は、アプリパッケージのリリース公開とは分離してください。

## テストとビルド

```bash
cd backend && PYTHONPATH=. python3.11 -m unittest discover -s tests -p 'test_*.py'
python3.11 -m compileall -q backend/app
cd frontend && npm run build
```

macOS ではローカルの `python3` が古いバージョンを指す場合があります。Python 3.11 以上を優先してください。本番イメージは Python 3.12 を使います。

## API を追加する

1. `backend/app/main.py` に route を追加します。
2. 永続化が必要な場合は `backend/app/database.py` に CRUD を追加します。
3. `frontend/src/api.ts` に型付きフロントエンドクライアントメソッドを追加します。
4. ページまたはコンポーネントから利用し、テストを追加します。

## スクレイパーを追加する

ユーザーがインストールできるスクレイパーは、`plugin.json` と `BaseScraper` を継承する Python entry class を含む `.zip` plugin package として作成します。package structure、manifest fields、install/enable flow、test checklist は中国語版の [Scraper Plugin Guide](/development/scraper-plugin-guide) にまとめています。

built-in scrapers を保守する場合は、`backend/app/builtin_plugins/scrapers/<name>/plugin.json` と `plugin.py` で manifest-driven registry に接続します。共有する core logic は引き続き `backend/app/scrapers/` に置けます。
