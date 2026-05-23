[English](CHANGELOG.md) | [简体中文](CHANGELOG_zh-CN.md)

# 更新日志

所有 MediaTree 的重要变更都会记录在此文件中。

---

## v1.0.0 (2026-05-23) — 首次公开发布

### 核心架构

- **后端**：Python 3.12 + FastAPI + Uvicorn，85+ RESTful API 端点
- **前端**：React 18 + TypeScript 5 + TailwindCSS 3 + Vite
- **数据库**：SQLite + aiosqlite（WAL 模式，busy_timeout=5s）
- **部署**：Docker 多阶段构建，linux/amd64 + linux/arm64 多架构

### 媒体管理

- 多库支持，每个库独立刮削器配置和访问密码
- 递归文件系统扫描，原子化 upsert + 已删除文件清理
- 文件夹树浏览器，支持嵌套目录导航和季集标签切换
- 首页源文件名 / 刮削标题显示切换
- 文件监控（`watchfiles`）+ 15s 防抖自动增量扫描
- 数据库驱动文件夹浏览（比文件系统遍历快 10-50 倍）

### 刮削系统

- 插件化架构，基于 `BaseScraper` 抽象类
- **TMDB** — 电影和电视剧元数据（标题、演员/制作人、封面、背景、评论、关键词）
- **Bangumi** — 针对中文/日文标题的动漫元数据
- **Javdatabase** — JAV 番号元数据
- 自动刮削器，支持从文件名提取 TMDB ID 和智能回退链
- TMDB 多季合并的季集整合
- 手动刮削，支持搜索选择界面
- 右键上下文菜单支持文件夹批量刮削
- 刮削器缓存，可配置 TTL（24h - 168h）
- 并发刮削，可配置并行度限制（最多 16 个任务）

### 视频播放器

- ArtPlayer 5 嵌入，定制 UI 和 YouTube 风格控件
- 直链播放，支持 HTTP Range 字节跳转
- 按需 ffmpeg 转码（H.264 + AAC MP4）
- 触摸手势系统 — 轻触/双击/滑动移动端控制
- 键盘快捷键 — Space/K（播放）、←→（跳转）、↑↓（音量）、F（全屏）、M（静音）
- 画中画支持
- VR/360° 视频支持（Three.js 等距矩形渲染）
- 外部播放器支持（IINA/mpv/VLC M3U 播放列表生成）
- 播放进度跟踪，支持断点续播

### 字幕系统

- 内嵌字幕检测（ffprobe）：ASS、SSA、SRT、VTT、MOV_TEXT
- 外挂字幕自动匹配：文件名 + 语言后缀 + 集数
- **ASS/SSA 渲染**：@jellyfin/libass-wasm，完整特效、字体和定位
- CJK 回退字体（思源黑体 CN Bold），适配动漫字幕
- SRT → WebVTT 转换（纯 Python，无 ffmpeg 依赖）
- 字幕编码自动检测（16 种编码 + charset-normalizer 回退）
- 用户字体上传/管理，支持自定义字幕字体
- 字幕轨道选择，支持语言优先级排序
- 外挂音频轨道检测（.mka、.aac、.flac、.opus、.ac3、.eac3、.dts）

### Jellyfin 兼容性

- 36 个 Jellyfin 兼容 API 端点，支持客户端直连
- 兼容 VidHub、Infuse、Kodi、VLC、IINA、mpv 等 Jellyfin 客户端
- 多客户端认证 — MediaBrowser Token、X-Emby-Token、Bearer、api_key
- 基于文件夹结构的 Series → Season → Episode 层级
- Emby 路径兼容（重写中间件）
- 默认直链播放，完整字幕轨道传输
- 播放会话跟踪和进度上报

### UI 设计系统

- **玻璃态 + Apple 风格** 设计语言
- 定制 TailwindCSS 调色板 — `apple-*`（蓝/紫/粉/薄荷/黄）、`glass-*`（表面/浮层/边框/减弱）
- 可复用 CSS 组件类 — `glass-panel`、`glass-card`、`glass-button`、`glass-input`、`glass-modal`、`glass-popover`、`glass-chip`
- Liquid Glass 顶栏，支持色散光晕效果
- 极光渐变背景 + 剧院模式环境光效
- 响应式导航 — 双玻璃胶囊（左侧品牌+导航，右侧操作区）
- 完整移动端适配，小屏缩写品牌名
- 图片灯箱，支持手势滑动导航
- Toast 通知系统替代浏览器 `alert()`

### 封面和图片处理

- 本地封面缓存，Pillow 缩放（最大 500px，JPEG q=80）
- TMDB/Bangumi/Javdatabase 远程封面 URL 回退
- 背景图支持，CSS 交叉淡入淡出轮播
- 视频截图生成剧照（ffmpeg）
- 备用封面选择器，支持浏览 TMDB 海报/背景
- 文件夹级别封面和背景管理
- 安全图片代理，仅限受信任 CDN 域名（TMDB、Bangumi、JavDB）

### 高级功能

- **动漫命名解析器** — 清除发布组和技术标签，从 `[01]`、`[EP01]`、`S01E01`、`第1话` 等格式提取集数
- **排序选项** — 按添加日期、上映日期、名称和随机排序
- **搜索** — 实时搜索标题、番号和演员，支持防抖
- **收藏** — 基于标签的收藏系统，独立收藏页面
- **分类** — 用户定义合集，自定义分组
- **排除文件夹** — 持久化隐藏机制，存储在 localStorage
- **滚动位置恢复** — 基于 sessionStorage 的导航位置恢复
- **API 响应缓存** — 120s TTL 客户端缓存，智能失效
- **数据库备份/恢复** — 核心（SQLite）和完整（含封面和剧照）备份选项
- **待审队列** — 未刮削媒体的待审核项

### 安全性

- PBKDF2-SHA256 密码哈希（100,000 次迭代）+ 独立盐值
- Docker 非 root 用户运行（uid 1000）
- SSRF 防护 — 图片代理仅限允许的 CDN 域名
- 配置端点 API 响应中遮蔽敏感值（TMDB 密钥/令牌）
- 密码不持久化到 config.json，仅从环境变量读取
- 字体文件操作的路径穿越防护
- CORS 正确配置（通配符来源 + 禁用凭据）
- NFO XML 解析禁用外部实体解析

### 文档

- 完整的 CLAUDE.md AI 辅助开发指南
- 首次配置启动向导
- 基于环境变量的配置，`.env.example` 模板
