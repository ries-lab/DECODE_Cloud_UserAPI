import dotenv

dotenv.load_dotenv()

from fastapi import FastAPI, Depends

from api import dependencies, settings, tags
from api.database import engine, Base
from api.endpoints import files, token, user, jobs, job_update, access
from api.exceptions import register_exception_handlers


Base.metadata.create_all(bind=engine)

app = FastAPI(openapi_tags=tags.tags_metadata)

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
if not settings.prod:
    app.include_router(user.router, tags=["Authentication"])
    app.include_router(token.router, tags=["Authentication"])
app.include_router(access.router, tags=["Authentication"])
# private endpoint for worker-facing API
app.include_router(job_update.router, tags=["_Internal"])

register_exception_handlers(app)


@app.get("/")
async def root():
    return {"message": "Welcome to the DECODE OpenCloud User-facing API"}
