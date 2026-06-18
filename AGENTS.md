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

## Product Collaboration Rules

- Treat the user as a product manager with no programming background: translate natural-language requests into product goals, user workflows, and acceptance criteria before choosing the technical implementation.
- Do not require the user to provide technical terminology. When a request is vague, first infer the likely product intent from the repository context, state the interpretation in Chinese, and ask only the minimum necessary clarification if implementation would otherwise be risky.
- Before every code change, read the current project guidance (`AGENTS.md`, `CLAUDE.md`, and any task-relevant docs) so implementation stays aligned with product constraints, release policy, and local conventions.
- When a change is committed, keep the normative docs updated in the same commit whenever the change affects product behavior, architecture, workflows, release/update policy, or future agent instructions.

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

Default Docker builds are size-optimized. Keep `INCLUDE_FULL_CJK_FONTS=false` and `INCLUDE_EMOJI_FONT=false` unless a release explicitly needs the full Noto CJK or emoji font packages; the default image keeps `fonts-wqy-microhei` plus the bundled frontend subtitle fallback font. If full Noto fonts are enabled or Dockerfile/runtime font policy changes, treat the release as a full Docker image update.

Application update packages must be built with `scripts/build-app-package.sh`. Do not reintroduce inline release-workflow packaging logic; the shared builder strips bytecode, pycache, source maps, and local metadata before creating the release archive.

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
- Before each code change, read the current project guidance (`AGENTS.md`, `CLAUDE.md`, and any task-relevant docs).
- Before each push, sync `CLAUDE.md`, `AGENTS.md`, `CHANGELOG.md`, and `README.md` to reflect the current code state.
- Include any required normative-document updates in the same commit as the implementation they describe.
- `docker-compose.yml`, `.env`, `data/`, `frontend/node_modules/`, and `frontend/dist/` are local/runtime artifacts.
- Do not revert unrelated changes.

## Scraper Plugin Management

- Settings 的“插件管理”同时管理内置刮削器和用户上传插件。
- 停用内置刮削器会让它从 `/api/scrapers`、媒体库下拉选项和运行时 registry 中消失，但仍保留在插件管理中，可重新启用。
- 删除内置刮削器只会在当前配置中隐藏该内置项，不删除应用自带代码；仍在使用该内置项的媒体库会回退到当前可用默认刮削器。用户上传插件删除才会移除运行时安装目录，且上传插件被媒体库使用时仍禁止删除。
- 如果变更影响刮削器可用性，保持 `scraper_plugins.py`、`scrapers/registry.py`、`database._valid_scraper()` 和设置页展示一致。

## Update Release Policy

- App-package updates and full Docker image updates share one version baseline. When either side reaches a version, subsequent update comparisons must continue from the higher installed version instead of the currently running layer alone.
- Unless the user explicitly overrides it, automatically choose the release/update path before push or release work:
  - Use `app-package` when the change is limited to application code or built frontend assets and does not require a new base image/runtime layer.
  - Use full Docker image update when the change touches the runtime/base image surface, including Dockerfile, system packages, Python version or pinned dependency layer, ffmpeg/fonts, container user/permissions, entrypoint/bootstrap behavior, Docker self-update prerequisites, or any change that cannot be delivered safely by replacing only the app package.
- Ordinary pushes must not run the release workflow. Trigger `.github/workflows/release-tag.yml` manually only when performing an app-package or full Docker image release.
- Keep build artifacts small by default: app-package releases use `scripts/build-app-package.sh`; DockerHub pushes use `scripts/push-docker-release.sh` with the default font build args unless the release notes call out a runtime-font requirement.
- Every release must refresh DockerHub `zasenjc/mediatree:latest` so new Docker installs start from the newest application baseline. Do this from a local build/push with `scripts/push-docker-release.sh`, not GitHub Actions. App-package releases publish only `latest`; full Docker image releases publish both `zasenjc/mediatree:<version>` and `latest`.
- Keep GitHub Release notes user-facing: write concise functional changes and upgrade guidance for users there, and put implementation details, configuration changes, test notes, and maintainer bookkeeping in `CHANGELOG.md` / `CHANGELOG_zh-CN.md`.
- When the chosen path is full Docker image update, keep Settings/release messaging aligned so users are guided to host-side `docker compose pull && docker compose up -d` when in-container image replacement is unavailable.
