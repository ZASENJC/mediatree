from fastapi import APIRouter, File, HTTPException, UploadFile

from ..scraper_plugins import (
    BUILTIN_SCRAPER_NAMES,
    delete_plugin,
    install_plugin_archive,
    list_plugins,
    record_plugin_error,
    serialize_scraper_info,
    set_plugin_enabled,
)
from ..scrapers.registry import list_scrapers

router = APIRouter()


@router.get("/api/scrapers")
async def api_list_scrapers():
    items = []
    for info in list_scrapers():
        items.append(serialize_scraper_info(info, builtin=info.name in BUILTIN_SCRAPER_NAMES))
    return {"items": items}


@router.get("/api/scraper-plugins")
async def api_list_scraper_plugins():
    return {"items": await list_plugins()}


@router.post("/api/scraper-plugins/install")
async def api_install_scraper_plugin(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    content = await file.read()
    plugin = await install_plugin_archive(file.filename or "", content)
    return {"ok": True, "plugin": plugin}


@router.post("/api/scraper-plugins/{name}/enable")
async def api_enable_scraper_plugin(name: str):
    try:
        plugin = await set_plugin_enabled(name, True)
    except HTTPException:
        raise
    except Exception as exc:
        await record_plugin_error(name, str(exc) or "Plugin load failed")
        raise HTTPException(status_code=400, detail="Plugin load failed")
    return {"ok": True, "plugin": plugin}


@router.post("/api/scraper-plugins/{name}/disable")
async def api_disable_scraper_plugin(name: str):
    plugin = await set_plugin_enabled(name, False)
    return {"ok": True, "plugin": plugin}


@router.delete("/api/scraper-plugins/{name}")
async def api_delete_scraper_plugin(name: str):
    await delete_plugin(name)
    return {"ok": True}
