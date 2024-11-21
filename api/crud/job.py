import os
from datetime import datetime
from typing import Callable, cast

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api import models, settings
from api.core.filesystem import FileSystem, get_user_filesystem
from api.schemas import job as schemas


def enqueue_job(
    job: models.Job, enqueueing_func: Callable[[schemas.QueueJob], None]
) -> None:
    user_fs = get_user_filesystem(user_id=cast(str, job.user_id))

    app = job.application
    job_config = settings.application_config.config[app["application"]][app["version"]][
        app["entrypoint"]
    ]

    # Handler parameters
    handler_config = job_config["handler"]

    def prepare_files(root_in: str, root_out: str, fs: FileSystem) -> dict[str, str]:
        root_in_dir = root_in + ("/" if not root_in[-1] == "/" else "")
        out_files = {}
        if not fs.isdir(root_in_dir):
            in_files = [root_in]
        else:
            in_files = [
                f.path
                for f in fs.list_directory(root_in_dir, dirs=False, recursive=True)
            ]
        for in_f in in_files:
            out_files[f"{root_out}/{os.path.relpath(in_f, root_in)}"] = (
                fs.full_path_uri(in_f)
            )
        return out_files

    config_path = f"config/{job.attributes['files_down']['config_id']}"
    data_paths = [
        f"data/{data_id}"
        for data_id in cast(list[str], job.attributes["files_down"]["data_ids"])
    ]
    artifact_paths = [
        f"artifact/{artifact_id}"
        for artifact_id in cast(list[str], job.attributes["files_down"]["artifact_ids"])
    ]
    _validate_files(user_fs, [config_path] + data_paths + artifact_paths)
    roots_down = handler_config["files_down"]
    files_down = prepare_files(config_path, roots_down["config_id"], user_fs)
    for data_path in data_paths:
        files_down.update(prepare_files(data_path, roots_down["data_ids"], user_fs))
    for artifact_path in artifact_paths:
        files_down.update(
            prepare_files(artifact_path, roots_down["artifact_ids"], user_fs)
        )

    app_specs = schemas.AppSpecs(
        cmd=cast(list[str] | None, job_config["app"]["cmd"]),
        env=cast(dict[str, str], job.attributes["env_vars"]),
    )
    handler_specs = schemas.HandlerSpecs(
        image_name=cast(str | None, app["application"]),
        image_version=cast(str | None, app["version"]),
        entrypoint=cast(str | None, app["entrypoint"]),
        image_url=cast(str, handler_config["image_url"]),
        files_down=cast(dict[str, str] | None, files_down),
        files_up=cast(dict[models.OutputEndpoints, str], handler_config["files_up"]),
    )
    meta_specs = schemas.MetaSpecs(
        job_id=cast(int, job.id), date_created=cast(datetime, job.date_created)
    )
    hardware_specs = schemas.HardwareSpecs(**job.hardware)
    job_specs = schemas.JobSpecs(
        app=app_specs, handler=handler_specs, meta=meta_specs, hardware=hardware_specs
    )

    paths_upload = {
        "output": user_fs.full_path_uri(cast(str, job.paths_out["output"])),
        "log": user_fs.full_path_uri(cast(str, job.paths_out["log"])),
        "artifact": user_fs.full_path_uri(cast(str, job.paths_out["artifact"])),
    }

    queue_item = schemas.QueueJob(
        job=job_specs,
        environment=(
            cast(models.EnvironmentTypes, job.environment)
            if job.environment
            else models.EnvironmentTypes.any
        ),
        group=None,  # TODO
        priority=cast(int, job.priority),
        paths_upload=cast(schemas.PathsUploadSpecs, paths_upload),
    )
    enqueueing_func(queue_item)


def get_jobs(
    db: Session, user_id: int, offset: int = 0, limit: int = 100
) -> list[models.Job]:
    return (
        db.query(models.Job)
        .filter(models.Job.user_id == user_id)
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_job(db: Session, job_id: int) -> models.Job | None:
    return db.query(models.Job).get(job_id)


def _validate_files(filesystem: FileSystem, paths: list[str]) -> None:
    for _file in paths:
        if not filesystem.exists(_file):
            raise HTTPException(status_code=400, detail=f"File {_file} does not exist")


def create_job(
    db: Session,
    enqueueing_func: Callable[[schemas.QueueJob], None],
    job: schemas.JobCreate,
    user_id: int,
    user_email: str | None = None,
) -> models.Job:
    try:
        paths_out = {
            "output": f"output/{job.job_name}",
            "log": f"log/{job.job_name}",
            "artifact": f"artifact/{job.job_name}",
        }
        db_job = models.Job(
            **job.model_dump(),
            user_id=user_id,
            user_email=user_email,
            paths_out=paths_out,
        )
        db.add(db_job)
        db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job name must be unique",
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ve,
        )
    enqueue_job(db_job, enqueueing_func)
    db.commit()
    db.refresh(db_job)
    return db_job


def delete_job(db: Session, db_job: models.Job) -> models.Job:
    db.delete(db_job)
    user_fs = get_user_filesystem(user_id=cast(str, db_job.user_id))
    for path in cast(dict[str, str], db_job.paths_out).values():
        if path[-1] != "/":
            path += "/"
        user_fs.delete(path)
    db.commit()
    return db_job
