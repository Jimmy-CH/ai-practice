"""前端静态产物托管与 SPA 回退路由。"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match


def register_static(app: FastAPI, static_dir: Path) -> None:
    """挂载前端产物与 SPA 回退；目录不存在时跳过（开发模式不受影响）。

    必须在所有 API 路由注册之后调用，避免 catch-all 拦截 /api。
    """
    if not static_dir.is_dir():
        return
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # catch-all 会拦截 Starlette 的尾斜杠重定向，这里用框架真实路由匹配补偿该行为
    # （include_router 生成的路由无 path 属性，不能用路径字符串白名单）
    def _matches_other_route(path: str, method: str) -> bool:
        scope = {"type": "http", "path": path, "method": method, "headers": []}
        for route in app.routes:
            if getattr(route, "path", None) == "/{full_path:path}":
                continue
            match, _child = route.matches(scope)
            if match != Match.NONE:
                return True
        return False

    def _partial_match_methods(path: str, method: str) -> list[str]:
        """路径已注册但方法不匹配时返回允许的方法，复刻原生 405/Allow 语义。"""
        scope = {"type": "http", "path": path, "method": method, "headers": []}
        methods: set[str] = set()
        for route in app.routes:
            if getattr(route, "path", None) == "/{full_path:path}":
                continue
            match, _child = route.matches(scope)
            if match == Match.PARTIAL:
                methods |= _collect_methods(route, scope)
        return sorted(methods)

    def _collect_methods(route, scope: dict) -> set[str]:
        """聚合路由允许的方法；兼容无 methods 属性的聚合路由（FastAPI 0.141 _IncludedRouter）。"""
        methods = getattr(route, "methods", None)
        if methods:
            return {m for m in methods if m != "HEAD"}
        result: set[str] = set()
        inner = getattr(route, "original_router", None)
        for sub in getattr(inner, "routes", None) or []:
            match, _child = sub.matches(scope)
            if match != Match.NONE:
                result |= _collect_methods(sub, scope)
        return result

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        include_in_schema=False,
    )
    async def spa_fallback(request: Request, full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            if full_path.endswith("/"):
                target = "/" + full_path.rstrip("/")
                if _matches_other_route(target, request.method):
                    query = request.scope.get("query_string", b"")
                    location = target + (f"?{query.decode('latin-1')}" if query else "")
                    return RedirectResponse(location, status_code=307)
            else:
                allowed = _partial_match_methods("/" + full_path, request.method)
                if allowed:
                    return JSONResponse(
                        {"detail": "Method Not Allowed"},
                        status_code=405,
                        headers={"Allow": ", ".join(allowed)},
                    )
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if request.method in ("GET", "HEAD"):
            candidate = (static_dir / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")
        return JSONResponse({"detail": "Not Found"}, status_code=404)
