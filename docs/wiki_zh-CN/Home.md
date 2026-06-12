[English](../wiki/Home) | **简体中文**

<p align="center">
  <img src="https://raw.githubusercontent.com/ZASENJC/mediatree/main/docs/assets/logo.png" alt="MediaTree" width="96" />
</p>

# MediaTree Wiki

欢迎查阅 MediaTree 文档。MediaTree 是一个自托管的媒体库管理器，将优雅的玻璃态 UI、浏览器播放、外部播放器接续和强大的插件化刮削系统融为一体。

> 新版文档站已发布到 [https://zasenjc.github.io/mediatree/](https://zasenjc.github.io/mediatree/)。GitHub Wiki 继续作为镜像和旧入口保留。

## 快速导航

| 指南 | 说明 |
|-------|-------------|
| [新版文档站](https://zasenjc.github.io/mediatree/) | 部署、配置、刮削、升级、API 和开发文档 |
| [安装指南](Installation) | Docker 部署和首次配置 |
| [配置说明](Configuration) | 环境变量和运行时设置 |
| [刮削器系统](Scrapers) | TMDB、Bangumi、Javdatabase 刮削系统 |
| [开发指南](Development) | 本地开发环境和架构说明 |

## 架构概览

```
┌─────────────────────────────────────────────┐
│                 Docker 容器                   │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │  前端 React 18 │  │  后端 (FastAPI)      │ │
│  │  TypeScript 5 │  │  Python 3.12         │ │
│  │  Vite         │  │  SQLite (aiosqlite)  │ │
│  └──────────────┘  └──────────────────────┘ │
│         ↕ 代理 /api/*      ↕ 文件系统        │
│  ┌────────────────────────────────────────┐  │
│  │  媒体卷（只读挂载）                       │  │
│  │  数据卷（数据库、封面、字体）              │  │
│  └────────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## 核心特性一览

- **玻璃态 UI** — Apple 风格设计，Liquid Glass 顶栏、极光渐变和剧院模式
- **多库支持** — 每个媒体根独立的刮削器配置、密码保护和文件夹树浏览
- **刮削器插件** — TMDB（电影/电视剧）、Bangumi（动漫）、Javdatabase（JAV）+ 自动回退链
- **ArtPlayer 5** — 定制控件、触摸手势、键盘快捷键、画中画和 VR/360° 支持
- **ASS/SSA 字幕** — libass-wasm 渲染，CJK 回退字体，完整特效支持
- **外部播放器** — 网页播放器可生成 M3U 播放列表，交给 VLC、IINA 或 mpv 播放
- **文件监控** — 文件变更自动增量扫描，15 秒防抖
