[English](CHANGELOG.md) | **简体中文**

# 更新日志

所有 MediaTree 的重要变更都会记录在此文件中。

---

## 1.0.10 (2026-06-06)

### 重大安全更新

- 将认证加固重新作为完整 Docker 镜像更新发布，让部署环境同时刷新基础镜像和应用基线
- 匿名首次访问仍会被阻止：没有有效会话的用户必须停留在登录页或首次管理员初始化页
- 未登录时仍禁止首次媒体库初始化、更新检查、媒体库业务接口，以及部分 Jellyfin 兼容媒体接口

### 品牌资源

- 将运行时站点图标和登录页 LOGO 恢复为仓库内的圆角 PNG LOGO
- 新增 `frontend/public/logo.png`，Docker 镜像构建会包含与 README / GitHub 展示一致的 LOGO 图

### 更新方式

- Docker Compose：执行 `docker compose pull && docker compose up -d`
- Docker run：执行 `docker pull zasenjc/mediatree:1.0.10`，再按原参数重新创建容器

### 发布类型

- 需要完整 Docker 镜像更新

---

## 1.0.08 (2026-06-06)

### 安全与访问控制

- 认证现在默认失败关闭，空的 `AUTH_USER` / `AUTH_PASS` 不再代表允许匿名访问
- 新增首次打开时创建管理员账号流程，使用签名 session token，并以哈希形式保存密码
- 未登录时禁止首次媒体库初始化、更新检查、媒体库业务接口，以及部分 Jellyfin 兼容媒体接口
- 前端在首次访问或无痕模式没有 token 时，会停留在登录/初始化界面，不再提前加载媒体库选择界面

### 文档

- 说明 `AUTH_USER` / `AUTH_PASS` 用于预置管理员账号；留空时会进入首次创建管理员账号流程

### 发布类型

- 应用包级更新；不需要完整 Docker 镜像更新

---

## 1.0.07 (2026-06-04)

### 继续观看

- 将“最近观看”入口统一改为“继续观看”
- 调整继续观看入选规则：电影、单集和剧集分集观看超过 1 分钟且未看完时入选，已完全看完的项目不再入选
- 剧集某一季度看完部分分集但未看完整季时，会显示该季度的下一集；继续观看页卡片只保留插旗标记
- 继续观看页封面保持原海报宽度，同时允许高度自适应

### 播放器

- 将播放页换集按钮改为半透明液态玻璃风格的汉堡菜单
- 换集按钮现在跟随 ArtPlayer 控制层一起显示和隐藏

### 品牌与文档

- README 与 wiki 的 LOGO 标识改为新的仓库内文档 LOGO 资源
- 登录页 LOGO 与网页站点图标曾临时改为直接引用远程透明 PNG
- 删除未再引用的前端本地 logo/icon 资源，并清理 README 中失效的详情页截图链接

### 发布类型

- 应用包级更新；不需要完整 Docker 镜像更新

---

## 1.0.06 (2026-06-03)

### 自动刮削

- 将自动刮削的 watcher 和调度策略拆到独立后端辅助模块，让触发规则更容易测试和维护
- 自动刮削从固定间隔检查改为媒体库文件变动触发，并覆盖文件夹新增/删除这类结构变化
- 容器内 watcher 默认使用 polling，并支持 `FILE_WATCHER_FORCE_POLLING` 与 `FILE_WATCHER_POLL_DELAY_MS` 覆盖配置，修复 Docker Desktop bind mount 变动漏触发的问题

### 刮削器

- 修正 auto/TMDB 刮削器的回退链说明，与实际 IMDB/TMDB ID → TMDB 标题 → Bangumi 顺序保持一致

### 发布类型

- 应用包级更新；不需要完整 Docker 镜像更新

---

## 1.0.05 (2026-06-02)

### 品牌资源

- 将网页 favicon 替换为新的 MediaTree logo 资源
- 将登录页图标替换为新的透明 PNG logo
- README 顶部 logo 引用同步改为仓库内新的 PNG 资源

### 发布类型

- 应用包级更新；不需要完整 Docker 镜像更新

---

## 1.0.04 (2026-05-28)

