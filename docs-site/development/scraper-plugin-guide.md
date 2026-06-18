# 刮削器插件开发指南

刮削器插件是一个 `.zip` 包。包里必须有 `plugin.json` 和一个 Python 入口文件，入口文件提供继承自 `BaseScraper` 的类。上传后插件会安装到运行时数据目录，默认保持停用；只有在设置页插件管理中启用成功后，插件才会出现在媒体库刮削器下拉栏和手动刮削入口中。

当前插件运行在 MediaTree 后端进程内，是可信本地代码，不提供沙箱。不要安装来源不明的插件。

## 最小包结构

压缩包内的 `plugin.json` 必须位于归档根目录，不能再套一层目录。

```text
demo_plugin-1.0.0.zip
├── plugin.json
└── plugin.py
```

打包时在插件源码目录内执行：

```bash
zip -r ../demo_plugin-1.0.0.zip plugin.json plugin.py
```

如果压缩包是下面这种结构，安装会失败：

```text
demo_plugin-1.0.0.zip
└── demo_plugin/
    ├── plugin.json
    └── plugin.py
```

## plugin.json

示例：

```json
{
  "name": "demo_plugin",
  "version": "1.0.0",
  "label": "Demo Plugin",
  "description": "Demo metadata scraper",
  "entrypoint": "plugin.py",
  "class_name": "DemoPluginScraper",
  "supported_media_types": ["movie"]
}
```

字段规则：

| 字段 | 要求 |
| --- | --- |
| `name` | 必填。3-64 位，小写字母开头，只能包含小写字母、数字和下划线。 |
| `version` | 必填。1-64 位，必须以字母或数字开头，可包含字母、数字、`.`、`_`、`+`、`-`。 |
| `label` | 必填。设置页和下拉栏显示名，最多 96 字符。 |
| `description` | 可选。最多 512 字符。当前设置页不展示说明，但 API 会返回。 |
| `entrypoint` | 必填。插件入口 Python 文件的相对路径，必须以 `.py` 结尾，不能是绝对路径，不能包含 `..`。 |
| `class_name` | 必填。入口文件中的类名，必须是合法 Python 标识符。 |
| `supported_media_types` | 必填且不能为空。每项 1-32 位，可包含小写字母、数字、`_`、`-`。常用值是 `movie`、`tv`、`anime`、`jav`、`collection`。 |

上传插件的 `requires_api_key` 和 `builtin` 不会作为公开能力使用。插件需要密钥时，优先从环境变量读取，不要把密钥放进 `plugin.json` 或插件源码包。

## 名称限制

默认启用内置刮削器时，上传插件不能使用这些名称：

- `auto`
- `none`
- `tmdb_movie`
- `tmdb_tv`
- `tmdb_collection`
- `bangumi`
- `javdatabase`

以下兼容别名也始终保留：

- `tmdb`
- `tmdb_tv_search`
- `tmdb_movie_search`

正常开发第三方插件时，不要依赖关闭内置刮削器来复用这些名称。插件名应该稳定，因为媒体库设置会保存这个名称。

## 入口类

入口类必须继承 `app.scrapers.base.BaseScraper`，至少实现：

- `search(query, media_type=None, limit=10) -> list[ScrapeCandidate]`
- `get_detail(source_id, media_type=None) -> ScrapeResult | None`
- `normalize_result(raw) -> ScrapeResult`

插件启用时，MediaTree 会实例化这个类，并用 `plugin.json` 覆盖实例上的 `name`、`label`、`description`、`supported_media_types` 和 `enabled`。因此类里可以不写这些元数据，但业务返回值里的 `source` 应该使用 `self.name`。

插件入口是按单文件动态加载的，不是作为完整 Python 包导入。入口文件可以导入 MediaTree 后端模块，例如：

```python
from app.scrapers.base import BaseScraper, ScrapeCandidate, ScrapeResult, ScrapeStaff
from app.database import get_scraper_cache, set_scraper_cache
from app.config import logger, settings
```

不要在入口文件里依赖 `from .xxx import ...` 这类相对导入，除非你已经自己处理好模块加载路径。

## 最小示例

```python
from app.scrapers.base import BaseScraper, ScrapeCandidate, ScrapeResult, ScrapeStaff


class DemoPluginScraper(BaseScraper):
    async def search(self, query: str, *, media_type: str | None = None, limit: int = 10):
        clean_query = (query or "").strip()
        if not clean_query:
            return []

        async def _run():
            return [
                ScrapeCandidate(
                    source=self.name,
                    source_id="demo-1",
                    title=f"Demo {clean_query}",
                    media_type=media_type or "movie",
                    poster_url="https://image.tmdb.org/t/p/w500/example.jpg",
                    raw={"query": clean_query},
                )
            ][:limit]

        return await self.cached_task(("search", media_type or "movie", clean_query, limit), _run)

    async def get_detail(self, source_id: str, *, media_type: str | None = None):
        raw = {
            "id": str(source_id),
            "title": "Demo Detail",
            "poster": "https://image.tmdb.org/t/p/w500/example.jpg",
            "overview": "Demo overview",
            "cast": ["Actor A"],
        }
        return self.normalize_result(raw)

    def normalize_result(self, raw: dict):
        return ScrapeResult(
            source=self.name,
            source_id=str(raw["id"]),
            title=raw["title"],
            media_type="movie",
            overview=raw.get("overview"),
            cover_url=raw.get("poster"),
            poster_url=raw.get("poster"),
            cast=[ScrapeStaff(name=name, role="", source=self.name) for name in raw.get("cast", [])],
            raw=raw,
        )
```

