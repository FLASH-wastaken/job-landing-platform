from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .models.database import Base, engine
from .routers import candidates, applications, dashboard, jobs, agent, discovery, alerts

Base.metadata.create_all(bind=engine)


# Background scheduler for job alerts
_scheduler_task = None


async def _alert_scheduler_loop():
    """Run all active job alerts every 5 minutes."""
    from .services.alert_monitor import run_all_alerts
    while True:
        try:
            results = await run_all_alerts()
            new_total = sum(r.get("new_jobs", 0) for r in results)
            if new_total > 0:
                print(f"[AlertMonitor] Found {new_total} new jobs across {len(results)} alerts")
        except Exception as e:
            print(f"[AlertMonitor] Error: {e}")
        await asyncio.sleep(300)  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler_task
    _scheduler_task = asyncio.create_task(_alert_scheduler_loop())
    print("[AlertMonitor] Background job alert monitor started")
    yield
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    print("[AlertMonitor] Background monitor stopped")


app = FastAPI(
    title="Job Landing Platform",
    description="Help talented people land interviews faster with tailored resumes, smart tracking, and proactive outreach suggestions.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidates.router)
app.include_router(applications.router)
app.include_router(dashboard.router)
app.include_router(jobs.router)
app.include_router(agent.router)
app.include_router(discovery.router)
app.include_router(alerts.router)


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.1.0"}


# Serve React frontend in production
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        """Serve React app for all non-API routes (SPA fallback)."""
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