### 需要完整镜像更新

- 本版本标记为需要完整 Docker 镜像更新，因为前端基础镜像、后端运行时依赖锁定、容器运行用户、healthcheck 和 compose 运行配置发生变化
- Release manifest 现在写入 `requires_image_update: true` 和明确原因，设置页会引导到完整镜像更新路径，而不是应用包安装

### 安全与访问控制

- 将静态 bearer 认证替换为签名会话 token，并为视频流、封面、缩略图、字幕、外部播放列表和静态媒体文件增加短期 media token
- 加固远程图片抓取和本地图片读取，只允许安全图片 URL 与预期本地目录
- 加固备份恢复流程，拒绝不安全归档成员、链接、设备文件，以及逃逸 `data_dir` 的 tar 路径
- Docker 自更新命令日志和状态输出会遮蔽敏感环境变量值
- Jellyfin 用户名/密码认证在主应用认证未配置时改为失败关闭

### 初始化与刮削配置

- 修复首次初始化时尚未登录也可以保存 TMDB access token/API 配置
- 设置页保存刮削器/TMDB 配置后会清理前端 config 缓存，手动刮削可立即识别最新 TMDB 状态

### 构建与发布流水线

- 补齐项目级 Codex/ECC 初始化文件 `.agents/`、`.codex/`，并新增 CI 校验 backend tests、backend compile 和 frontend build
- 使用 `backend/constraints.txt` 锁定后端依赖，同时在 `backend/requirements.txt` 保留 `uvicorn[standard]` extras
- Docker 构建更新到 Node 22、Python 3.12 依赖约束、非 root 运行用户和 HTTP healthcheck

---

## 1.0.03 (2026-05-25)

### 应用包级更新

- **轻量应用包更新**：设置页 Web 更新默认下载 `mediatree-app-<version>.tar.gz`，安装到 `/app/data/releases`，日常版本不再需要拉取完整 Docker 镜像
- **Docker socket 降级为高级能力**：默认 compose 不再要求挂载 `/var/run/docker.sock`；基础镜像依赖变化时仍保留完整镜像更新路径
- **回滚与状态记录**：新增 `/api/update/status` 与 `/api/update/rollback`，更新失败可回滚到上一应用包版本或镜像内置版本
- **发布产物**：GitHub Release 自动上传应用包、manifest 和 sha256，用于前端展示版本类型、下载大小和校验信息

### 设置页更新体验

- 更新栏固定只显示最近 3 个版本，避免旧版本列表挤占设置页空间
- 应用包更新进度条移动到对应版本卡片内，完成状态不再单独显示
- 回滚按钮移动到可回滚版本对应的操作位，和更新日志入口放在同一行
- 完整镜像更新时在版本卡片内展示 Docker 拉取与 helper 执行日志

### 播放器

- 新增沉浸式影院模式，播放页支持独立剧院入口、环境光背景和更集中的观看布局
- 优化影院模式在路由切换、控制层显示和退出时的体验

### 部署与移动端

- Docker 镜像改为 `/opt/mediatree/base` 基础应用 + `/app/data/releases` 可更新应用包布局
- 新增启动器，启动时优先运行数据卷中的当前应用包，异常时回退到上一版本或镜像内置版本
- 增加 Capacitor/Android 构建配置，并支持原生客户端配置服务端地址

---

## 1.0.02 (2026-05-25)

### UI 改进

- **Toast 层级修复**：toast 通知及刮削进度提示通过 createPortal 渲染到 `document.body`，修复因 `#root` 层叠上下文导致 toast 被弹窗遮罩遮挡的问题
- **手动刮削进度提示**：选择并应用手动刮削结果后，右下角显示扫描进度通知（不确定进度滑动动画），完成后自动消失
- **TMDB 未配置提醒**：执行刮削操作时若 TMDB API 未配置，toast 提醒用户前往设置页面填写 API Key

### 后端

- `/api/config` 新增 `tmdb_configured` 字段，前端可直接检测 TMDB 配置状态

---

## 1.0.01 (2026-05-24)

### 性能

