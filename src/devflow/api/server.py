"""DevFlow Web UI — 文件夹上传 + AI 编程助手

FastAPI + Jinja2 模板，支持 ZIP 项目上传和 AI 任务提交。
"""

import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import structlog
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from devflow.config import load_config
from devflow.core.agent import Agent
from devflow.history.store import ConversationStore
from devflow.llm import create_llm_provider
from devflow.tools import create_tool_registry
from devflow.tools.base import _safe_path, set_safe_root

logger = structlog.get_logger()

app = FastAPI()
UPLOADS = Path("uploads").resolve()
UPLOADS.mkdir(exist_ok=True)

# 模板目录
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def get_agent() -> Agent:
    """FastAPI 依赖注入：创建并返回 Agent 实例。"""
    config = load_config()
    if not config.llm.api_key.get_secret_value():
        raise HTTPException(status_code=400, detail="请设置 DEEPSEEK_API_KEY")
    llm_provider = create_llm_provider(config.llm)
    tools = create_tool_registry()
    return Agent(llm_provider, tools, config=config)


class TaskRequest(BaseModel):
    task: str
    project: str = ""


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/projects")
async def list_projects():
    projects = []
    for d in sorted(UPLOADS.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if d.is_dir():
            files = list(d.rglob("*"))
            file_count = sum(1 for f in files if f.is_file())
            projects.append({
                "name": d.name,
                "file_count": file_count,
                "modified": datetime.fromtimestamp(d.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return {"projects": projects}


@app.post("/api/upload")
async def upload_project(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".zip"):
        return JSONResponse({"error": "请上传 .zip 文件"}, status_code=400)

    # 文件大小限制 50MB
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return JSONResponse({"error": "上传文件超过 50MB 限制"}, status_code=400)

    project_name = Path(file.filename).stem
    safe_name = "".join(c for c in project_name if c.isalnum() or c in "._-")
    if not safe_name:
        return JSONResponse({"error": "无效的项目名"}, status_code=400)

    dest = UPLOADS / safe_name

    # 备份已存在的项目（避免数据丢失）
    if dest.exists():
        backup_name = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = UPLOADS / backup_name
        try:
            shutil.move(str(dest), str(backup_path))
            logger.info(f"已备份旧项目: {safe_name} -> {backup_name}")
        except Exception as e:
            return JSONResponse(
                {"error": f"备份旧项目失败: {str(e)}"},
                status_code=500
            )

    temp_zip = UPLOADS / f"{safe_name}.zip"
    temp_zip.write_bytes(content)

    try:
        with zipfile.ZipFile(temp_zip) as zf:
            infos = zf.infolist()

            # 检查 1：文件数量限制
            if len(infos) > 100:
                logger.warning(
                    "上传被拒绝：文件数量过多",
                    project=safe_name,
                    file_count=len(infos),
                )
                return JSONResponse({"error": "超过 100 个文件限制"}, status_code=400)

            # 检查 2：解压后大小限制
            total_size = sum(info.file_size for info in infos)
            if total_size > 100 * 1024 * 1024:
                logger.warning(
                    "上传被拒绝：解压后过大",
                    project=safe_name,
                    total_size_mb=total_size / (1024 * 1024),
                )
                return JSONResponse({"error": "解压后超过 100MB 限制"}, status_code=400)

            # 检查 3：ZIP 炸弹检测（压缩比异常）
            compressed_size = sum(info.compress_size for info in infos)
            if compressed_size > 0:
                ratio = total_size / compressed_size
                if ratio > 100:  # 压缩比超过 100 倍，可能是 ZIP 炸弹
                    logger.warning(
                        "上传被拒绝：检测到 ZIP 炸弹",
                        project=safe_name,
                        compression_ratio=ratio,
                    )
                    return JSONResponse(
                        {"error": "检测到 ZIP 炸弹攻击（压缩比异常）"},
                        status_code=400
                    )

            # 检查 4：路径遍历防护
            for info in infos:
                # 检查文件名是否包含路径遍历
                if '..' in info.filename or info.filename.startswith('/'):
                    logger.warning(
                        "上传被拒绝：ZIP 包含非法路径",
                        project=safe_name,
                        illegal_path=info.filename,
                    )
                    return JSONResponse(
                        {"error": f"ZIP 中包含非法路径: {info.filename}"},
                        status_code=400
                    )

            logger.info(
                "开始解压 ZIP",
                project=safe_name,
                file_count=len(infos),
                total_size=total_size,
            )
            zf.extractall(dest)
            logger.info("ZIP 解压成功", project=safe_name)
    except zipfile.BadZipFile:
        logger.warning("上传被拒绝：无效的 ZIP 文件", project=safe_name)
        return JSONResponse({"error": "无效的 zip 文件"}, status_code=400)
    except Exception as e:
        logger.error("解压失败", project=safe_name, error=str(e))
        return JSONResponse({"error": f"解压失败: {str(e)}"}, status_code=500)
    finally:
        # 清理临时文件
        if temp_zip.exists():
            temp_zip.unlink()

    files = list(dest.rglob("*"))
    file_count = sum(1 for f in files if f.is_file())
    return {"success": True, "name": safe_name, "file_count": file_count}


@app.delete("/api/projects/{name}")
async def delete_project(name: str):
    dest = UPLOADS / name
    if not dest.exists():
        return JSONResponse({"error": "项目不存在"}, status_code=404)
    shutil.rmtree(dest)
    return {"success": True, "name": name}


@app.post("/api/run")
async def run_task(req: TaskRequest, agent: Agent = Depends(get_agent)):
    repo_path = UPLOADS / req.project if req.project else Path(".").resolve()
    set_safe_root(repo_path)
    result = await agent.run(req.task, repo_path)
    steps = []
    if result.plan:
        steps = [
            {
                "index": sr.step.index,
                "description": sr.step.description[:120],
                "success": sr.success,
                "output": (sr.output or "")[:300],
            }
            for sr in result.step_results
        ]
    verify_errors = []
    if result.verify_result:
        verify_errors = [e.message for e in result.verify_result.errors]
    return {
        "success": result.success,
        "error": result.error,
        "steps": steps,
        "files_modified": result.files_modified,
        "verify": {
            "passed": result.verify_result.passed if result.verify_result else True,
            "errors": verify_errors,
        },
    }


@app.post("/api/run/stream")
async def run_task_stream(req: TaskRequest):
    """流式执行任务（SSE）"""
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    from devflow.core.agent import Agent
    from devflow.llm import create_llm_provider
    from devflow.tools import create_tool_registry
    from devflow.tools.base import set_safe_root

    repo_path = UPLOADS / req.project if req.project else Path(".").resolve()
    set_safe_root(repo_path)

    config = load_config()
    llm_provider = create_llm_provider(config.llm)
    tools = create_tool_registry()
    event_queue = asyncio.Queue()
    agent = Agent(llm_provider, tools, config=config, event_queue=event_queue)

    async def event_generator():
        # 启动 Agent 任务
        task = asyncio.create_task(agent.run(req.task, repo_path))

        while True:
            event = await event_queue.get()
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["type"] == "complete":
                break

        # 等待 Agent 任务完成，获取最终结果
        result = await task
        result_data = json.dumps({
            "success": result.success,
            "error": result.error,
            "files_modified": result.files_modified,
            "total_tokens": result.total_tokens,
            "total_cost": result.total_cost_usd,
        })
        yield f"event: result\ndata: {result_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ========== 对话历史 API ==========

store = ConversationStore()


class CreateConversationRequest(BaseModel):
    project: str
    task: str


@app.get("/api/conversations")
async def list_conversations(project: str = ""):
    """获取会话列表"""
    conversations = store.list_conversations(project=project or None)
    return {
        "conversations": [
            {
                "id": c.id,
                "project": c.project,
                "task": c.task,
                "status": c.status,
                "success": c.success,
                "total_tokens": c.total_tokens,
                "created_at": c.created_at,
            }
            for c in conversations
        ]
    }


@app.post("/api/conversations")
async def create_conversation(req: CreateConversationRequest):
    """创建新会话"""
    conv = store.create_conversation(req.project, req.task)
    return {"id": conv.id, "project": conv.project, "task": conv.task}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取会话详情（包含消息）"""
    conv = store.get_conversation(conversation_id)
    if not conv:
        return JSONResponse({"error": "会话不存在"}, status_code=404)

    messages = store.get_messages(conversation_id)
    return {
        "id": conv.id,
        "project": conv.project,
        "task": conv.task,
        "status": conv.status,
        "success": conv.success,
        "error": conv.error,
        "total_tokens": conv.total_tokens,
        "files_modified": conv.files_modified,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "metadata": m.metadata,
            }
            for m in messages
        ],
    }


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除会话"""
    store.delete_conversation(conversation_id)
    return {"success": True}


# ========== 文件管理 API ==========


@app.get("/api/files")
async def list_files(path: str = ""):
    """列出目录内容"""
    try:
        target = _safe_path(path) if path else _safe_path(".")
        if not target.exists():
            return JSONResponse({"error": "路径不存在"}, status_code=404)

        if target.is_file():
            return {"type": "file", "name": target.name, "path": path}

        items = []
        for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            items.append({
                "name": item.name,
                "path": str(item.relative_to(_safe_path("."))),
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
                "modified": datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        return {"path": path, "items": items}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/files/content")
async def get_file_content(path: str):
    """读取文件内容"""
    try:
        file_path = _safe_path(path)
        if not file_path.exists():
            return JSONResponse({"error": "文件不存在"}, status_code=404)
        if not file_path.is_file():
            return JSONResponse({"error": "不是文件"}, status_code=400)

        # 限制文件大小（最大 1MB）
        if file_path.stat().st_size > 1024 * 1024:
            return JSONResponse({"error": "文件超过 1MB 限制"}, status_code=400)

        content = file_path.read_text(encoding="utf-8", errors="replace")
        return {"path": path, "content": content}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


class SaveFileRequest(BaseModel):
    path: str
    content: str


@app.post("/api/files/content")
async def save_file_content(req: SaveFileRequest):
    """保存文件内容"""
    try:
        file_path = _safe_path(req.path)
        file_path.write_text(req.content, encoding="utf-8")
        return {"success": True, "path": req.path}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.delete("/api/files")
async def delete_file(path: str):
    """删除文件或文件夹"""
    try:
        target = _safe_path(path)
        if not target.exists():
            return JSONResponse({"error": "路径不存在"}, status_code=404)

        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"success": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


class RenameRequest(BaseModel):
    old_path: str
    new_path: str


@app.post("/api/files/rename")
async def rename_file(req: RenameRequest):
    """重命名文件或文件夹"""
    try:
        old = _safe_path(req.old_path)
        new = _safe_path(req.new_path)
        if not old.exists():
            return JSONResponse({"error": "源路径不存在"}, status_code=404)

        old.rename(new)
        return {"success": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/files/search")
async def search_files(q: str, path: str = ""):
    """搜索文件名"""
    try:
        target = _safe_path(path) if path else _safe_path(".")
        if not target.exists() or not target.is_dir():
            return JSONResponse({"error": "无效的搜索路径"}, status_code=400)

        results = []
        for item in target.rglob(f"*{q}*"):
            if item.is_file():
                results.append({
                    "name": item.name,
                    "path": str(item.relative_to(_safe_path("."))),
                })
            if len(results) >= 50:  # 限制结果数量
                break
        return {"query": q, "results": results}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def main():
    import uvicorn
    uvicorn.run("devflow.api.server:app", host="0.0.0.0", port=8000, reload=True)
