# ECC for Codex CLI

This supplements `CLAUDE.md` with Codex-specific guidance for this repository.

## Project Scope

- This repository is the full MediaTree web/backend project.
- Backend code lives under `backend/app/` and uses FastAPI, SQLite, ffmpeg/ffprobe, and scraper integrations.
- Frontend code lives under `frontend/` and uses React 18, TypeScript, Vite, Tailwind, ArtPlayer, and Capacitor.
- Media under nested `sp` folders is treated as folder-level specials: keep it out of normal listings, scraping, continue watching, and player episode queues unless a specials-specific path is being changed.
- Browser playback compatibility includes automatic AC3 transcoding; preserve this behavior when touching stream or player capability code.
- Playback pages update the browser tab title with `▶` / `⏸` and the current media title while the user stays on the page; restore the site title only when leaving playback.
- Scraper cache TTLs and Javdatabase request spacing are internal backend policy: do not re-expose them as Settings/environment configuration. Manual scans, rescrapes, and manual apply paths must bypass scraper cache.
- Keep user-facing explanations, plans, summaries, questions, and change reports in Chinese.
- Keep code identifiers, file names, paths, commands, config keys, API routes, function names, class names, and logs in their original English.

## Model Recommendations

| Task Type | Recommended Model |
|-----------|------------------|
| Routine coding, tests, formatting | GPT 5.5 |
| Complex features, architecture | GPT 5.5 |
| Debugging, refactoring | GPT 5.5 |
| Security review | GPT 5.5 |

## Skills Discovery

Project skills are available from `.agents/skills/`. Each installed skill contains:

- `SKILL.md` - detailed instructions and workflow
- `agents/openai.yaml` - Codex interface metadata, when provided by ECC

Installed skills:

- `tdd-workflow` - test-driven development with 80%+ coverage expectations
- `security-review` - security checklist and threat review
- `coding-standards` - universal coding standards
- `frontend-patterns` - React/Next.js/frontend patterns
- `frontend-slides` - viewport-safe HTML presentations and PPTX-to-web conversion
- `article-writing` - long-form writing from notes and voice references
- `content-engine` - platform-native social content and repurposing
- `market-research` - source-attributed market and competitor research
- `investor-materials` - decks, memos, models, and one-pagers
- `investor-outreach` - personalized investor outreach and follow-ups
- `backend-patterns` - API design, database, caching
- `e2e-testing` - Playwright E2E tests
- `eval-harness` - eval-driven development
- `strategic-compact` - context management
- `api-design` - REST API design patterns
- `verification-loop` - build, test, lint, typecheck, security
- `deep-research` - multi-source research
- `exa-search` - neural search via Exa MCP
- `x-api` - X/Twitter API integration
- `crosspost` - multi-platform content distribution
- `fal-ai-media` - AI image/video/audio generation via fal.ai
- `dmux-workflows` - multi-agent orchestration

`claude-api` was listed in the upstream ECC inventory but is not present in the local user-level ECC install used to initialize this repo. A placeholder is kept at `.agents/skills/claude-api/` so future installs can fill it without ambiguity.

## MCP Servers

Treat project-local `.codex/config.toml` as the Codex baseline for this repo. The baseline enables multi-agent support and declares the standard ECC MCP server entries used by this project:

- GitHub
- Context7
- Exa
- Memory
- Playwright
- Sequential Thinking
- Supabase

The canonical Context7 section name is `[mcp_servers.context7]`. The launcher package remains `@upstash/context7-mcp`; only the TOML section name is normalized for consistency with `codex mcp list` and the ECC reference config.

Keep networked tools read-only by default. Search, inspect, and draft freely within the requested scope, but require explicit user approval before posting, publishing, pushing, merging, opening paid jobs, dispatching remote agents, changing third-party resources, or modifying credentials.

## Multi-Agent Support

Codex multi-agent workflows are enabled in `.codex/config.toml`:

```toml
[features]
multi_agent = true
```

Project-local roles live under `.codex/agents/`:

- `.codex/agents/explorer.toml` - read-only evidence gathering
- `.codex/agents/reviewer.toml` - correctness/security review
- `.codex/agents/docs-researcher.toml` - API and release-note verification

Use agents for bounded parallel review or exploration. Keep implementation ownership clear when delegating edits, and do not let agents revert user-owned changes.

## Commands

### Backend

