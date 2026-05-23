[English](../wiki/Development) | [简体中文](Development)

# 开发指南

## 项目结构

```
mediatree/
├── backend/               # Python 3.12 + FastAPI
│   ├── app/
│   │   ├── main.py        # FastAPI 应用，85+ 路由处理
│   │   ├── scanner.py     # 核心扫描和刮削引擎
│   │   ├── database.py    # SQLite CRUD 操作
│   │   ├── config.py      # pydantic-settings + JSON 持久化
│   │   ├── stream.py      # 视频流（Range、转码）
│   │   ├── subtitles.py   # 字幕检测和转换
│   │   ├── covers.py      # 封面下载和缓存
│   │   ├── watcher.py     # 文件系统监控
│   │   ├── anime_naming.py # 动漫文件名解析器
│   │   ├── tmdb.py        # TMDB API 客户端
│   │   ├── bangumi.py     # Bangumi API 客户端
│   │   ├── javdb.py       # JavDatabase 刮削器
│   │   ├── jellyfin_compat.py  # Jellyfin API 路由
│   │   ├── jellyfin_mappers.py # 数据映射
│   │   ├── jellyfin_auth.py    # Jellyfin 认证
│   │   └── scrapers/      # 刮削器插件系统
│   └── tests/             # 单元测试
│
├── frontend/              # React 18 + TypeScript 5
│   ├── src/
│   │   ├── App.tsx        # 根组件 + 路由 + 导航
│   │   ├── api.ts         # API 客户端（120s TTL 缓存）
│   │   ├── cache.ts       # 响应缓存
│   │   ├── store.ts       # localStorage 偏好设置
│   │   ├── pages/         # 8 个页面组件
│   │   ├── components/    # 16 个可复用组件
│   │   ├── utils/         # 辅助函数（VTT 解析、轮询）
│   │   └── index.css      # 玻璃态设计系统
│   └── public/fonts/      # 内置字体
│
├── data/                  # 运行时数据（gitignored）
├── Dockerfile             # 多阶段构建
├── docker-compose.yml     # Docker 部署
└── .env.example           # 环境变量模板
```

## 本地开发

### 双进程开发模式

生产环境中，后端直接提供构建后的前端页面。开发时，需要分别运行：

```bash
# 终端 1 — 后端（端口 80）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# 终端 2 — 前端（端口 5173）
cd frontend
npm install
npm run dev
```

Vite 开发服务器将 `/api/*` 请求代理到 `localhost:80`（在 `vite.config.ts` 中配置）。

### 运行测试

```bash
# 所有测试
cd backend
python -m unittest discover -s tests -p 'test_*.py'

# 单个测试文件
python -m unittest tests.test_anime_naming

# 指定测试用例
python -m unittest tests.test_scanner_tmdbid.TestSomething.test_method
```

### 构建生产版本

```bash
# 前端构建
cd frontend && npm run build

# 后端语法检查
python -m compileall backend/app

# Docker 多架构构建
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t mediatree:dev .
```

## 架构模式

### 后端

- **单文件路由**：所有 API 路由集中在 `main.py`（~1100 行），没有单独的 router 模块。
- **认证中间件**：`AuthMiddleware` 使用 Basic/Bearer 认证守卫 `/api/*` 路由，白名单路径跳过认证。
- **生命周期钩子**：数据库初始化、Jellyfin 启动、初始扫描和文件监控均在 FastAPI lifespan 中管理。
- **SQLite WAL 模式**：启用 WAL 模式以提升并发读取性能。

### 前端

- **API 缓存**：120s TTL 客户端缓存，变更操作（重新刮削、删除、编辑）自动失效。
- **玻璃态组件**：`index.css` 中的 CSS 工具类 — 统一使用 `glass-panel`、`glass-card` 等。
- **Portal 渲染**：弹窗和灯箱渲染到 `document.body`，避免 z-index 层级冲突。

### 关键设计决策

| 决策 | 理由 |
|----------|-----------|
| SQLite 而非 PostgreSQL | 零配置、单文件备份、WAL 模式满足单用户负载 |
| 单文件 main.py | 项目规模下维护更简单，无循环导入问题 |
| 客户端字幕渲染 | 避免服务端 ffmpeg 转码，libass-wasm 支持 ASS 特效 |
| 默认直链播放 | 现代客户端原生支持多数编码，避免服务端 CPU 负载 |
| 文件监控而非轮询 | `watchfiles` 实现低开销的实时更新 |

## 添加新功能

### 新增 API 端点

1. 在 `main.py` 中添加路由
2. 如需数据库操作，在 `database.py` 中添加 CRUD 函数
3. 在 `frontend/src/api.ts` 中添加类型化的 API 方法
4. 在页面/组件中使用

### 新增刮削器

1. 创建 `backend/app/scrapers/名称_scraper.py`
2. 继承 `BaseScraper`，实现 `search()` 和 `get_detail()`
3. 在 `registry.py` 中注册
4. `auto` 回退链会自动处理后续逻辑

### 新增前端组件

1. 在 `frontend/src/components/` 中创建
2. 使用 TailwindCSS 工具类和玻璃态组件类
3. 弹窗/遮罩层使用 React Portal
4. 如果是新页面，在 `App.tsx` 中添加路由

## 代码风格

- **后端**：标准 Python 规范。函数签名使用类型注解。
- **前端**：函数组件 + Hooks。TypeScript strict 模式。
- **CSS**：Tailwind 工具类。在 `index.css` 的 `@layer components` 中定义自定义组件。
- **命名**：代码标识符使用英文。文档和注释使用中文。
