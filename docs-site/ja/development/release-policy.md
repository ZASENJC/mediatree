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

アプリパッケージは必ず `scripts/build-app-package.sh` で作成します。GitHub Actions やローカルリリース手順で別の打包ロジックを重複させないでください。共有ビルダーは bytecode、`__pycache__`、source map、ローカルメタデータを除去し、安定した圧縮設定でアーカイブを生成します。

## 完全 Docker イメージ更新

次の場合は完全イメージ更新を使います。

- Dockerfile、システムパッケージ、Python バージョン、依存レイヤーの変更。
- ffmpeg、フォント、実行時バイナリの変更。
- コンテナユーザー、権限、entrypoint、起動処理の変更。
- アプリパッケージの差し替えだけでは安全に配布できない変更。

完全イメージ更新では、バージョンタグと `latest` の両方を公開します。

Docker ビルドは既定で軽量構成を維持します。完全な `fonts-noto-cjk` と `fonts-noto-color-emoji` は含めず、`fonts-wqy-microhei` とフロントエンド同梱の字幕フォールバックフォントを使います。リリースで完全な Noto CJK または絵文字フォントが明示的に必要な場合だけ、ローカルビルドで `INCLUDE_FULL_CJK_FONTS=true` または `INCLUDE_EMOJI_FONT=true` を設定します。これらの引数を有効化する場合や Dockerfile/runtime のフォント方針を変更する場合は、完全 Docker イメージ更新として扱います。

## ドキュメントサイトのデプロイ

ドキュメントサイトは `.github/workflows/docs-pages.yml` により GitHub Pages へデプロイされます。この workflow は `docs-site` だけをビルドし、GitHub Releases の作成、DockerHub 更新、アプリパッケージバージョン変更は行いません。

## リリース前チェック

公開前に確認します。

- バックエンドテストが通る。
- バックエンドがコンパイルできる。
- フロントエンドがビルドできる。
- Docs と README が現在の挙動と一致している。
- アプリパッケージは `scripts/build-app-package.sh` で生成し、Docker イメージは完全フォントが明示的に必要な場合を除いて `scripts/push-docker-release.sh` の軽量既定値で構築する。
- `git diff` に意図した変更だけが含まれている。
