# ECC for Codex CLI

This supplements `CLAUDE.md` with Codex-specific guidance for this repository.

## Project Scope

- This repository is the full MediaTree web/backend project.
- Backend code lives under `backend/app/` and uses FastAPI, SQLite, ffmpeg/ffprobe, and scraper integrations.
- Frontend code lives under `frontend/` and uses React 18, TypeScript, Vite, Tailwind, ArtPlayer, and Capacitor.
- Keep user-facing explanations, plans, summaries, questions, and change reports in Chinese.
- Keep code identifiers, file names, paths, commands, config keys, API routes, function names, class names, and logs in their original English.

## Model Recommendations

| Task Type | Recommended Model |
|-----------|------------------|
| Routine coding, tests, formatting | GPT 5.4 |
| Complex features, architecture | GPT 5.4 |
| Debugging, refactoring | GPT 5.4 |
| Security review | GPT 5.4 |

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
docker buildx build --platform linux/amd64,linux/arm64 -t zasenjc/mediatree:1.0.00 --push .
```

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
- Every release must refresh DockerHub `zasenjc/mediatree:latest` so new Docker installs start from the newest application baseline. App-package releases publish only `latest`; full Docker image releases publish both `zasenjc/mediatree:<version>` and `latest`.
- When the chosen path is full Docker image update, keep Settings/release messaging aligned so users are guided to host-side `docker compose pull && docker compose up -d` when in-container image replacement is unavailable.
