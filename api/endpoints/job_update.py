import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import api.core.notifications as notifications
import api.crud.job as job_crud
from api.database import get_db
from api.dependencies import email_sender_dep, workerfacing_api_auth_dep
from api.models import JobStates
from api.schemas.job_update import JobUpdate

router = APIRouter(dependencies=[Depends(workerfacing_api_auth_dep)])


@router.put(
    "/_job_status",
    response_model=JobStates,
    description="Internal endpoint for the worker-facing API to signal job status updates",
)
def update_job_status(
    update: JobUpdate,
    db: Session = Depends(get_db),
    email_sender: notifications.EmailSender = Depends(email_sender_dep),
) -> JobStates:
    db_job = job_crud.get_job(db, update.job_id)
    if db_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    # Update the status
    db_job.status = update.status.value
    
    # Update date_started when job is first pulled/started
    if update.status == JobStates.pulled and db_job.date_started is None:
        db_job.date_started = datetime.datetime.now(datetime.timezone.utc)
    
    # Update date_finished when job reaches a terminal state
    if (
        update.status in [JobStates.finished, JobStates.error] 
        and db_job.date_finished is None
    ):
        db_job.date_finished = datetime.datetime.now(datetime.timezone.utc)
    
    if update.runtime_details:
        db_job.runtime_details = (
            (db_job.runtime_details or "") + "\n" + update.runtime_details
        )
    db.add(db_job)
    db.commit()
    if (
        update.status.value in [JobStates.finished.value, JobStates.error.value]
        and db_job.user_email
    ):
        subject = f"Job {db_job.job_name} (id={db_job.id}) {db_job.status}"
        body = f"""This is an update for job '{db_job.job_name}': (id={db_job.id}).
            Status: {db_job.status}.\n\n
            Job run-time details:\n{db_job.runtime_details}\n\n
            If you would like not to receive such updates in the future, contact the developers.
            At the moment, the selection of whether to receive updates or not is not supported.
        """.replace("\n", "<br>")
        email_sender.send_email(to=db_job.user_email, subject=subject, body=body)
    return update.status
