# 設定

MediaTree は環境変数と実行時設定を組み合わせて使います。環境変数はデプロイ単位の設定に向いており、Settings ページはライブラリ、スクレイパー、UI 設定に向いています。

## 認証

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `AUTH_USER` | `""` | 管理者ユーザー名。空のままにすると初回起動時に管理者アカウントを作成します。 |
| `AUTH_PASS` | `""` | 管理者パスワード。認証を有効にする場合は強いパスワードを使ってください。 |

認証シークレットは環境変数からのみ読み込まれ、`data/config.json` には保存されません。

## メディアとデータ

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `MEDIA_ROOT` | `/media` | コンテナ内のメディアルート。 |
| `DATA_DIR` | `../data` | 永続データディレクトリ。 |
| `SCAN_ON_STARTUP` | `true` | コンテナ起動時にスキャンします。 |
| `FILE_WATCHER_ENABLED` | `true` | ファイル監視と自動スキャンを有効にします。 |

複数ライブラリを使う場合は、複数のフォルダを `/media/*` 配下にマウントし、Settings で各ライブラリを設定します。

## スクレイパー設定

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `TMDB_ACCESS_TOKEN` | `""` | TMDB v4 Read Access Token。推奨です。 |
| `SCRAPE_CONCURRENCY_PER_LIBRARY` | `8` | ライブラリごとの最大同時スクレイプ数。 |
| `SCRAPE_GLOBAL_CONCURRENCY` | `16` | 全体の最大同時スクレイプ数。 |
| `SCRAPER_API_CONCURRENCY` | `8` | 外部 API リクエストの最大同時数。 |
| `SCRAPER_HTTP_TIMEOUT` | `10.0` | 外部 HTTP タイムアウト秒数。 |

Javdatabase は組み込みスクレイパープラグインとして提供されます。使用するには Settings で対象ライブラリに `Javdatabase` を選択します。キャッシュ TTL と Javdatabase のリクエスト間隔は内部ポリシーであり、ユーザー設定としては公開していません。手動スキャン、再スクレイプ、手動適用はキャッシュをバイパスします。

## 実行時設定

以下は Settings ページで管理され、`data/config.json` に保存されます。

- ライブラリパス、スクレイパー、パスワード。
- TMDB Read Access Token。
- ホームタイトル非表示、アンビエントモード、元ファイル名表示などの UI 設定。
- バックアップ、復元、更新、字幕フォント。

## TMDB Read Access Token の取得

1. [TMDB](https://www.themoviedb.org/) に登録またはログインします。
2. [API Settings](https://www.themoviedb.org/settings/api) を開きます。
3. v4 Read Access Token を生成します。
4. `.env` に `TMDB_ACCESS_TOKEN` を設定するか、Settings → Scrapers で `TMDB Read Access Token` を入力します。

TMDB 認証情報がなくても MediaTree はスキャンと再生ができますが、メタデータと画像は制限されます。
