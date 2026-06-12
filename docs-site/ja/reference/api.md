# API Reference

MediaTree の API は主に Web フロントエンドと外部再生リンクのために提供されています。ヘルスチェック、ログイン、初回セットアップを除き、`/api/*` にはアプリ認証が必要です。

## 認証

| Method | Path | 説明 |
| --- | --- | --- |
| `POST` | `/api/auth/login` | サインインしてセッショントークンを受け取ります。 |
| `POST` | `/api/auth/setup` | 最初の管理者アカウントを作成します。 |
| `GET` | `/api/auth/status` | 認証とセットアップ状態を取得します。 |
| `POST` | `/api/auth/change-password` | 管理者パスワードを変更します。 |
| `POST` | `/api/media-token` | 短命のメディアアクセストークンを取得します。 |

## ライブラリとスキャン

| Method | Path | 説明 |
| --- | --- | --- |
| `GET` | `/api/health` | ヘルスチェック。 |
| `GET` | `/api/scan` | スキャンを開始します。 |
| `GET` | `/api/scan/status` | スキャン状態を取得します。 |
| `GET` | `/api/scan/log` | スキャンログを取得します。 |
| `GET` | `/api/media-roots` | メディアルート一覧を取得します。 |
| `GET` | `/api/library-settings` | ライブラリ設定を取得します。 |
| `POST` | `/api/library-settings` | ライブラリ設定を保存します。 |
| `POST` | `/api/library/clear` | ライブラリデータを消去します。 |

## ブラウズと詳細

| Method | Path | 説明 |
| --- | --- | --- |
| `GET` | `/api/folders` | フォルダツリーとフォルダ単位のメタデータを取得します。 |
| `GET` | `/api/movies` | 作品一覧を取得します。 |
| `GET` | `/api/search` | 作品を検索します。 |
| `GET` | `/api/favorites` | お気に入り一覧を取得します。 |
| `GET` | `/api/detail/{movie_id}` | 作品詳細を取得します。 |
| `GET` | `/api/recent-watched` | 続きから見る項目を取得します。 |
| `GET` | `/api/categories` | カテゴリ一覧を取得します。 |
| `POST` | `/api/categories` | カテゴリを作成します。 |
| `PUT` | `/api/categories/{cat_id}` | カテゴリを更新します。 |
| `DELETE` | `/api/categories/{cat_id}` | カテゴリを削除します。 |

## 再生、字幕、メディアファイル

| Method | Path | 説明 |
| --- | --- | --- |
| `GET` | `/api/stream/{movie_id}` | Range とフォールバックトランスコード付きで動画をストリームします。 |
| `GET` | `/api/media-info/{movie_id}` | メディア情報を取得します。 |
| `GET` | `/api/external-play/{movie_id}.m3u` | 外部プレイヤー用プレイリストを生成します。 |
| `GET` | `/api/subtitle-tracks/{movie_id}` | 字幕トラック一覧を取得します。 |
| `GET` | `/api/subtitle/{movie_id}/{track_index}` | Web 字幕を取得します。 |
| `GET` | `/api/subtitle-file/{movie_id}/{track_index}/{filename}` | 字幕ファイルを取得します。 |
| `GET` | `/api/media/{file_path}` | メディアファイルパスを読み出します。 |

## カバーと画像

| Method | Path | 説明 |
| --- | --- | --- |
| `GET` | `/api/cover/{movie_id}` | 作品カバーを取得します。 |
| `GET` | `/api/cached-cover/{cache_key}` | キャッシュ済みカバーを取得します。 |
| `GET` | `/api/episode-still/{movie_id}` | エピソード画像を取得します。 |
| `GET` | `/api/thumbnail/{movie_id}/{index}` | サムネイルを取得します。 |
| `POST` | `/api/movies/{movie_id}/cover` | 作品カバーを変更します。 |
| `POST` | `/api/folder/cover` | フォルダカバーを変更します。 |
| `POST` | `/api/folder/backdrop` | フォルダ背景を変更します。 |

## スクレイピングとメタデータ

| Method | Path | 説明 |
| --- | --- | --- |
| `POST` | `/api/movies/{movie_id}/rescrape` | 作品を再スクレイプします。 |
| `POST` | `/api/movies/{movie_id}/manual-scrape` | 手動スクレイプ結果を作品に適用します。 |
| `POST` | `/api/rescrape-folder` | フォルダを再スクレイプします。 |
| `POST` | `/api/search-scrape` | スクレイプ候補を検索します。 |
| `POST` | `/api/apply-folder-scrape` | フォルダのスクレイプ結果を適用します。 |
| `POST` | `/api/javdb/fetch` | コードから Javdatabase 情報を取得します。 |

## 更新、バックアップ、設定

| Method | Path | 説明 |
| --- | --- | --- |
| `GET` | `/api/config` | 実行時設定を取得します。 |
| `POST` | `/api/config` | 実行時設定を保存します。 |
| `GET` | `/api/backup` | バックアップをダウンロードします。 |
| `POST` | `/api/restore` | バックアップから復元します。 |
| `POST` | `/api/restore/upload` | バックアップをアップロードして復元します。 |
| `GET` | `/api/version` | 現在バージョンと実行レイヤー情報を取得します。 |
| `GET` | `/api/update/check` | 利用可能な更新を確認します。 |
| `POST` | `/api/update/perform` | 更新を実行します。 |
| `GET` | `/api/update/status` | 更新状態を取得します。 |
| `POST` | `/api/update/rollback` | アプリパッケージ更新をロールバックします。 |
| `GET` | `/api/update/changelog` | バージョン変更履歴を取得します。 |

## 利用ガイド

サードパーティクライアントは、安定したブラウズ機能と再生機能を優先し、フロントエンド内部フィールドへ依存しないでください。認証、メディアトークン、復元、更新、ファイルパス系エンドポイントは高リスク領域です。呼び出す前に明確な権限境界を定義してください。
