# MediaTree 架构拆分整理规划

本规划用于当前会话内的前后端结构优化。目标是降低大文件耦合和后续改动风险，不改变现有用户可见行为、不触碰 release/push/外部发布流程。

## 固定约束

- 保持 `sp` 特殊集、AC3 自动转码、播放页标题、手动刮削绕过缓存、更新/release 策略等现有行为不变。
- 每一步只拆一个清晰边界，优先移动代码和补导入，不做顺手重写。
- 后端每步至少运行相关 `unittest`；触碰公共 API、认证、恢复、媒体流时运行安全回归测试。
- 前端每步至少运行 `cd frontend && npm run build`。
- 不提交、不 push，除非用户明确要求。
- 如遇未预期的用户改动，保留并绕开；不使用 reset/checkout 回退。

## 阶段 0：基线与文档

- 创建本规划文件，作为本会话拆分顺序依据。
- 记录每阶段的目标、验证命令和完成条件。
- 验证：`git status --short` 确认只出现预期文件。

## 阶段 1：后端认证与媒体访问边界

目标：把 `backend/app/main.py` 顶部的认证中间件、session token、media token 和媒体路由访问判断拆到独立模块，后续路由拆分时可以复用。

建议文件：

- `backend/app/security.py`

允许改动：

- 从 `main.py` 移出 `AuthMiddleware`、`MEDIA_TOKEN_TTL_SECONDS`、`AUTH_SESSION_TTL_SECONDS`、`MEDIA_ROUTE_PREFIXES`、`_has_app_auth`、`_has_media_access`、`_require_media_access`、token 签发/校验函数。
- `main.py` 只保留导入和路由调用。

验证：

```bash
cd backend && PYTHONPATH=. python3.11 -m unittest tests.test_security_regressions
python3.11 -m compileall -q backend/app
```

完成条件：

- 认证、媒体 token、媒体流访问测试全部通过。
- `main.py` 路由行为不变。

## 阶段 2：后端 Auth / Update / Backup Router 拆分

目标：把低耦合路由从 `main.py` 迁出，形成 `APIRouter` 结构。

建议文件：

- `backend/app/routers/__init__.py`
- `backend/app/routers/auth.py`
- `backend/app/routers/update.py`
- `backend/app/routers/backup.py`

顺序：

1. Auth routes：`/api/auth/*`、`/api/media-token`、`/api/setup/status` 中只依赖认证状态的部分。
2. Update routes：`/api/version`、`/api/update/*`。
3. Backup/restore routes：`/api/backup`、`/api/restore*`，保留安全测试。

验证：

```bash
cd backend && PYTHONPATH=. python3.11 -m unittest tests.test_security_regressions tests.test_updater_versions tests.test_entrypoint_version_choice
python3.11 -m compileall -q backend/app
```

完成条件：

- `main.py` 明显减少路由职责。
- 高风险 restore/update/auth 测试通过。

## 阶段 3：后端 Media / Subtitle Router 拆分

目标：把媒体流、封面、缩略图、字幕、字体路由迁出，保持媒体 token 访问模型不变。

建议文件：

- `backend/app/routers/media.py`
- `backend/app/routers/subtitles.py`

验证：

```bash
cd backend && PYTHONPATH=. python3.11 -m unittest tests.test_security_regressions tests.test_subtitles tests.test_continue_watching
python3.11 -m compileall -q backend/app
```

完成条件：

- `_require_media_access` 只从 `security.py` 使用。
- 流媒体、字幕、字体路由行为不变。

## 阶段 4：前端播放器纯工具与 Hook 拆分

目标：先从 `VideoPlayer.tsx` 抽纯函数和 hooks，避免直接重写播放器生命周期。

建议文件：

- `frontend/src/player/subtitles.ts`
- `frontend/src/player/gesture.ts`
- `frontend/src/player/useAmbientColor.ts`
- `frontend/src/player/usePlaybackTitle.ts`
- `frontend/src/player/EpisodeMenu.tsx`

顺序：

1. 抽字幕/VTT/ASS 字体纯工具。
2. 抽手势绑定函数。
3. 抽环境光和剧院尺寸 hooks。
4. 最后抽可视组件。

验证：

```bash
cd frontend && npm run build
```

完成条件：

- `VideoPlayer.tsx` 行数下降，播放、字幕、转码、选集导入路径清晰。
- build 通过。

## 阶段 5：前端 API 客户端拆分

目标：把 `api.ts` 拆成 session、URL 解析、request client、类型和 endpoint 分组。

建议文件：

- `frontend/src/api/session.ts`
- `frontend/src/api/client.ts`
- `frontend/src/api/mediaUrls.ts`
- `frontend/src/api/types.ts`
- `frontend/src/api/endpoints.ts`
- `frontend/src/api/index.ts`

验证：

```bash
cd frontend && npm run build
```

完成条件：

- 现有 `import { api, type Movie } from '../api'` 仍可工作。
- Android/Capacitor server URL 行为不变。

## 阶段 6：后端数据库与扫描服务拆分

目标：拆最大、风险最高的业务模块，只在前面边界稳定后执行。

建议文件：

- `backend/app/db/connection.py`
- `backend/app/db/migrations.py`
- `backend/app/repositories/movies.py`
- `backend/app/repositories/libraries.py`
- `backend/app/services/scanning.py`
- `backend/app/services/scraping.py`
- `backend/app/services/folders.py`

验证：

```bash
cd backend && PYTHONPATH=. python3.11 -m unittest discover -s tests -p 'test_*.py'
python3.11 -m compileall -q backend/app
```

完成条件：

- `database.py` 和 `scanner.py` 不再是所有领域逻辑的聚合点。
- 全量后端测试通过。

## 阶段 7：工具链补强

目标：补低侵入质量检查，不在本轮进行大格式化。

候选：

- 前端增加 `lint`。
- 后端增加 `pyproject.toml` / `ruff` 基础配置。
- 只启用不会触发大规模风格改写的规则。

验证：

```bash
cd frontend && npm run build
cd backend && PYTHONPATH=. python3.11 -m unittest discover -s tests -p 'test_*.py'
```

完成条件：

- 后续拆分有稳定检查入口。
- 没有无关格式化噪音。

## 当前执行记录

- 阶段 0：已创建本规划文件。
- 阶段 1：已拆出 `backend/app/security.py`。
- 阶段 2：已拆出 `backend/app/routers/auth.py`、`backend/app/routers/update.py`、`backend/app/routers/backup.py`。
- 阶段 3：已拆出 `backend/app/routers/subtitles.py`、`backend/app/routers/media.py`。
- 阶段 4：已拆出播放器字幕工具、手势绑定、环境光/影院尺寸/标题 hooks、`EpisodeMenu`。
- 阶段 5：已拆出 `frontend/src/api/` 下的 `session.ts`、`client.ts`、`mediaUrls.ts`、`types.ts`、`endpoints.ts`，顶层 `frontend/src/api.ts` 保持兼容导出。
- 阶段 6：已拆出 `backend/app/db/migrations.py` 和 `backend/app/services/folders.py`，保留 `database.py` / `scanner.py` 的公共入口。
- 阶段 7：已新增 `scripts/check-local.sh` 作为本地综合检查入口。
