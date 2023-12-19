from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import api.crud.job as job_crud
import api.database as database
from api import settings
from api.models import JobStates
from api.schemas.job_update import JobUpdate
from api.dependencies import workerfacing_api_auth_dep


router = APIRouter(dependencies=[Depends(workerfacing_api_auth_dep)])


@router.put("/_job_status", status_code=204)
def update_job(update: JobUpdate, db: Session = Depends(database.get_db)):
    db_job = job_crud.get_job(db, update.job_id)
    if db_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    db_job.status = update.status.value
    db.add(db_job)
    db.commit()
    if (
        update.status.value in [JobStates.finished.value, JobStates.error.value]
        and db_job.user_email
    ):
        subject = f"Job {db_job.job_name} (id={db_job.id}) {db_job.status}"
        body = f"""This is an update for job {db_job.job_name} (id={db_job.id}).
            The job is now {db_job.status}.\n
            If you would like not to receive such updates in the future, contact the developers.
            At the moment, the selection of whether to receive updates or not is not supported.
        """
        settings.email_sender.send_email(
            to=db_job.user_email, subject=subject, body=body
        )