## 返回数据约定

`ScrapeCandidate` 用于搜索候选列表。重点字段：

- `source`：插件名，通常填 `self.name`。
- `source_id`：第三方来源 ID，后续 `get_detail()` 会收到这个值。
- `title`：候选标题。
- `media_type`：候选媒体类型。
- `poster_url`、`backdrop_url`、`overview`、`score`：用于手动刮削列表展示和背景图预取。
- `raw`：保留来源原始数据，方便排错。

`ScrapeResult` 用于写入媒体库。重点字段：

- `source`、`source_id`、`title`
- `original_title`、`year`、`media_type`、`overview`
- `cover_url` 或 `poster_url`
- `backdrop_url`
- `thumbnail_url`、`still_url`、`episode_still_url`
- `cast`、`crew`、`studios`、`genres`、`tags`
- `tmdb_id`、`bangumi_id`、`javdb_id` 或通用 `source_id`
- `season`、`episode`、`episode_title`
- `raw`

后端会把 `ScrapeResult` 转成旧的数据库写入格式。自动扫描和重新刮削还会做标题匹配；如果你的来源标题和本地文件名差异较大，需要在 `full_scrape()` 中实现更合适的匹配逻辑，或者确保返回的 `raw` 里包含足够的辅助字段。

## 自动扫描与手动刮削

只实现 `search()` 和 `get_detail()` 后，插件已经可以参与手动刮削、手动应用和详情获取。

自动扫描、重新刮削和文件夹刮削会走 `BaseScraper.full_scrape()`。默认实现会基于本地标题构造查询，调用 `scrape()`，再把 `ScrapeResult` 转成数据库写入格式。简单标题源可以直接使用默认实现；如果插件需要番号、ID、季集、特殊标题清洗或跨字段匹配，建议覆盖 `full_scrape()`。

一个已启用的上传插件在回退链中只代表它自己，不会自动调用 TMDB、Bangumi 或其他刮削器。跨来源 fallback 应该放在调度层或插件自己的明确逻辑里，不要隐式改写其他插件的结果。

## 缓存和网络请求

网络插件应该同时处理两层缓存：

- `BaseScraper.cached_task()`：合并同一轮并发中的相同请求，避免同时打到第三方 API。
- `get_scraper_cache()` / `set_scraper_cache()`：写入 SQLite 持久缓存，减少后台重复请求。

示例：

```python
from app.database import get_scraper_cache, set_scraper_cache


CACHE_HOURS = 168


async def cached_search(self, query: str, media_type: str | None):
    cache_key = f"demo_search:{media_type or 'movie'}:{query.strip().lower()}"
    cached = await get_scraper_cache(self.name, cache_key, CACHE_HOURS)
    if cached is not None:
        return cached

    data = await fetch_from_remote_api(query)
    await set_scraper_cache(self.name, cache_key, data)
    return data
```

请求规范：

- 复用 `httpx.AsyncClient` 或等价异步客户端。
- timeout 使用 `settings.scraper_http_timeout`。
- 并发上限参考 `settings.scraper_api_concurrency`。
- 捕获 HTTP 状态码和网络异常，失败时返回 `[]` 或 `None`。
- 不打印 API key、token、cookie 或密码。
- 不做无限重试。

手动扫描、重新刮削和手动应用结果会绕过 MediaTree 的 scraper cache。使用 `get_scraper_cache()` 和 `cached_task()` 时，这个绕过策略会自动生效。

## 图片 URL

封面、背景图和剧照最终会由后端代理或缓存。MediaTree 默认只允许抓取安全白名单里的远程图片域名。插件返回自定义站点图片时，如果图片不能显示，需要同步扩展 `backend/app/config.py` 里的安全图片域名策略，并补充测试。

插件也可以返回本地可访问的图片路径，但必须确保路径位于 MediaTree 允许读取的媒体目录或数据目录内。

## 安装、启用、停用和删除

设置页的插件管理面板同时管理内置刮削器和用户上传插件。用户上传插件的操作流程是：

1. 上传 `.zip`。
2. 后端校验归档和 `plugin.json`。
3. 文件安装到 `DATA_DIR/scraper_plugins/<name>/<version>/`。
4. 数据库写入 `scraper_plugins` 记录，默认 `enabled=false`。
5. 用户点击启用。
6. 后端动态加载入口类并检查它是否继承 `BaseScraper`。
7. 启用成功后，插件出现在 `/api/scrapers` 和前端刮削器下拉栏。

