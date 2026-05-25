from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path

from .models.database import Base, engine
from .routers import candidates, applications, dashboard

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Job Landing Platform",
    description="Help talented people land interviews faster with tailored resumes, smart tracking, and proactive outreach suggestions.",
    version="1.0.0",
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


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}


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
