from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Any

import api.database as database
from api.crud import job as crud
from api.dependencies import enqueueing_function_dep
from api.schemas.job import Job, JobCreate
from api.settings import application_config


router = APIRouter()


@router.get("/jobs/applications")
def list_applications():
    return application_config.config


@router.get("/jobs", response_model=list[Job])
def list_jobs(
    request: Request,
    offset: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
):
    return sorted(
        crud.get_jobs(db, request.state.current_user.username, offset, limit),
        key=lambda x: x.date_created,
        reverse=True,
    )


@router.get("/jobs/{job_id}", response_model=Job)
def describe_job(request: Request, job_id: int, db: Session = Depends(database.get_db)):
    db_job = crud.get_job(db, job_id)
    if db_job is None or db_job.user_id != request.state.current_user.username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return db_job


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def start_job(
    request: Request,
    job: JobCreate,
    db: Any = Depends(database.get_db),
    enqueueing_func: callable = Depends(enqueueing_function_dep),
):
    return crud.create_job(
        db,
        enqueueing_func,
        job,
        user_id=request.state.current_user.username,
        user_email=request.state.current_user.email,
    )


@router.delete("/jobs/{job_id}", response_model=Job)
def delete_job(request: Request, job_id: int, db: Session = Depends(database.get_db)):
    db_job = crud.get_job(db, job_id)
    if db_job is None or db_job.user_id != request.state.current_user.username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    crud.delete_job(db, db_job)
    return db_job
