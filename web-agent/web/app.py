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
    async def run_stream(session_id: str, task: str = Query(...)):
        try:
            loop = sessions.get_loop(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        async def event_generator():
            async for event in loop.run_stream(task):
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
            dest = ws / f.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
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
        return {"status": "saved", "filename": filename}

    @app.get("/api/session/{session_id}/files")
    async def list_files(session_id: str):
        try:
            ws = sessions.get_workspace(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        files = []
        for p in ws.rglob("*"):
            if p.is_file() and ".harness" not in p.parts:
                files.append(str(p.relative_to(ws)))
        return {"files": sorted(files)}

    @app.get("/api/session/{session_id}/download")
    async def download_files(session_id: str):
        try:
            ws = sessions.get_workspace(session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Session not found")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in ws.rglob("*"):
                if p.is_file() and ".harness" not in p.parts:
                    zf.write(p, p.relative_to(ws))
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=modified_code.zip"},
        )

    return app


def _load_html() -> str:
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<html><body><h1>Web Agent Harness</h1><p>Static file not found</p></body></html>"


app = create_app()