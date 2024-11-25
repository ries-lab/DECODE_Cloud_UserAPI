import datetime
import enum

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import mapped_column

from api.database import Base


class JobStates(enum.Enum):
    queued = "queued"
    pulled = "pulled"
    preprocessing = "preprocessing"
    running = "running"
    postprocessing = "postprocessing"
    finished = "finished"
    error = "error"


class EnvironmentTypes(enum.Enum):
    cloud = "cloud"
    local = "local"
    any = None


class OutputEndpoints(enum.Enum):
    output = "output"
    log = "log"
    artifact = "artifact"


class UploadFileTypes(enum.Enum):
    config = "config"
    data = "data"
    artifact = "artifact"


class Job(Base):
    __tablename__ = "jobs"

    id = mapped_column(Integer, primary_key=True, index=True)
    user_id = mapped_column(String, nullable=False)
    user_email = mapped_column(String, nullable=True)  # required for notifications
    job_name = mapped_column(String)
    date_created = mapped_column(DateTime, default=datetime.datetime.utcnow)
    date_started = mapped_column(DateTime)
    date_finished = mapped_column(DateTime)
    status = mapped_column(
        String, Enum(JobStates), nullable=False, default=JobStates.queued.value
    )
    paths_out = mapped_column(JSON, nullable=False)
    runtime_details = mapped_column(Text, nullable=True)
    environment = mapped_column(Enum(EnvironmentTypes))
    priority = mapped_column(Integer, nullable=False, default=0)
    application = mapped_column(JSON, nullable=False)
    attributes = mapped_column(JSON, nullable=False)
    hardware = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "job_name", name="_user_job_name_unique"),
    )
