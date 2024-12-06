from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import api.database as database
from api.crud import job as crud
from api.dependencies import enqueueing_function_dep
from api.schemas.job import Job, JobCreate, QueueJob
from api.settings import application_config

router = APIRouter()


ApplicationConfig = dict[str, dict[str, dict[str, Any]]]


@router.get(
    "/jobs/applications",
    response_model=ApplicationConfig,
    description="List all available applications/versions/entrypoints",
)
def list_applications() -> ApplicationConfig:
    return application_config.config


@router.get("/jobs", response_model=list[Job], description="List all jobs")
def list_jobs(
    request: Request,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
) -> list[Job]:
    return sorted(
        crud.get_jobs(db, request.state.current_user.username, offset, limit),
        key=lambda x: x.date_created,
        reverse=True,
    )


@router.get("/jobs/{job_id}", response_model=Job, description="Describe a job")
def describe_job(
    request: Request, job_id: int, db: Session = Depends(database.get_db)
) -> Job:
    db_job = crud.get_job(db, job_id)
    if db_job is None or db_job.user_id != request.state.current_user.username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return db_job


@router.post(
    "/jobs",
    status_code=status.HTTP_201_CREATED,
    response_model=Job,
    description="Start a job",
)
def start_job(
    request: Request,
    job: JobCreate,
    db: Session = Depends(database.get_db),
    enqueueing_func: Callable[[QueueJob], None] = Depends(enqueueing_function_dep),
) -> Job:
    try:
        return crud.create_job(
            db,
            enqueueing_func,
            job,
            user_id=request.state.current_user.username,
            user_email=request.state.current_user.email,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    description="Delete a job",
)
def delete_job(
    request: Request, job_id: int, db: Session = Depends(database.get_db)
) -> None:
    db_job = crud.get_job(db, job_id)
    if db_job is None or db_job.user_id != request.state.current_user.username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    crud.delete_job(db, db_job)
