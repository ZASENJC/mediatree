# TMDB API 完整接入规划

> 本文档列出本项目可接入的 TMDB API 高/中价值端点，按功能领域分组，给出实现路径、前后端改动范围和预估工作量。

## 零、已完成

| 功能 | 实现方式 | 状态 |
|------|---------|------|
| genre 存入 DB | `movies.genre` 列，TMDB 类型名逗号分隔 | ✅ |
| keywords 存入 DB | `movies.keywords` 列，TMDB 关键词逗号分隔 | ✅ |
| studios 存入 DB | `movies.studios` 列，制作公司逗号分隔 | ✅ |
| tagline / status 存入 DB | `movies.tagline` / `movies.status` 列 | ✅ |
| person_id 存入 crew/cast | `ScrapeStaff.person_id` 已填充 TMDB c.id | ✅ |
| D1 图片画廊 | `GET /api/tmdb-images/{id}?media_type=movie\|tv` — posters/backdrops/logos | ✅ |
| D2 人物照片 | `GET /api/person-images/{id}` — 人物照片集 | ✅ |
| D3 季海报 | `GET /api/season-images/{sid}/{sn}` — 季海报列表 | ✅ |
| D4 集剧照 | `GET /api/episode-images/{sid}/{sn}/{en}` — 集剧照列表 | ✅ |
| B1 人物作品 | `GET /api/person/{id}/credits` — 人物参演电影+电视作品 | ✅ |
| 人物详情 | `GET /api/person/{id}` — 生平+生日+外部链接 | ✅ |
| C1/C2 预告片 | `GET /api/tmdb-videos/{id}?media_type=movie\|tv` — 预告片/花絮/片段 | ✅ |
| F2 上映信息 | `GET /api/release-dates/{id}` — 各国上映日期+分级 | ✅ |
| M3 用户评论 | `GET /api/tmdb-reviews/{id}?media_type=movie\|tv` — 用户短评 | ✅ |
| M11 关键词详情 | `GET /api/tmdb-keywords/{id}?media_type=movie\|tv` — 关键词 ID+名称 | ✅ |

### 变更文件

```
backend/app/tmdb.py           ← 数据断层修复 + 人物详情 + 5 个图像函数 + 5 个信息函数（共 10 个新函数）
backend/app/scrapers/tmdb_scraper.py ← normalize_result 加 tags
backend/app/scrapers/utils.py ← scrape_result_to_legacy 加 genre/keywords/studios/tagline/status
backend/app/database.py       ← DB 迁移 + 列声明 + 查询列更新
backend/app/scanner.py        ← _apply_scraped_data 加 5 个新字段
backend/app/main.py           ← 10 个新 REST 端点
frontend/src/api.ts           ← Movie 接口加 keywords/studios/tagline/status
backend/tests/test_p1_scraper.py ← 测试表同步新列
```

### 当前 API 端点总览

| 端点 | 用途 | 状态 |
|------|------|------|
| `GET /api/tmdb-images/{id}?media_type=movie\|tv` | 电影/剧集所有海报、背景、Logo | ✅ |
| `GET /api/person-images/{id}` | 人物所有照片 | ✅ |
| `GET /api/person/{id}` | 人物生平详情 | ✅ |
| `GET /api/person/{id}/credits` | 人物参演作品 | ✅ |
| `GET /api/season-images/{sid}/{sn}` | 季海报列表 | ✅ |
| `GET /api/episode-images/{sid}/{sn}/{en}` | 集剧照列表 | ✅ |
| `GET /api/tmdb-videos/{id}?media_type=movie\|tv` | 预告片/花絮/片段 | ✅ |
| `GET /api/release-dates/{id}` | 各国上映日期+分级 | ✅ |
| `GET /api/tmdb-reviews/{id}?media_type=movie\|tv&page=1` | 用户评论(分页) | ✅ |
| `GET /api/tmdb-keywords/{id}?media_type=movie\|tv` | 关键词详情 | ✅ |

---

## 一、高价值接入（按场景分组）

### 场景 A：详情页内容增强

| # | 端点 | 数据 | 前端展示 | 状态 |
|---|------|------|---------|------|
| A1 | `/movie/{id}/recommendations` | 推荐电影列表(海报+ID+评分) | 详情页底部「喜欢这个的人也看」横向滚动卡片 | 🔲 待接入 |
| A2 | `/tv/{id}/recommendations` | 推荐剧集列表 | 同上 | 🔲 待接入 |
| A3 | `/movie/{id}/alternative_titles` | 各国片名(title+iso_3166_1) | 详情页标题下方「又名」灰字 | 🔲 待接入 |
| A4 | `/tv/{id}/alternative_titles` | 剧集多国片名 | 同上 | 🔲 待接入 |

### 场景 B：人物资料卡

| # | 端点 | 数据 | 前端展示 | 状态 |
|---|------|------|---------|------|
| B1 | `/person/{id}/combined_credits` | 人物参演电影+电视作品 | 点击演员名弹出浮层，列出代表作 | ✅ 后端完成 |
| B2 | `/person/{id}/external_ids` | IMDB/Facebook/Instagram/Twitter | 人物卡底部社交链接图标 | ✅ 已随 `fetch_person_detail()` 获取 |

### 场景 C：视频/预告片

