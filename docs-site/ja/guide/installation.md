# インストール

## 前提条件

- Docker と Docker Compose。
- 動画、字幕、カバー画像を置いたフォルダ。
- データベース、カバーキャッシュ、フォント、アプリパッケージ更新用に 1 GB 以上の空き容量。

## クイックスタート

### 1. 設定ファイルを準備する

公開済みイメージをそのまま使うか、リポジトリを clone してサンプル設定をコピーします。

```bash
git clone https://github.com/ZASENJC/mediatree.git
cd mediatree
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
```

`.env` と `docker-compose.yml` を編集します。最低限、管理者アカウント、データディレクトリ、メディアのマウントを設定してください。

### 2. 最小構成の docker-compose.yml

```yaml
services:
  mediatree:
    image: zasenjc/mediatree:latest
    container_name: mediatree
    restart: unless-stopped
    ports:
      - "27580:80"
    volumes:
      - ./data:/app/data
      - /path/to/your/movies:/media/movies:ro
    environment:
      - AUTH_USER=admin
      - AUTH_PASS=change-me
      - PORT=80
      - SCAN_ON_STARTUP=true
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:80/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

メディアフォルダは読み取り専用でマウントします。例: `/host/movies:/media/movies:ro`。MediaTree はデータベース、カバー、設定、フォント、バックアップ、アプリパッケージ更新を `./data` に保存します。

### 3. 起動する

```bash
docker compose up -d
```

`http://localhost:27580` を開きます。`AUTH_USER` / `AUTH_PASS` を事前設定していない場合、初回起動時に管理者アカウントの作成を求められます。

## 対応プラットフォーム

- `linux/amd64`
- `linux/arm64`

## よくある起動トラブル

### データディレクトリの権限

コンテナは非 root ユーザーで動作します。`./data` に書き込めない場合は、ホスト側で権限を調整します。

```bash
mkdir -p ./data
sudo chown -R 1000:1000 ./data
chmod 755 ./data
```

### ポート競合

`27580` がすでに使われている場合は、ポートマッピングの左側を変更します。

```yaml
ports:
  - "3000:80"
```

その後、`http://localhost:3000` を開きます。

### 字幕フォント

標準の Docker イメージには WenQuanYi Micro Hei が含まれ、イメージサイズを抑えるためにフロントエンド側の Source Han Sans フォールバックフォントも同梱しています。完全な Noto CJK や emoji フォントが必要なカスタムビルドでは `INCLUDE_FULL_CJK_FONTS=true` または `INCLUDE_EMOJI_FONT=true` を指定してください。Settings からカスタム字幕フォントをアップロードすることもできます。
