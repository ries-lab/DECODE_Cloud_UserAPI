import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import dotenv

dotenv.load_dotenv()

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import dependencies, settings, tags
from api.core.database import Database
from api.endpoints import auth, auth_get, files, job_update, jobs
from api.exceptions import register_exception_handlers

logger = logging.getLogger(__name__)


async def cron_backup_database(db: Database) -> None:
    while True:
        logger.info("Database backup: starting...")
        # Run backup in thread pool to avoid blocking event loop;
        # Fine instead of making backup async since it runs infrequently.
        try:
            if await asyncio.to_thread(db.backup):
                logger.info("Backed up database.")
        except Exception as e:
            logger.error(f"Database backup failed with {e}")
        await asyncio.sleep(settings.cron_backup_interval)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    db = app.dependency_overrides.get(dependencies.db_dep, dependencies.db_dep)()
    assert isinstance(db, Database)
    db.create()
    task_backup = asyncio.create_task(cron_backup_database(db))
    yield
    task_backup.cancel()
    await asyncio.gather(task_backup, return_exceptions=True)
    if db.backup():
        logger.info("Created final backup on shutdown.")


app = FastAPI(openapi_tags=tags.tags_metadata, lifespan=lifespan)
if settings.frontend_url:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app.include_router(
    files.router,
    tags=["Files"],
    dependencies=[Depends(dependencies.current_user_global_dep)],
)
app.include_router(
    jobs.router,
    tags=["Jobs"],
    dependencies=[Depends(dependencies.current_user_global_dep)],
)
if settings.auth:
    app.include_router(auth.router, tags=["Authentication"])
app.include_router(auth_get.router, tags=["Authentication"])
# private endpoint for worker-facing API
app.include_router(job_update.router, tags=["_Internal"])

register_exception_handlers(app)


@app.get("/")
async def root() -> str:
    return "Welcome to the DECODE OpenCloud User-facing API"