| # | 端点 | 数据 | 前端展示 | 状态 |
|---|------|------|---------|------|
| C1 | `/movie/{id}/videos` | 预告片/花絮/片段(YouTube key+type) | 详情页「预告片」Tab，嵌入 YouTube/Bilibili iframe | ✅ 后端完成 |
| C2 | `/tv/{id}/videos` | 同上 | 同上 | ✅ 合并为通用端点 |

### 场景 D：图片画廊

| # | 端点 | 数据 | 前端展示 | 状态 |
|---|------|------|---------|------|
| D1 | `/api/tmdb-images/{id}` | posters/backdrops/logos 数组 | 详情页海报切换画廊，可左右滑动选封面 | ✅ 后端完成 |
| D2 | `/api/person-images/{id}` | 人物照片集 profiles 数组 | 演员点击后浮层显示多张照片 | ✅ 后端完成 |
| D3 | `/api/season-images/{sid}/{sn}` | 季海报列表 | 剧集季导航显示对应季封面 | ✅ 后端完成 |
| D4 | `/api/episode-images/{sid}/{sn}/{en}` | 集剧照列表 | 剧集详情中集剧照画廊 | ✅ 后端完成 |

### 场景 E：多语言翻译

| # | 端点 | 数据 | 前端展示 | 状态 |
|---|------|------|---------|------|
| E1 | `/movie/{id}/translations` | 各语言 overview+tagline | 详情页语言切换下拉框，中文/英文/日文简介 | 🔲 待接入 |
| E2 | `/tv/{id}/translations` | 同上 | 同上 | 🔲 待接入 |

### 场景 F：串流/发行信息

| # | 端点 | 数据 | 前端展示 | 状态 |
|---|------|------|---------|------|
| F1 | `/movie/{id}/watch/providers` | 各国串流平台(logo+链接) | 详情页「可在...观看」行，显示平台图标 | 🔲 待接入 |
| F2 | `/movie/{id}/release_dates` | 各国上映日期+分级 | 详情页「上映」行，显示中国/美国/日本上映日+分级 | ✅ 后端完成 |

### 场景 G：搜索优化

| # | 端点 | 数据 | 前端展示 | 状态 |
|---|------|------|---------|------|
| G1 | `/search/multi` | 一次搜索返回 movie+tv+person | 替换当前两次串行调用 | 🔲 待接入 |
| G2 | `/genre/movie/list` + `/genre/tv/list` | 类型 ID→名称映射表 | 搜索结果中 genre_ids 无需查详情即可显示类型名 | 🔲 待接入 |

---

## 二、中价值接入

| # | 端点 | 数据 | 前端展示 | 状态 |
|---|------|------|---------|------|
| M1 | `/movie/{id}/credits` | 完整演职表(无截断) | 取代 `append_to_response` 的截断版 | 🔲 待接入 |
| M2 | `/tv/{id}/similar` | 算法相似内容 | 详情页「相似内容」区块 | 🔲 待接入 |
| M3 | `/movie/{id}/reviews` | 用户短评 | 详情页「用户评论」折叠区 | ✅ 后端完成 |
| M4 | `/trending/{movie,tv}/{day,week}` | 每日/每周热门 | 首页选加「热门推荐」区块 | 🔲 待接入 |
| M5 | `/discover/movie` + `/discover/tv` | 30+过滤排序的发现引擎 | 独立的「发现」页面 | 🔲 待接入 |
| M6 | `/tv/{id}/episode_groups` | TMDB 剧集原始分组 | 当 TMDB 多季合并导致偏移推断失败时，用官方分组修复 | 🔲 待接入 |
| M7 | `/tv/{id}/content_ratings` | 各国年龄分级 | 详情页元数据行展示分级徽章 | 🔲 待接入 |
| M8 | `/tv/{id}/season/{n}/credits` | 季级演职表(aggregate) | 剧集详情展示当前季的演员和角色汇总 | 🔲 待接入 |
| M9 | `/search/person` | 搜索人物 | 全局搜索也返回匹配的演员/导演 | 🔲 待接入 |
| M10 | `/collection/{id}` + `images` | 电影系列详情 | 将系列中的电影关联展示，显示系列统一海报 | 🔲 待接入 |
| M11 | `/movie/{id}/keywords` | 电影关键词详情 | 详情页可点击关键词进行二次过滤 | ✅ 后端完成 |

---

## 三、推荐实现优先级

### 第一优先级（小成本高回报）

- **G1**: `/search/multi` 取代双重搜索 → 后端 30min
- **G2**: 类型 ID→名称缓存 → 后端 30min
- **A3/A4**: 多语言片名 → 后端 30min + 前端修改

### 第二优先级（需前后端各半天到一天）

- **D1-D4**: 图片画廊前端接入 → 前端 1day（后端已完成）
- **C1/C2**: 预告片前端接入 → 前端 1day（后端已完成）
- **B1/B2**: 人物资料卡前端接入 → 前端 1day（后端已完成）
- **E1/E2**: 多语言简介 → 后端 1h + 前端 1day

### 第三优先级（新功能区域）

- **A1/A2**: 推荐引擎 → 后端 2h + 前端 1day
- **F1/F2**: 串流/发行信息前端接入 → 前端 1day（F2 后端已完成，F1 待接入）
- **M4**: 热门趋势 → 后端 1h + 前端 1day

### 第四优先级（改动较大）

- **M5**: 发现页面 → 前后端各 3-5 days
- **M10**: 系列管理 → 前后端各 2-3 days
- **M6**: 剧集分组修复 → 后端逻辑改动
