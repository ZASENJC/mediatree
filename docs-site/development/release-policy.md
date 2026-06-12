# 发布规则

MediaTree 发布分为普通提交、应用包更新和完整 Docker 镜像更新。

## 普通提交

普通 push 不应触发 release 发布。当前 release workflow 只允许手动 `workflow_dispatch`，避免普通提交误改 tag、GitHub Release 或 DockerHub。

## 应用包更新

当变更只涉及应用代码、前端构建产物、文档或不需要修改基础运行层的行为时，使用应用包更新。

应用包发布会生成：

- `mediatree-app-<version>.tar.gz`
- `mediatree-app-<version>.manifest.json`
- `mediatree-app-<version>.sha256`

维护者发布应用包时，需要本地刷新 DockerHub `zasenjc/mediatree:latest`，让新安装用户获得最新应用基线。

## 完整 Docker 镜像更新

以下变更需要完整镜像更新：

- Dockerfile、系统包、Python 版本或依赖层变化。
- ffmpeg、字体或运行时二进制变化。
- 容器用户、权限、entrypoint、bootstrap 行为变化。
- 任何不能通过替换应用包安全交付的变更。

完整镜像更新应同时发布版本 tag 和 `latest`。

## 文档站发布

文档站通过 `.github/workflows/docs-pages.yml` 部署到 GitHub Pages。它只构建 `docs-site`，不创建 GitHub Release，不更新 DockerHub，也不修改应用包版本。

## 发布前检查

发布前至少确认：

- 后端测试通过。
- 后端可编译。
- 前端构建通过。
- 文档和 README 与当前行为一致。
- `git diff` 只包含本次范围内的变更。
