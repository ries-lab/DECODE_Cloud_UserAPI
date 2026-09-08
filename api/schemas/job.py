import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from api import settings
from api.models import EnvironmentTypes, JobStates, OutputEndpoints


class HardwareSpecs(BaseModel):
    cpu_cores: int | None = None
    memory: int | None = None
    gpu_model: str | None = None
    gpu_archi: str | None = None
    gpu_mem: int | None = None


class Application(BaseModel):
    application: str
    version: str
    entrypoint: str

    @model_validator(mode="after")
    def application_check(self) -> Self:
        allowed_apps = list(settings.application_config.config.keys())
        if self.application not in allowed_apps:
            raise ValueError(
                f"Application must be one of {allowed_apps}, not {self.application}."
            )
        allowed_versions = list(
            settings.application_config.config[self.application].keys()
        )
        if self.version not in allowed_versions:
            raise ValueError(
                f"Version must be one of {allowed_versions}, not {self.version}."
            )
        allowed_entrypoints = list(
            settings.application_config.config[self.application][self.version].keys()
        )
        if self.entrypoint not in allowed_entrypoints:
            raise ValueError(
                f"Entrypoint must be one of {allowed_entrypoints}, not {self.entrypoint}."
            )
        return self


class InputJobAttributes(BaseModel):
    config_id: str | None = None
    data_ids: list[str] | None = None
    artifact_ids: list[str] | None = None


class JobAttributes(BaseModel):
    files_down: InputJobAttributes
    env_vars: dict[str, str] | None = None


class JobBase(BaseModel):
    job_name: str
    environment: EnvironmentTypes | None = None
    priority: int = Field(0, ge=0, le=5)
    application: Application
    attributes: JobAttributes
    hardware: HardwareSpecs | None = None

    @model_validator(mode="after")
    def env_check(self) -> Self:
        config = settings.application_config.config[self.application.application][
            self.application.version
        ][self.application.entrypoint]
        allowed_env_vars = config["app"]["env"]
        if self.attributes.env_vars is not None and not all(
            v_ in allowed_env_vars for v_ in self.attributes.env_vars
        ):
            raise ValueError(f"Environment variables must be in {allowed_env_vars}.")
        return self


class JobReadBase(BaseModel):
    id: int
    date_created: datetime.datetime
    date_started: datetime.datetime | None
    date_finished: datetime.datetime | None
    status: JobStates
    runtime_details: str | None = None
    paths_out: dict[OutputEndpoints, str]


class JobCreate(JobBase):
    pass


class Job(JobBase, JobReadBase):
    user_id: str
    user_email: str | None = None

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "job_name": "decode_analysis_job",
                "environment": "cpu",
                "priority": 1,
                "application": {
                    "application": "decode", 
                    "version": "latest",
                    "entrypoint": "analysis"
                },
                "attributes": {
                    "files_down": {
                        "config_id": "config_123",
                        "data_ids": ["data_456", "data_789"],
                        "artifact_ids": ["artifact_abc"]
                    },
                    "env_vars": {
                        "PARAM1": "value1",
                        "PARAM2": "value2"
                    }
                },
                "hardware": {
                    "cpu_cores": 4,
                    "memory": 8192,
                    "gpu_model": None,
                    "gpu_archi": None,
                    "gpu_mem": None
                },
                "id": 12345,
                "date_created": "2023-12-01T10:00:00Z",
                "date_started": "2023-12-01T10:05:00Z",
                "date_finished": "2023-12-01T11:30:00Z",
                "status": "finished",
                "runtime_details": "Job completed successfully",
                "paths_out": {
                    "output": "/outputs/results/",
                    "log": "/outputs/logs/job.log",
                    "artifact": "/outputs/artifacts/"
                },
                "user_id": "user@example.com",
                "user_email": "user@example.com"
            }
        }


class MetaSpecs(BaseModel):
    job_id: int
    date_created: datetime.datetime

    class Config:
        extra = "allow"


class AppSpecs(BaseModel):
    cmd: list[str] | None = None
    env: dict[str, str] | None = None


class HandlerSpecs(BaseModel):
    image_url: str
    image_name: str | None = None
    image_version: str | None = None
    entrypoint: str | None = None
    files_down: dict[str, str] | None = None  # local_path: fs_path
    files_up: dict[OutputEndpoints, str]  # endpoint: local_path


class JobSpecs(BaseModel):
    app: AppSpecs
    handler: HandlerSpecs
    meta: MetaSpecs
    hardware: HardwareSpecs


class PathsUploadSpecs(BaseModel):
    output: str
    log: str
    artifact: str


class QueueJob(BaseModel):
    job: JobSpecs
    environment: EnvironmentTypes | None = None
    group: str | None = None
    priority: int | None = None
    paths_upload: PathsUploadSpecs