- **滚动优化**：所有媒体网格卡片加入 `content-visibility: auto`，浏览器自动跳过离屏卡片的渲染
- **CSS 隔离**：网格容器添加 `contain: layout style`，防止滚动时触发整页重排
- 降低 `glass-card` 高斯模糊半径（12px → 6px），视觉效果不变，GPU 模糊计算量减半
- 收窄 `apple-focus` 过渡属性（`transition-all` → 仅 `transform/box-shadow/border-color`）
- 噪点纹理层通过 `translateZ(0)` 提升到 GPU 合成层，避免 CPU 重绘
- 所有 5 个网格页面（首页、目录、浏览、收藏、MovieCard）统一使用 `media-grid` / `media-grid-card` 类

### 自更新重构

- **docker inspect 驱动**：不再依赖 compose 文件挂载或 `COMPOSE_FILE` 环境变量，通过 `docker inspect` 自动提取容器运行时配置
- **双路径支持**：compose 管理容器自动重建 compose YAML + `compose up -d`，裸 `docker run` 容器自动重放 run 命令
- **版本检测增强**：`get_current_version()` 优先通过 docker inspect 获取镜像 tag，VERSION 文件作为回退；版本归一化支持 `-test` 等后缀
- **移除依赖**：不再需要 `docker-compose-plugin`，Dockerfile 和 compose 模板同步清理
- **版本号格式**：移除 `v` 前缀，统一使用 `1.0.01` 格式

### 修复

- 刮削器切换为"none"时立即停止刮削并清除已刮削内容
- Browse 页面：移除 JavDB 评分/点赞徽章，标题显示文件名，文件夹树跟随排序
- 修复 10 个 CodeQL 安全告警 + 字幕测试断言修正
- CHANGELOG 弹窗改用 `createPortal` + 正确的 Markdown 渲染
- 移除 `docker-compose.yml` 的 git 追踪，改用 `.example` 模板
- 退出登录修复：登出不清空媒体库选择，`?logout=1` 参数区分主动退出与首次访问
- 版本更新后自动轮询刷新，按钮文字改为"切换到此版本"

---

## 1.0.00 (2026-05-23) — 首次公开发布

### 核心架构

- **后端**：Python 3.12 + FastAPI + Uvicorn，87 个 RESTful API 端点
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
- **Javdatabase** — JAV 番号元数据，支持模糊搜索回退（去横线、前缀匹配）
- 自动刮削器，支持从文件名提取 TMDB ID 和智能回退链
- TMDB 多季合并的季集整合
- 修复 TMDB 数据管线断层 — genre、keywords、studios、tagline、status 已完整入库
- 新增 10 个 REST 端点：人物详情/作品集/照片、媒体图片/视频/上映日期/评论/关键词、季海报、集剧照
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
- 容器以 root 运行，挂载 Docker socket 以支持自更新
- SSRF 防护 — 图片代理仅限允许的 CDN 域名
- 配置端点 API 响应中遮蔽敏感值（TMDB 密钥/令牌）
- 密码不持久化到 config.json，仅从环境变量读取
- 字体文件操作的路径穿越防护
- CORS 正确配置（通配符来源 + 禁用凭据）
- NFO XML 解析禁用外部实体解析

### 自动更新系统

- Docker 自更新机制，轮询 DockerHub Tags 获取可用版本
- 一键更新或回退到任意已发布的 DockerHub Tag 版本
- 辅助容器架构 — `docker compose up -d` 在独立 `docker:cli` 容器中执行，利用 cgroup 隔离确保主容器重启时 compose 进程不受影响
- 全屏变暗居中更新日志弹窗，按需从 GitHub Releases 获取完整发布说明
- 设置导航红点提醒（15 分钟自动轮询检查）
- 4 个专用 API 端点：`/api/version`、`/api/update/check`、`/api/update/perform`、`/api/update/changelog`
- 依赖 Docker socket 挂载（`/var/run/docker.sock`）和 `COMPOSE_FILE` 环境变量
- 可配置的自动检查开关和轮询间隔（`update_check_enabled`、`update_check_interval_hours`）

### 文档

- 完整的 CLAUDE.md AI 辅助开发指南
- 首次配置启动向导
- 基于环境变量的配置，`.env.example` 模板