停用插件或内置刮削器后，它会从 `/api/scrapers` 消失，也不会继续出现在刮削器下拉栏。记录仍保留在插件管理中，可以重新启用。

删除用户上传插件会删除数据库记录和当前安装目录；如果仍有媒体库使用该上传插件，删除会返回 `409 Plugin is used by a library`，需要先切换对应媒体库。删除内置刮削器只会把它从当前配置中隐藏，不会删除应用自带代码；仍在使用该内置刮削器的媒体库会回退到当前可用默认刮削器。

对应 API：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/api/scrapers` | 返回内置刮削器和已启用上传插件。 |
| `GET` | `/api/scraper-plugins` | 返回插件管理列表，包含内置刮削器和用户上传插件。 |
| `POST` | `/api/scraper-plugins/install` | 上传并安装 `.zip`，默认停用。 |
| `POST` | `/api/scraper-plugins/{name}/enable` | 启用插件并尝试加载入口类。 |
| `POST` | `/api/scraper-plugins/{name}/disable` | 停用插件。 |
| `DELETE` | `/api/scraper-plugins/{name}` | 删除插件。 |

## 归档限制

安装器会拒绝不符合安全限制的压缩包：

- 只接受 `.zip`。
- 压缩包不能为空。
- 压缩包大小上限是 2 MB。
- 归档成员数量上限是 32。
- 单个文件未压缩大小上限是 4 MB。
- 所有文件未压缩总大小上限是 4 MB。
- 不允许绝对路径。
- 不允许 `..` 路径穿越。
- 不允许符号链接。
- 不允许重复文件路径。
- 必须包含根目录下的 `plugin.json`。
- `entrypoint` 指向的文件必须存在于归档中。

这些限制只保证安装路径安全，不代表插件代码被沙箱隔离。插件启用后可以执行普通 Python 代码，安装前必须确认来源可信。

## 内置插件和上传插件的区别

内置刮削器也使用 manifest 形式，源码位于：

```text
backend/app/builtin_plugins/scrapers/<name>/
├── plugin.json
└── plugin.py
```

内置插件随应用发布，通过 `backend/app/scrapers/registry.py` 加载；用户上传插件安装在 `DATA_DIR/scraper_plugins/<name>/<version>/`，状态保存在 SQLite 的 `scraper_plugins` 表。

默认情况下：

- `/api/scrapers` 返回当前启用且未隐藏的内置刮削器和已启用上传插件。
- `/api/scraper-plugins` 返回插件管理列表，包含内置刮削器和用户上传插件。
- fresh Docker 容器没有用户上传插件，但会有内置刮削器。
- 设置 `ENABLE_BUILTIN_SCRAPER_PLUGINS=false` 可以让测试容器不加载任何内置刮削器。

## 本地测试建议

先检查插件文件本身：

```bash
python3.11 -m py_compile plugin.py
zip -r ../demo_plugin-1.0.0.zip plugin.json plugin.py
```

在 MediaTree 后端测试插件管理链路：

```bash
curl -u admin:password \
  -F "file=@demo_plugin-1.0.0.zip" \
  http://localhost:27580/api/scraper-plugins/install

curl -u admin:password \
  -X POST \
  http://localhost:27580/api/scraper-plugins/demo_plugin/enable

curl -u admin:password \
  http://localhost:27580/api/scrapers
```

仓库内回归测试：

```bash
cd backend
PYTHONPATH=. python3.11 -m unittest tests.test_scraper_plugins tests.test_builtin_scraper_plugins
cd ..
python3.11 -m compileall -q backend/app
```

至少验证这些场景：

- 安装后插件在插件管理中存在，但未启用前不出现在刮削器下拉栏。
- 启用成功后 `/api/scrapers` 包含插件名。
- 停用所有上传插件后，下拉栏不再显示它们。
- 手动搜索能返回候选结果。
- 手动应用候选能写入标题、封面、来源 ID 和人员信息。
- 自动扫描或重新刮削能命中正确条目。
- 插件启用失败时，错误会显示在插件管理中，且插件保持停用。
- 插件被媒体库使用时不能删除。

## 常见错误

| 错误 | 处理 |
| --- | --- |
| `plugin.json required` | 确认 `plugin.json` 位于 zip 根目录。 |
| `Invalid plugin name` | 使用小写字母开头的 `name`，只包含小写字母、数字和下划线。 |
| `Plugin name is reserved` | 换一个不与内置刮削器或兼容别名冲突的名称。 |
| `Plugin entrypoint not found` | 确认 `entrypoint` 与 zip 内文件路径完全一致。 |
| `Plugin class must subclass BaseScraper` | 入口类必须继承 `app.scrapers.base.BaseScraper`。 |
| 启用失败但安装成功 | 查看插件管理中的 `error` 字段；安装阶段不执行插件代码，启用阶段才加载入口类。 |
| 插件已启用但下拉栏没有 | 调用 `/api/scrapers` 确认后端是否返回；如果后端没有返回，检查启用状态和加载错误。 |
| 封面 URL 不显示 | 检查图片域名是否在后端安全白名单中，或改为返回允许读取的本地图片路径。 |
