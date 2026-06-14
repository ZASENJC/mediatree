from fastapi import APIRouter, HTTPException, Query

from ..updater import (
    fetch_github_release_body,
    get_available_versions,
    get_update_status,
    get_version_state,
    perform_update,
    rollback_app_package,
)

router = APIRouter()


@router.get("/api/version")
async def api_version():
    """Get current application version."""
    info = get_version_state()
    return {
        "version": info["current_version"],
        "runtime_version": info["runtime_version"],
        "current_source": info["current_source"],
        "base_version": info["base_version"],
        "effective_version": info["effective_version"],
        "overlay_active": info["overlay_active"],
        "overlay_is_outdated": info["overlay_is_outdated"],
        "status_note": info["status_note"],
    }


@router.get("/api/update/check")
async def api_update_check(include_registry_sync: bool = Query(False)):
    """Check for available updates from GitHub Releases."""
    return await get_available_versions(include_registry_sync=include_registry_sync)


@router.post("/api/update/perform")
async def api_update_perform(data: dict):
    """Trigger an app-package update to the specified version."""
    version = data.get("version", "")
    mode = data.get("mode", "auto")
    if not version:
        raise HTTPException(status_code=400, detail="version required")
    result = await perform_update(version, mode=mode)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Update failed"))
    return result


@router.get("/api/update/status")
async def api_update_status():
    """Return the current app-package update status."""
    return get_update_status()


@router.post("/api/update/rollback")
async def api_update_rollback():
    """Rollback to the previous app-package version."""
    result = await rollback_app_package()
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Rollback failed"))
    return result


@router.get("/api/update/changelog")
async def api_update_changelog(version: str = Query(...)):
    """Fetch full CHANGELOG (release body) from GitHub for a specific version."""
    body = await fetch_github_release_body(version)
    return {"version": version, "body": body}
