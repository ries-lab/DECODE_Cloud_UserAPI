import os
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api import models, schemas, settings
from api.core.filesystem import get_user_filesystem


def enqueue_job(job: models.Job, enqueueing_func: callable):
    user_fs = get_user_filesystem(user_id=job.user_id)

    app = job.application
    job_config = settings.application_config.config[app["application"]][app["version"]][
        app["entrypoint"]
    ]

    # Handler parameters
    handler_config = job_config["handler"]

    def prepare_files(root_in, root_out, fs):
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
            out_files[
                f"{root_out}/{os.path.relpath(in_f, root_in)}"
            ] = fs.full_path_uri(in_f)
        return out_files

    config_path = f"config/{job.attributes['files_down']['config_id']}"
    data_paths = [
        f"data/{data_id}" for data_id in job.attributes["files_down"]["data_ids"]
    ]
    artifact_paths = [
        f"artifact/{artifact_id}"
        for artifact_id in job.attributes["files_down"]["artifact_ids"]
    ]
    _validate_files(user_fs, [config_path] + data_paths + artifact_paths)
    files_down = prepare_files(config_path, "config", user_fs)
    for data_path in data_paths:
        files_down.update(prepare_files(data_path, "data", user_fs))
    for artifact_path in artifact_paths:
        files_down.update(prepare_files(artifact_path, "artifact", user_fs))

    app_specs = schemas.AppSpecs(
        cmd=job_config["app"]["cmd"], env=job.attributes["env_vars"]
    )
    handler_specs = schemas.HandlerSpecs(
        image_name=app["application"],
        image_version=app["version"],
        entrypoint=app["entrypoint"],
        image_url=handler_config["image_url"],
        files_down=files_down,
        files_up=handler_config["files_up"],
    )
    meta_specs = schemas.MetaSpecs(job_id=job.id, date_created=job.date_created)
    hardware_specs = schemas.HardwareSpecs(**job.hardware)
    job_specs = schemas.JobSpecs(
        app=app_specs, handler=handler_specs, meta=meta_specs, hardware=hardware_specs
    )

    paths_upload = {
        "output": user_fs.full_path_uri(job.paths_out["output"]),
        "log": user_fs.full_path_uri(job.paths_out["log"]),
        "artifact": user_fs.full_path_uri(job.paths_out["artifact"]),
    }

    queue_item = schemas.QueueJob(
        job=job_specs,
        environment=job.environment if job.environment else models.EnvironmentTypes.any,
        group=None,  # TODO
        priority=job.priority,
        paths_upload=paths_upload,
    )
    enqueueing_func(queue_item)


def get_jobs(db: Session, user_id: int, offset: int = 0, limit: int = 100):
    return (
        db.query(models.Job)
        .filter(models.Job.user_id == user_id)
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_job(db: Session, job_id: int):
    return db.query(models.Job).get(job_id)


def _validate_files(filesystem, paths: list[str]):
    for _file in paths:
        if not filesystem.exists(_file):
            raise HTTPException(status_code=400, detail=f"File {_file} does not exist")


def create_job(
    db: Session,
    enqueueing_func: callable,
    job: schemas.JobCreate,
    user_id: int,
    user_email: str | None = None,
):
    try:
        paths_out = {
            "output": f"output/{job.job_name}",
            "log": f"log/{job.job_name}",
            "artifact": f"artifact/{job.job_name}",
        }
        db_job = models.Job(
            **job.dict(), user_id=user_id, user_email=user_email, paths_out=paths_out
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
