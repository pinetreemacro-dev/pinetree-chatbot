from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.admin import router as admin_router
from backend.api.cron import router as cron_router
from backend.api.routes import router
from backend.core.security import require_admin
from backend.chatbot.engine import ChatEngine
from backend.core.config import settings
from backend.database import models  # noqa: F401
from backend.database.database import Base, engine
from backend.services.retention import purge_old_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    app.state.engine = ChatEngine()
    scheduler = None
    if not settings.serverless:  # serverless hosts call /api/internal/purge from their own cron instead
        purge_old_data()
        scheduler = BackgroundScheduler()
        scheduler.add_job(purge_old_data, "cron", hour=2)
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="PineTree Chatbot", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                   allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(router)
app.include_router(admin_router)
app.include_router(cron_router)
NO_CACHE = {"Cache-Control": "no-cache"}


class FreshStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/static", FreshStaticFiles(directory=settings.frontend_dir), name="static")


@app.get("/", include_in_schema=False)
def chat_page():
    return FileResponse(settings.frontend_dir / "index.html", headers=NO_CACHE)


@app.get("/admin", include_in_schema=False, dependencies=[Depends(require_admin)])
def admin_page():
    return FileResponse(settings.frontend_dir / "admin.html", headers=NO_CACHE)
