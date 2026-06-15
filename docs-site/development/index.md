# 开发指南

## 项目结构

```text
mediatree/
├── backend/               # Python 3.12 + FastAPI
│   ├── app/
│   │   ├── main.py        # FastAPI 应用和路由处理
│   │   ├── scanner.py     # 扫描和刮削引擎
│   │   ├── database.py    # SQLite CRUD
│   │   ├── config.py      # pydantic-settings + JSON 持久化
│   │   ├── stream.py      # 视频流、Range、转码
│   │   ├── subtitles.py   # 字幕检测和转换
│   │   └── scrapers/      # 刮削器插件系统
│   └── tests/
├── frontend/              # React 18 + TypeScript + Vite
├── docs-site/             # VitePress 文档站
└── Dockerfile
```

## 本地开发

生产环境由后端提供构建后的前端。开发时通常运行两个进程：

```bash
# 后端
cd backend
pip install -r requirements.txt -c constraints.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# 前端
cd frontend
npm install
npm run dev
```

Vite 开发服务器会把 `/api/*` 代理到 `localhost:80`。

## 文档站开发

```bash
cd docs-site
npm ci
npm run dev
```

构建：

```bash
cd docs-site
npm run build
```

文档站部署到 GitHub Pages，路径为 `/mediatree/`。不要把文档部署 workflow 和应用包发布 workflow 合并。

## 测试和构建

```bash
cd backend && PYTHONPATH=. python3.11 -m unittest discover -s tests -p 'test_*.py'
python3.11 -m compileall -q backend/app
cd frontend && npm run build
```

本地 `python3` 在 macOS 上可能指向较旧版本，优先使用 Python 3.11+。生产镜像使用 Python 3.12。

## 添加 API

1. 在 `backend/app/main.py` 添加路由。
2. 需要持久化时，在 `backend/app/database.py` 添加 CRUD。
3. 在 `frontend/src/api.ts` 添加类型化客户端方法。
4. 在页面或组件中使用，并补充测试。

## 添加刮削器

用户可上传安装的刮削器应做成 `.zip` 插件包，包含 `plugin.json` 和继承 `BaseScraper` 的 Python 入口类。完整包结构、manifest 字段、安装启用流程和测试方法见[刮削器插件开发指南](/development/scraper-plugin-guide)。

维护内置刮削器时，使用 `backend/app/builtin_plugins/scrapers/<name>/plugin.json` 和 `plugin.py` 接入 manifest 驱动注册表；核心复用逻辑仍可放在 `backend/app/scrapers/`。

## 添加前端主题

用户可导入的前端主题支持主题变量、稳定 `.mt-*` 选择器和可选的安全 CSS，可用于颜色、字体、间距、圆角、阴影、动效和 MD3 风格这类大范围外观改造。完整文件结构、变量清单、自定义 CSS 限制和主题包格式见[主题开发指南](/development/theme-development)。
