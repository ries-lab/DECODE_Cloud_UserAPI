import dotenv

dotenv.load_dotenv()

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from api import dependencies, settings, tags
from api.database import engine, Base
from api.endpoints import auth, auth_get, files, jobs, job_update
from api.exceptions import register_exception_handlers


Base.metadata.create_all(bind=engine)

app = FastAPI(openapi_tags=tags.tags_metadata)
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
async def root():
    return "Welcome to the DECODE OpenCloud User-facing API"
