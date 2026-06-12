# リリースポリシー

MediaTree は通常コミット、アプリパッケージ更新、完全 Docker イメージ更新を区別します。

## 通常コミット

通常の push でリリースを公開してはいけません。現在の release workflow は `workflow_dispatch` の手動実行専用なので、通常コミットはタグ、GitHub Releases、DockerHub を変更しません。

## アプリパッケージ更新

変更がアプリコード、ビルド済みフロントエンド、ドキュメント、またはベース実行レイヤーを変更しない挙動に限られる場合は、アプリパッケージ更新を使います。

アプリパッケージリリースは次を生成します。

- `mediatree-app-<version>.tar.gz`
- `mediatree-app-<version>.manifest.json`
- `mediatree-app-<version>.sha256`

メンテナーは DockerHub の `zasenjc/mediatree:latest` もローカルで更新し、新規インストールが最新のアプリケーション基準から始まるようにします。

## 完全 Docker イメージ更新

次の場合は完全イメージ更新を使います。

- Dockerfile、システムパッケージ、Python バージョン、依存レイヤーの変更。
- ffmpeg、フォント、実行時バイナリの変更。
- コンテナユーザー、権限、entrypoint、起動処理の変更。
- アプリパッケージの差し替えだけでは安全に配布できない変更。

完全イメージ更新では、バージョンタグと `latest` の両方を公開します。

## ドキュメントサイトのデプロイ

ドキュメントサイトは `.github/workflows/docs-pages.yml` により GitHub Pages へデプロイされます。この workflow は `docs-site` だけをビルドし、GitHub Releases の作成、DockerHub 更新、アプリパッケージバージョン変更は行いません。

## リリース前チェック

公開前に確認します。

- バックエンドテストが通る。
- バックエンドがコンパイルできる。
- フロントエンドがビルドできる。
- Docs と README が現在の挙動と一致している。
- `git diff` に意図した変更だけが含まれている。