```bash
cd backend && PYTHONPATH=. python3.11 -m unittest discover -s tests -p 'test_*.py'
python3.11 -m compileall -q backend/app
```

The production image uses Python 3.12. Local `python3` may point to Python 3.9 on macOS and fail on `str | None` syntax, so prefer Python 3.11+ for local checks.

### Frontend

```bash
cd frontend && npm ci --legacy-peer-deps
cd frontend && npm run build
```

### Docker

```bash
docker compose up -d --build
scripts/push-docker-release.sh
```

### Windows Desktop Build

- Treat Mac Codex as the editing, analysis, refactoring, and orchestration environment; treat the Windows host as the source of truth for WinUI runtime behavior, packaging, startup, file paths, permissions, tray/notification behavior, embedded backend behavior, and update UX.
- Windows 构建固定连接本地 `mediatree-windows` 主机：`Administrator@192.168.100.102:22`。
- 远端固定复用目录：`C:\Users\Administrator\Documents\code\mediatree-codex-win-live`。
- Windows 主机上的测试、动态 exe 构建验证和运行冒烟都固定在 `C:\Users\Administrator\Documents\code\mediatree-codex-win-live` 执行；不要为常规验证另建临时源码目录。
- 从 Mac 同步到 Windows 时优先使用 Git/SSH，让 Windows 侧在固定目录内执行 `git fetch`/`git pull` 或检出同一提交；避免用手工复制作为长期流程。若必须临时复制文件，最终仍要用 Git diff 确认源码状态。
- Windows 构建入口固定使用 `packaging/windows/build-windows.ps1`。脚本必须可从项目根或任意当前目录调用、失败返回非 0、输出清晰阶段名，并把产物写入 `dist/windows/`。
- 典型远端构建命令：`ssh mediatree-windows 'cd C:\Users\Administrator\Documents\code\mediatree-codex-win-live; pwsh packaging\windows\build-windows.ps1 -Configuration Release'`。
- 后续 Windows 构建以 `portable` 为主目标，优先验证和交付“一个文件打开就能用”的体验。
- 除非用户明确要求“打包 app”、发布完整 Windows 包、生成 portable/MSIX，常规 Windows 验证不要重新打包；只做固定目录内的动态 exe 构建测试和必要的运行冒烟。
- 除非用户明确要求 MSIX / `.appinstaller`，Windows 构建、验证和交付说明都默认围绕 portable 包展开。
- 不要声称 Windows 专属行为已经修复，除非已经在 Windows 主机上验证，或在汇报中明确标为“仅完成代码级检查，尚未 Windows 验证”。涉及 UI 时保留截图、UI 自动化结果、窗口树、日志或人工验收记录；涉及打包时记录 portable/MSIX 产物路径和关键日志。
- 若用户明确说明“我手动测试就好”，Windows/WinUI 视觉效果以用户手动验收为准；Codex 仍需把改动同步到 Windows、完成构建并启动测试 exe，让用户能直接在 Windows 上查看效果。此场景不要用截图/UI 自动化替代用户验收，也不要阻塞在交互弹窗上；汇报中标明“已启动测试 exe，UI 效果待用户手动验收”。
- Mac 端可先运行通用 backend/frontend 检查；WinUI、`.csproj`、PyInstaller、libmpv、portable zip、MSIX、自动更新、安装器和真实启动冒烟必须在 Windows 环境验证。
- Windows 侧冒烟至少确认 portable 解压后 `MediaTree.Windows.exe` 可启动、主窗口出现、内置后端启动成功、关键页面可访问、日志没有明显 crash；涉及播放器或更新流程时必须覆盖对应路径。
- Windows 设置页更新只保留两种用户路径：`应用包更新` 和 `全量更新`。应用包更新在软件内下载 `mediatree-app-<version>.tar.gz`、替换当前应用包、清理旧包并自动重启本机后端；全量更新只跳转下载新的 Windows 完整包，不显示 Docker/镜像更新说明。
- Windows 端和 Web 端不复用前端：Web 使用 `frontend/` React，Windows 使用 `windows/MediaTree.Windows/` WinUI 原生前端；只有后端 FastAPI / 数据模型 / 业务逻辑应保持复用或迁移一致。
- Win 端前端/UI 任务不得新增、删除或修改后端 API 接口；Windows 项目里的后端代码只用于迁移和适配 Web 端既有后端能力。若 WinUI 功能缺少接口，优先用现有 API/配置路径实现，或先向用户确认 Web 端后端是否需要独立演进。
- 当用户要求“Win 端同步 Web 端更新”时，必须先检查 Web 端新增 UI/交互是否能在 WinUI 原生前端落地：纯 Web UI 改动不会自动进入 Windows；需要用户可见的 Windows 前端特性时，要在 WinUI 中单独适配、构建并验证 portable 包。
- Windows 架构按三层管理：`windows/MediaTree.Windows/` 是独立 WinUI 前端；`backend/app/` 是 Web/Docker/Windows 共享的 MediaTree 后端逻辑，Windows 只通过 `windows_entry.py`、`windows_runtime.py`、打包脚本和环境变量做平台迁移；远程 MediaTree、Jellyfin、Emby 等外部媒体库连接放在 WinUI 的 Provider/媒体源适配层，不复用 `backend/app/jellyfin_compat.py` 这类“MediaTree 后端对外兼容 Jellyfin/Emby 客户端”的代码路径。
- Windows 前端重构优先顺序：先拆分 MediaTree API 客户端和 DTO/服务边界，再建立 Provider contracts 与 `LocalMediaTreeProvider`，随后将页面逐步改为依赖 Provider 接口；远程 MediaTree Provider 优先于 Jellyfin/Emby Provider，因为它最接近现有 MediaTree API 语义。

