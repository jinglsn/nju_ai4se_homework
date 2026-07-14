import json
import shutil
import tempfile
import zipfile
import io
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from pydantic import BaseModel
from web.session_manager import SessionManager


class CreateSessionRequest(BaseModel):
    api_key: str


def _save_original(workspace: Path, rel_path: str) -> None:
    """Save a copy of the file in .originals/ for before/after comparison."""
    src = workspace / rel_path
    if not src.is_file():
        return
    dest = workspace / ".originals" / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _get_original_path(workspace: Path, filepath: str) -> Path | None:
    """Get the path to the original copy of a file, if it exists."""
    orig = workspace / ".originals" / filepath
    return orig if orig.is_file() else None


def _is_modified(workspace: Path, filepath: str) -> bool:
    """Check if the current file differs from its original."""
    orig = _get_original_path(workspace, filepath)
    if orig is None:
        return False
    current = workspace / filepath
    if not current.is_file():
        return False
    return orig.read_bytes() != current.read_bytes()


def create_app(workspace: Path | None = None) -> FastAPI:
    app = FastAPI(title="Web Agent Harness")
    sessions = SessionManager()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _load_html()

    @app.post("/api/session")
    async def create_session(req: CreateSessionRequest):
        if not req.api_key.strip():
            raise HTTPException(status_code=400, detail="API key is required")
        sid = sessions.create_session(api_key=req.api_key.strip())
        return {"session_id": sid}

    @app.get("/api/session/{session_id}/stream")
    async def run_stream(session_id: str, task: str = Query(...), selected_files: str = Query("")):
        try:
            loop = sessions.get_loop(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        file_list = [f.strip() for f in selected_files.split(",") if f.strip()]

        async def event_generator():
            async for event in loop.run_stream(task, selected_files=file_list):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.websocket("/ws/{session_id}")
    async def ws_hitl(websocket: WebSocket, session_id: str):
        await websocket.accept()
        try:
            loop = sessions.get_loop(session_id)
        except KeyError:
            await websocket.close(code=4004)
            return

        hitl = loop.hitl
        while True:
            try:
                data = await websocket.receive_json()
                if data.get("action") == "resolve":
                    approved = data.get("approved", False)
                    hitl.resolve_decision(approved)
                    await websocket.send_json({"status": "resolved", "approved": approved})
            except WebSocketDisconnect:
                break
            except Exception:
                break

    @app.delete("/api/session/{session_id}")
    async def destroy_session(session_id: str):
        try:
            sessions.destroy_session(session_id)
            return {"status": "deleted"}
        except Exception:
            raise HTTPException(status_code=404, detail="Session not found")

    @app.get("/api/status")
    async def api_status():
        return {
            "status": "running",
            "active_sessions": len(sessions._sessions),
        }

    @app.post("/api/session/{session_id}/upload")
    async def upload_files(session_id: str, files: list[UploadFile] = File(...)):
        try:
            ws = sessions.get_workspace(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        saved = []
        for f in files:
            content = await f.read()
            if f.filename and f.filename.lower().endswith(".zip"):
                extracted = _extract_zip(content, ws)
                for name in extracted:
                    _save_original(ws, name)
                saved.extend(extracted)
            else:
                dest = ws / f.filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                _save_original(ws, f.filename)
                saved.append(f.filename)
        return {"status": "uploaded", "files": saved}

    @app.post("/api/session/{session_id}/paste")
    async def paste_code(session_id: str, filename: str = Form(...), code: str = Form(...)):
        try:
            ws = sessions.get_workspace(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        dest = ws / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(code, encoding="utf-8")
        _save_original(ws, filename)
        return {"status": "saved", "filename": filename}

    @app.get("/api/session/{session_id}/file/{filepath:path}")
    async def get_file_content(session_id: str, filepath: str, version: str = Query("current")):
        try:
            ws = sessions.get_workspace(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        if version == "original":
            target = _get_original_path(ws, filepath)
            if target is None:
                raise HTTPException(status_code=404, detail="Original not found")
        else:
            target = ws / filepath

        target = target.resolve()
        if not str(target).startswith(str(ws.resolve())):
            raise HTTPException(status_code=403, detail="Path traversal denied")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Binary file cannot be previewed")

        return {
            "filename": filepath,
            "content": content,
            "size": target.stat().st_size,
            "version": version,
            "modified": _is_modified(ws, filepath) if version == "current" else False,
        }

    @app.get("/api/session/{session_id}/download/{filepath:path}")
    async def download_single_file(session_id: str, filepath: str, version: str = Query("current")):
        try:
            ws = sessions.get_workspace(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        if version == "original":
            target = _get_original_path(ws, filepath)
            if target is None:
                raise HTTPException(status_code=404, detail="Original not found")
        else:
            target = ws / filepath

        target = target.resolve()
        if not str(target).startswith(str(ws.resolve())):
            raise HTTPException(status_code=403, detail="Path traversal denied")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(target, filename=target.name)

    @app.get("/api/session/{session_id}/files")
    async def list_files(session_id: str):
        try:
            ws = sessions.get_workspace(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        files = []
        for p in ws.rglob("*"):
            if p.is_file() and ".originals" not in p.parts and ".harness" not in p.parts:
                rel = str(p.relative_to(ws)).replace("\\", "/")
                files.append({
                    "path": rel,
                    "size": p.stat().st_size,
                    "has_original": _get_original_path(ws, rel) is not None,
                    "modified": _is_modified(ws, rel),
                })
        return {"files": sorted(files, key=lambda f: f["path"])}

    @app.get("/api/session/{session_id}/download")
    async def download_files(session_id: str):
        try:
            ws = sessions.get_workspace(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in ws.rglob("*"):
                if p.is_file() and ".originals" not in p.parts and ".harness" not in p.parts:
                    zf.write(p, p.relative_to(ws))
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=modified_code.zip"},
        )

    return app


def _extract_zip(content: bytes, workspace: Path) -> list[str]:
    """Extract a ZIP file into workspace, guarding against path traversal."""
    extracted = []
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        workspace_resolved = workspace.resolve()
        for entry in zf.namelist():
            member = zf.getinfo(entry)
            if member.is_dir():
                continue
            dest = (workspace / entry).resolve()
            if not str(dest).startswith(str(workspace_resolved)):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(entry))
            extracted.append(entry)
    return extracted


def _load_html() -> str:
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<html><body><h1>Web Agent Harness</h1><p>Static file not found</p></body></html>"


app = create_app()