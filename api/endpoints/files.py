import os
import re
from fastapi import APIRouter, HTTPException, UploadFile, status, Depends, Request

from api import models
import api.schemas as schemas
from api.dependencies import filesystem_dep


router = APIRouter()


@router.get("/files/{file_path:path}/download")
def download_file(file_path: str, filesystem=Depends(filesystem_dep)):
    ret = filesystem.download(file_path)
    if not ret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ret


@router.get("/files/{file_path:path}/url", response_model=schemas.file.FileHTTPRequest)
def get_download_presigned_url(
    file_path: str, request: Request, filesystem=Depends(filesystem_dep)
):
    ret = filesystem.download_url(
        file_path, request, re.escape("/url") + "$", "/download"
    )
    if not ret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ret


@router.get("/files/{base_path:path}", response_model=list[schemas.File])
def list_files(
    base_path: str | None = None,
    show_dirs: bool = True,
    recursive: bool = False,
    filesystem=Depends(filesystem_dep),
):
    return filesystem.list_directory(base_path, dirs=show_dirs, recursive=recursive)


@router.post(
    "/files/{f_type}/{base_path:path}/upload",
    response_model=schemas.File,
    status_code=status.HTTP_201_CREATED,
)
def upload_file(
    f_type: models.UploadFileTypes,
    base_path: str,
    file: UploadFile,
    filesystem=Depends(filesystem_dep),
):
    base_path = f"{f_type.value}/" + base_path
    file_path = os.path.join(base_path, file.filename)
    filesystem.create_file(file_path, file.file)
    return filesystem.get_file_info(file_path)


@router.post(
    "/files/{f_type}/{base_path:path}/url",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.file.FileHTTPRequest,
)
def get_upload_presigned_url(
    f_type: models.UploadFileTypes,
    base_path: str,
    request: Request,
    filesystem=Depends(filesystem_dep),
):
    base_path = f"{f_type.value}/" + base_path
    ret = filesystem.create_file_url(
        base_path, request, re.escape("/url") + "$", "/upload"
    )
    if not ret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ret


@router.post(
    "/files/{f_type}/{base_path:path}",
    status_code=status.HTTP_201_CREATED,
)
def create_folder(
    f_type: models.UploadFileTypes,
    base_path: str,
    filesystem=Depends(filesystem_dep),
):
    return filesystem.create_directory(f"{f_type.value}/" + base_path)


@router.put("/files/{file_path:path}", response_model=schemas.File)
def rename_file(
    file_path: str, file: schemas.FileUpdate, filesystem=Depends(filesystem_dep)
):
    filesystem.rename(file_path, file.path)
    return filesystem.get_file_info(file.path)


@router.delete("/files/{file_path:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_path: str, filesystem=Depends(filesystem_dep)):
    filesystem.delete(file_path)
    return {}