## Security Without Hooks

Codex does not provide Claude Code hooks in this repo, so enforce security through review and verification:

1. Validate inputs at API, file, and archive boundaries.
2. Never hardcode secrets; use environment variables or ignored local config.
3. Review auth bypass lists carefully before shipping.
4. Run backend tests and frontend build before publishing.
5. Review `git diff` before any push.
6. Treat Docker socket access, restore/upload, self-update, and media streaming as high-risk surfaces.

## Git Hygiene

- Preserve user changes and ignored local files unless the user explicitly asks to remove or reset them.
- Before each push, sync `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`, and `README.md` to reflect the current code state.
- `docker-compose.yml`, `.env`, `data/`, `frontend/node_modules/`, and `frontend/dist/` are local/runtime artifacts.
- Do not revert unrelated changes.

## Update Release Policy

- App-package updates and full Docker image updates share one version baseline. When either side reaches a version, subsequent update comparisons must continue from the higher installed version instead of the currently running layer alone.
- Unless the user explicitly overrides it, automatically choose the release/update path before push or release work:
  - Use `app-package` when the change is limited to application code or built frontend assets and does not require a new base image/runtime layer.
  - Use full Docker image update when the change touches the runtime/base image surface, including Dockerfile, system packages, Python version or pinned dependency layer, ffmpeg/fonts, container user/permissions, entrypoint/bootstrap behavior, Docker self-update prerequisites, or any change that cannot be delivered safely by replacing only the app package.
- For Windows releases, make the same decision as `应用包更新` vs `全量更新` before publishing:
  - Use Windows `应用包更新` only when the Windows-impacting change is limited to shared backend/application code that can run on the existing bundled Python/libmpv/WinUI/PyInstaller runtime, without changing WinUI views, DTO contracts, bundled dependencies, or native/runtime surfaces; keep `requires_windows_base_update: false`.
  - Treat Web React UI changes as Web-only unless the same feature is explicitly implemented in `windows/MediaTree.Windows/`; if a Web UI feature must appear in Windows, adapt it in WinUI and use Windows `全量更新`.
  - Use Windows `全量更新` when the change touches WinUI pages/components, Windows DTO/API consumption, player UI, settings UI, Python dependencies, bundled binaries, ffmpeg/libmpv, PyInstaller packaging, Windows bootstrap/session behavior, or any native/runtime surface; set `requires_windows_base_update: true` and publish a new Windows full package asset.
  - For shared backend changes, check whether Windows API consumers and DTOs still match. If no Windows frontend/native change is needed, app-package can sync the backend; if Windows models/pages must change, ship the backend change together with a Windows full package.
- Every release must refresh DockerHub `zasenjc/mediatree:latest` so new Docker installs start from the newest application baseline. Do this from a local build/push with `scripts/push-docker-release.sh`, not GitHub Actions. App-package releases publish only `latest`; full Docker image releases publish both `zasenjc/mediatree:<version>` and `latest`.
- When the chosen path is full Docker image update, keep Settings/release messaging aligned so users are guided to host-side `docker compose pull && docker compose up -d` when in-container image replacement is unavailable.
