"""项目 & 用户 CRUD 路由。"""

import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..db import (
    delete_project, delete_user, get_project, get_user_by_id, list_projects, list_users,
)
from ..response import ok as _ok

router = APIRouter()


# ── 清理辅助 ──

def _clean_project_files(project: dict):
    """清理项目的会话文件和项目文件夹。"""
    session_id = project.get("session_id", "")
    claude_path = project.get("claude_path", "")

    if session_id:
        claude_dir = Path(os.path.expanduser("~/.claude/projects"))
        for p in claude_dir.rglob(f"{session_id}.jsonl"):
            p.unlink()
            break
        session_dir = claude_dir / session_id
        if session_dir.is_dir():
            shutil.rmtree(session_dir)

    if claude_path:
        claude_project_dir = Path(os.path.expanduser(claude_path))
        if claude_project_dir.is_dir():
            shutil.rmtree(claude_project_dir)

    folder_name = project.get("folder_name", "")
    if folder_name:
        folder_path = Path(folder_name)
        if folder_path.is_dir() and not any(folder_path.iterdir()):
            folder_path.rmdir()


def _cleanup_claude_dir():
    """清理 ~/.claude/projects 下的空目录。"""
    claude_dir = Path(os.path.expanduser("~/.claude/projects"))
    if not claude_dir.is_dir():
        return
    for item in list(claude_dir.iterdir()):
        if item.is_dir() and not any(item.iterdir()):
            shutil.rmtree(item)


# ── User ──

@router.get("/users")
def list_users_endpoint():
    return _ok(list_users())


@router.delete("/users/{user_id}")
def delete_user_endpoint(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, f"用户不存在: {user_id}")

    # 删除用户所有项目
    for project in list_projects(user_id):
        pid = project.get("subprocess_pid", 0)
        if pid > 0:
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        _clean_project_files(project)
        delete_project(project["project_id"])

    # 清理空目录
    _cleanup_claude_dir()

    # 删用户
    delete_user(user_id)
    return _ok(200, {"deleted": user_id})


# ── Project ──

@router.get("/projects")
def list_projects_endpoint(user_id: str | None = None):
    return _ok(list_projects(user_id))


@router.get("/projects/{project_id}")
def get_project_endpoint(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")
    return _ok(project)


@router.patch("/projects/{project_id}")
def update_project_endpoint(project_id: str, body: dict):
    from ..db import update_project as _up
    project = _up(project_id, **body)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")
    return _ok(project)


@router.delete("/projects/{project_id}")
def delete_project_endpoint(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, f"项目不存在: {project_id}")

    pid = project.get("subprocess_pid", 0)
    if pid > 0:
        try:
            os.kill(pid, 9)
        except OSError:
            pass

    _clean_project_files(project)
    _cleanup_claude_dir()

    delete_project(project_id)
    return _ok(200, {"deleted": project_id})
