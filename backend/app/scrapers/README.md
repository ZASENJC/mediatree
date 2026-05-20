# MediaTree 刮削器模板

本目录只放“统一接口适配层”。外部站点的 HTTP 细节、字段解析和缓存逻辑保留在各自模块中，`scanner.py` 尽量只消费 `ScrapeCandidate` 和 `ScrapeResult`。

## 推荐目录结构

- `base.py`：统一数据结构和 `BaseScraper`。
- `registry.py`：注册表，内置 `tmdb_movie`、`tmdb_tv`、`bangumi`、`javdatabase`、`auto`、`none`。
- `<name>_scraper.py`：新增刮削器适配层。

## BaseScraper 要求

新增刮削器继承 `BaseScraper`，至少实现：

- `search(query, media_type=None, limit=10) -> list[ScrapeCandidate]`
- `get_detail(source_id, media_type=None) -> ScrapeResult | None`
- `normalize_result(raw) -> ScrapeResult`

`scrape()` 默认是 `search(limit=1)` 后 `get_detail()`，需要特殊逻辑时可以覆盖。

## 数据结构

- `ScrapeCandidate`：搜索候选，给手动刮削列表使用。重点字段是 `source`、`source_id`、`title`、`original_title`、`year`、`media_type`、`poster_url`、`backdrop_url`、`overview`、`score`、`raw`。
- `ScrapeResult`：详情结果，给扫描、重新刮削、手动应用使用。重点字段是 `title`、`cover_url/poster_url`、`thumbnail_url/still_url/episode_still_url`、`cast/crew`、各来源 id 和 `raw`。
- `ScrapeStaff`：人员信息。演员使用 `role`，导演/监督/编剧等使用 `job` 和 `department`，`source` 填来源名。

最低返回字段：

- `title`
- `cover_url` 或 `poster_url`
- 尽量提供 `thumbnail_url`、`still_url` 或 `episode_still_url`
- 尽量提供 `cast` 或 `crew`
- `raw` 保留第三方原始响应，方便排错

## 缓存 Key 规范

所有搜索和详情请求先查 `scraper_cache`，命中缓存不得发网络请求。同一轮并发刮削用 `BaseScraper.cached_task()` 合并相同请求。

推荐 key：

- `tmdb_id:movie:123456`
- `tmdb_id:tv:123456`
- `tmdb_search:movie:inception`
- `tmdb_search:tv:breaking bad`
- `bangumi_search:anime:葬送的芙莉莲`
- `bangumi_detail:anime:12345`
- `javdb_search:code:ABC-123`
- `my_scraper_detail:movie:source_id`

## HTTP 规范

- 复用 `httpx.AsyncClient` 或等价异步客户端，不要每个条目新建 client。
- timeout 使用 `settings.scraper_http_timeout`，默认 10 秒。
- 并发使用 `settings.scraper_api_concurrency` 控制。
- 捕获 HTTP 状态码和异常并记录日志，返回 `[]` 或 `None`。
- 不打印 API key、token、密码。
- 不无限重试；失败交给 fallback 链处理。

## normalize_result 规范

`normalize_result(raw)` 只做字段映射，不做跨刮削器 fallback。第三方字段必须转换为 `ScrapeResult`：

- 图片：`cover_url/poster_url` 作为封面，`backdrop_url` 作为背景，`thumbnail_url/still_url/episode_still_url` 作为缩略图或剧照。
- staff：演员放 `cast`，导演/监督/编剧/制作等放 `crew`，制作公司同时可放 `studios`。
- 来源 id：按来源填 `tmdb_id`、`bangumi_id`、`javdb_id`，并填通用 `source_id`。
- `raw` 保留原始数据。

## 注册方式

在 `registry.py` 中注册实例：

```python
from .my_scraper import MyScraper

register_scraper(MyScraper())
```

注册后 `scanner.py` 通过 `get_scraper(name)` 获取，不直接依赖刮削器私有返回格式。

## SetupWizard / Settings 接入

前端和数据库中的 scraper 名称必须与 registry 名称一致，例如 `tmdb_movie`、`tmdb_tv`、`bangumi`、`javdatabase`。新增 scraper 后：

- 后端 `_valid_scraper()` / registry 允许该名称。
- Settings 和 SetupWizard 的选项值使用同一个名称。
- 需要 API key 时在 `config.py` 增加配置项，并设置 `requires_api_key=True`。

## Fallback 约定

fallback 由 `scanner.py` 或统一调度层决定，不要在单个 scraper 内部随意调用其它 scraper。比如 `tmdb_movie` 适配层只访问 TMDB movie API，`tmdb_tv` 只访问 TMDB tv API。

## 最小示例

```python
from .base import BaseScraper, ScrapeCandidate, ScrapeResult, ScrapeStaff


class ExampleScraper(BaseScraper):
    name = "example"
    label = "Example"
    description = "Example metadata source"
    supported_media_types = {"movie"}
    requires_api_key = False

    async def search(self, query: str, *, media_type: str | None = None, limit: int = 10):
        async def _run():
            raw_items = await fetch_search_results(query)
            return [
                ScrapeCandidate(
                    source=self.name,
                    source_id=str(item["id"]),
                    title=item["title"],
                    media_type=media_type or "movie",
                    poster_url=item.get("poster"),
                    raw=item,
                )
                for item in raw_items[:limit]
            ]

        return await self.cached_task(("search", media_type or "movie", query, limit), _run)

    async def get_detail(self, source_id: str, *, media_type: str | None = None):
        async def _run():
            raw = await fetch_detail(source_id)
            return self.normalize_result(raw) if raw else None

        return await self.cached_task(("detail", media_type or "movie", source_id), _run)

    def normalize_result(self, raw: dict):
        return ScrapeResult(
            source=self.name,
            source_id=str(raw["id"]),
            title=raw["title"],
            cover_url=raw.get("poster"),
            thumbnail_url=raw.get("thumbnail"),
            cast=[ScrapeStaff(name=n, role="") for n in raw.get("cast", [])],
            crew=[ScrapeStaff(name=n, job="Director") for n in raw.get("directors", [])],
            raw=raw,
        )
```

## 测试建议

- `python -m compileall backend/app`
- registry 加载：确认 `tmdb_movie/tmdb_tv/bangumi/javdatabase/auto/none` 都存在。
- 搜索和详情各测一次，第二次应命中 `scraper_cache`。
- 用两个媒体库同时扫描，确认不会重复扫描同一个 `media_root`，日志中没有 `database locked`。
- 对普通电影和动画电影分别验证 `tmdb_movie` 只调用 `/search/movie` 和 `/movie/{id}`。
