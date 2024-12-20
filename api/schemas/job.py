import datetime
from typing import Any

from pydantic import BaseModel, validator

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

    @validator("application")
    def application_check(cls: "Application", v: str, values: dict[str, str]) -> str:
        allowed = list(settings.application_config.config.keys())
        if v not in allowed:
            raise ValueError(f"Application must be one of {allowed}, not {v}.")
        return v

    @validator("version")
    def version_check(cls: "Application", v: str, values: dict[str, str]) -> str:
        if "application" not in values:
            raise ValueError("Application must be set before version.")
        allowed = settings.application_config.config[values["application"]].keys()
        if v not in allowed:
            raise ValueError(f"Version must be one of {allowed}, not {v}.")
        return v

    @validator("entrypoint")
    def entrypoint_check(cls: "Application", v: str, values: dict[str, str]) -> str:
        if "application" not in values or "version" not in values:
            raise ValueError("Application and version must be set before entrypoint.")
        allowed = settings.application_config.config[values["application"]][
            values["version"]
        ].keys()
        if v not in allowed:
            raise ValueError(f"Entrypoint must be one of {allowed}, not {v}.")
        return v


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
    priority: int | None = None
    application: Application
    attributes: JobAttributes
    hardware: HardwareSpecs | None = None

    @validator("attributes")
    def env_check(
        cls: "JobBase", v: JobAttributes, values: dict[str, Any]
    ) -> JobAttributes:
        app = values.get("application")
        if not app:
            raise ValueError("Application must be set before attributes.")
        application = (
            app.application if hasattr(app, "application") else app["application"]
        )
        version = app.version if hasattr(app, "version") else app["version"]
        entrypoint = app.entrypoint if hasattr(app, "entrypoint") else app["entrypoint"]
        config = settings.application_config.config[application][version][entrypoint]
        allowed = config["app"]["env"]
        if v.env_vars is not None and not all(v_ in allowed for v_ in v.env_vars):
            raise ValueError(f"Environment variables must be in {allowed}.")
        return v

    @validator("priority")
    def priority_check(cls: "JobBase", v: int | None, values: dict[str, Any]) -> int:
        if v is None:
            v = 0
        elif v < 0 or v > 5:
            raise ValueError(f"Priority must be between 0 and 5, not {v}.")
        return v


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
