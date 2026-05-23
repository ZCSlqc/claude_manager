"""统一响应格式。"""


def err(code: int, pid: str = "", msg: str = "") -> dict:
    return {"success": False, "code": code, "detail": {"project_id": pid, "error": msg}}


def ok(code: int, data: dict | list | None = None) -> dict:
    if isinstance(data, dict):
        return {"success": True, "code": code, "detail": {"project_id": "", "error": "", **data}}
    return {"success": True, "code": code, "detail": data or []}
