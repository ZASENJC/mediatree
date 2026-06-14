# 外部クライアント

MediaTree の主な入口は Web アプリですが、外部プレイヤー再生やクライアント接続にも対応しています。

## 外部プレイヤー

作品詳細ページから、VLC、IINA、mpv などで使える外部再生リンクと M3U プレイリストを生成できます。

典型的な URL 形式:

```text
http://your-server:27580/api/external-play/{movie_id}.m3u
```

これらのリンクは短命のメディアアクセストークンを使うため、アプリの認可なしにメディアファイルが露出しません。

## Android クライアント

単体 Android クライアントは [ZASENJC/mediatree-app](https://github.com/ZASENJC/mediatree-app) にあります。MediaTree に接続できるほか、Jellyfin、Emby、SMB、WebDAV の独立クライアントとしても使えます。

MediaTree に接続する場合は、次のようなサーバー URL を使います。

```text
http://192.168.1.10:27580
```

自宅ネットワーク外からアクセスする場合は、先にリバースプロキシ、HTTPS、強いパスワードを設定してください。

## Jellyfin / Emby について

MediaTree は外部プレイヤー用プレイリストを生成できますが、完全な Jellyfin/Emby 互換サーバーではありません。ネイティブプロトコルが必要な場合は Jellyfin または Emby サーバーを使ってください。
