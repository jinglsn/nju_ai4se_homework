from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from src.memory.store import MemoryStore


def create_app(workspace: Path | None = None) -> FastAPI:
    app = FastAPI(title="Harness Dashboard")

    if workspace is None:
        workspace = Path.cwd()

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        store = MemoryStore(workspace / ".harness")
        data = store.load()
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Harness Dashboard</title>
        <style>body{{font-family:monospace;max-width:800px;margin:40px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}}
        pre{{background:#16213e;padding:15px;border-radius:8px;overflow-x:auto}}
        .card{{background:#16213e;padding:15px;border-radius:8px;margin:10px 0}}</style></head>
        <body>
        <h1>Harness Dashboard</h1>
        <div class="card"><h3>Status</h3><p>Workspace: {workspace}</p></div>
        <div class="card"><h3>Project</h3><pre>{_format_json(data.get("project", {}))}</pre></div>
        <div class="card"><h3>Conventions</h3><pre>{_format_json(data.get("conventions", {}))}</pre></div>
        <div class="card"><h3>Fix History ({len(data.get("fix_history", []))} records)</h3><pre>{_format_json(data.get("fix_history", [])[-5:])}</pre></div>
        <div class="card"><h3>Audit Log ({len(data.get("audit_log", []))} entries)</h3><pre>{_format_json(data.get("audit_log", [])[-10:])}</pre></div>
        </body></html>"""

    @app.get("/api/status")
    async def api_status():
        return {"workspace": str(workspace), "status": "running"}

    @app.get("/api/memory")
    async def api_memory():
        store = MemoryStore(workspace / ".harness")
        return store.load()

    return app


def _format_json(data, indent=2):
    import json
    return json.dumps(data, ensure_ascii=False, indent=indent, default=str)


app = create_app()