from pydantic import BaseModel

from api.models import JobStates


class JobUpdate(BaseModel):
    job_id: int
    status: JobStates
    runtime_details: str | None = None

    class Config:
        schema_extra = {
            "example": {
                "job_id": 12345,
                "status": "finished",
                "runtime_details": "Job completed successfully in 45 minutes"
            }
        }
