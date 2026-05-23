[English](../wiki/Scrapers) | [简体中文](Scrapers)

# 刮削器系统

MediaTree 使用插件化的刮削器系统从多个来源获取元数据。每个媒体库可以使用不同的刮削器配置。

## 内置刮削器

### TMDB（`tmdb_movie` / `tmdb_tv`）

最全面的刮削器，支持电影和电视剧。

- **元数据**：标题、原始标题、概述、上映日期、类型、关键词、分级
- **演员和制作人**：演员、导演、编剧，含头像
- **图片**：海报、背景、Logo、季海报、分集剧照
- **评论**：来自 TMDB 的用户评论
- **视频**：预告片和片段
- **人物**：完整人物资料，含影片作品集

**要求**：TMDB API 密钥或读取访问令牌（参见[配置说明](Configuration)）

### Bangumi（`bangumi`）

专注于动漫和东亚媒体。

- **元数据**：中文、日文和英文标题
- **人员**：声优、导演、原作
- **图片**：封面图和角色图
- **条目类型**：动画、漫画、游戏、小说、三次元

**无需 API 密钥**（使用公开 API）。

### Javdatabase（`javdatabase`）

基于番号的 JAV 元数据刮削器。

- **元数据**：标题、演员、导演、制作商、厂牌、类型
- **评分**：评分、点赞数、播放量
- **缩略图**：封面和样品图
- **详情**：时长、发行日期、系列

**要求**：默认启用。可通过设置页面配置。

### 自动（`auto`）

智能回退链，自动选择最佳刮削器：

1. 从文件名提取 TMDB ID（`[tmdbid=123]`、`[tmdb-movie=123]` 等）
2. 如果找到 TMDB ID → 精确匹配，自动推断电影/电视剧类型
3. 如果没有 ID → TMDB 标题搜索（电影和电视剧均搜索）
4. 如果 TMDB 失败 → Bangumi 回退
5. 全部失败 → 不应用元数据

### 无刮削（`none`）

禁用网络刮削。适用于仅使用本地 NFO/元数据或基于文件名展示的库。

## 回退链

```
tmdb_movie ──→ Bangumi ──→ TMDB movie 标题搜索
tmdb_tv    ──→ Bangumi ──→ TMDB tv 标题搜索
bangumi    ──→ TMDB tv 标题搜索
javdatabase ──（独立，无回退）
auto        ──→ Bangumi ──→ TMDB 标题搜索（二者均尝试）
```

## 添加自定义刮削器

刮削器采用插件架构。添加新的刮削器：

```python
# backend/app/scrapers/my_scraper.py
from .base import BaseScraper, ScrapeResult, ScrapeCandidate

class MyScraper(BaseScraper):
    name = "my_scraper"
    label = "My Scraper"
    description = "Custom metadata source"

    async def search(self, query: str, **kwargs) -> list[ScrapeCandidate]:
        # 实现搜索逻辑
        ...

    async def get_detail(self, candidate: ScrapeCandidate) -> ScrapeResult:
        # 实现详情获取
        ...

    def normalize_result(self, result: ScrapeResult) -> ScrapeResult:
        # 可选：规范化结果
        return result
```

然后注册：

```python
# backend/app/scrapers/registry.py
from .my_scraper import MyScraper
register_scraper(MyScraper())
```

## 刮削器缓存

- HTTP 响应缓存在 SQLite 中（`scraper_cache` 表）
- 每个来源可配置缓存有效期（默认：TMDB/Bangumi 168h，JavDB 24h）
- 同一资源的并发请求会被去重
- 右键 → 「重新刮削」可绕过缓存，强制刷新

## 手动刮削

1. 右键点击文件夹或影片 → 「手动刮削」
2. 按标题或 TMDB ID 搜索
3. 从搜索结果中选择正确的匹配
4. 点击「应用」更新元数据

## 季集处理

MediaTree 自动检测季文件夹（`S01`、`S02`、`Season 1` 等）并：
- 从 TMDB 获取每季元数据
- 将本地分集文件映射到 TMDB 集数
- 处理多季合并（TMDB 合并多季时）
- 显示分集标题、概述和剧照

对于动漫，[动漫命名解析器](#) 从 `[01]`、`EP01`、`S01E01` 等多种格式中提取集数。
