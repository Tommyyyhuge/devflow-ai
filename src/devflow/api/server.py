"""DevFlow Web UI — 文件夹上传 + AI 编程助手

Week 2 升级：使用 Jinja2 模板，前后端分离。
"""

import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from devflow.config import load_config
from devflow.core.agent import Agent
from devflow.llm import DeepSeekClient
from devflow.tools import create_tool_registry
from devflow.tools.base import set_safe_root

app = FastAPI()
UPLOADS = Path("uploads").resolve()
UPLOADS.mkdir(exist_ok=True)

# 模板目录
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class TaskRequest(BaseModel):
    task: str
    project: str = ""


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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
    if dest.exists():
        shutil.rmtree(dest)

    temp_zip = UPLOADS / f"{safe_name}.zip"
    temp_zip.write_bytes(content)

    try:
        with zipfile.ZipFile(temp_zip) as zf:
            infos = zf.infolist()
            if len(infos) > 100:
                temp_zip.unlink()
                return JSONResponse({"error": "超过 100 个文件限制"}, status_code=400)
            total_size = sum(info.file_size for info in infos)
            if total_size > 100 * 1024 * 1024:
                temp_zip.unlink()
                return JSONResponse({"error": "解压后超过 100MB 限制"}, status_code=400)
            zf.extractall(dest)
    except zipfile.BadZipFile:
        temp_zip.unlink()
        return JSONResponse({"error": "无效的 zip 文件"}, status_code=400)
    finally:
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
async def run_task(req: TaskRequest):
    config = load_config()
    if not config.llm.api_key.get_secret_value():
        return JSONResponse({"error": "请设置 DEEPSEEK_API_KEY"}, status_code=400)

    repo_path = UPLOADS / req.project if req.project else Path(".").resolve()
    set_safe_root(repo_path)
    client = DeepSeekClient(config.llm)
    tools = create_tool_registry()
    agent = Agent(client, tools, config=config)
    result = await agent.run(req.task, repo_path)
    return {
        "success": result.success, "error": result.error,
        "steps": [{"index": sr.step.index, "description": sr.step.description[:120], "success": sr.success, "output": (sr.output or "")[:300]} for sr in result.step_results] if result.plan else [],
        "files_modified": result.files_modified,
        "verify": {"passed": result.verify_result.passed if result.verify_result else True, "errors": [e.message for e in result.verify_result.errors] if result.verify_result else []},
    }


def main():
    import uvicorn
    uvicorn.run("devflow.api.server:app", host="0.0.0.0", port=8000, reload=True)
