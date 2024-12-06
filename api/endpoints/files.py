import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse

from api import models
from api.core.filesystem import FileSystem
from api.dependencies import filesystem_dep
from api.schemas import file as file_schemas

router = APIRouter()


@router.get(
    "/files/{file_path:path}/download",
    response_model=None,
    response_class=Response,
    description="Download a file",
)
def download_file(
    file_path: str, filesystem: FileSystem = Depends(filesystem_dep)
) -> FileResponse | StreamingResponse:
    try:
        return filesystem.download(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get(
    "/files/{file_path:path}/url",
    response_model=file_schemas.FileHTTPRequest,
    description="Get request parameters (pre-signed URL) to download a file",
)
def get_download_presigned_url(
    file_path: str, request: Request, filesystem: FileSystem = Depends(filesystem_dep)
) -> file_schemas.FileHTTPRequest:
    try:
        return filesystem.download_url(
            file_path, request, re.escape("/url") + "$", "/download"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get(
    "/files/{base_path:path}",
    response_model=list[file_schemas.FileInfo],
    description="List files in a directory",
)
def list_files(
    base_path: str = "",
    show_dirs: bool = True,
    recursive: bool = False,
    filesystem: FileSystem = Depends(filesystem_dep),
) -> list[file_schemas.FileInfo]:
    try:
        return sorted(
            filesystem.list_directory(base_path, dirs=show_dirs, recursive=recursive),
            key=lambda x: x.path,
        )
    except NotADirectoryError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/files/{f_type}/{base_path:path}/upload",
    response_model=file_schemas.FileInfo,
    status_code=status.HTTP_201_CREATED,
    description="Upload a file",
)
def upload_file(
    f_type: models.UploadFileTypes,
    base_path: str,
    file: UploadFile,
    filesystem: FileSystem = Depends(filesystem_dep),
) -> file_schemas.FileInfo:
    base_path = f"{f_type.value}/" + base_path
    file_path = os.path.join(base_path, file.filename or "unnamed")
    filesystem.create_file(file_path, file.file)
    return filesystem.get_file_info(file_path)


@router.post(
    "/files/{f_type}/{base_path:path}/url",
    status_code=status.HTTP_201_CREATED,
    response_model=file_schemas.FileHTTPRequest,
    description="Get request parameters (pre-signed URL) to upload a file",
)
def get_upload_presigned_url(
    f_type: models.UploadFileTypes,
    base_path: str,
    request: Request,
    filesystem: FileSystem = Depends(filesystem_dep),
) -> file_schemas.FileHTTPRequest:
    base_path = f"{f_type.value}/" + base_path
    return filesystem.create_file_url(
        base_path, request, re.escape("/url") + "$", "/upload"
    )


@router.post(
    "/files/{f_type}/{base_path:path}/",
    status_code=status.HTTP_201_CREATED,
    description="Create a directory",
)
def create_directory(
    f_type: models.UploadFileTypes,
    base_path: str,
    filesystem: FileSystem = Depends(filesystem_dep),
) -> None:
    return filesystem.create_directory(f"{f_type.value}/{base_path}/")


@router.put(
    "/files/{file_path:path}",
    response_model=file_schemas.FileInfo,
    description="Rename a file",
)
def rename_file(
    file_path: str,
    file: file_schemas.FileUpdate,
    filesystem: FileSystem = Depends(filesystem_dep),
) -> file_schemas.FileInfo:
    try:
        filesystem.rename(file_path, file.path)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    except IsADirectoryError as e:
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail=str(e),
        )
    return filesystem.get_file_info(file.path)


@router.delete(
    "/files/{file_path:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    description="Delete a file or directory",
)
def delete_file(
    file_path: str, filesystem: FileSystem = Depends(filesystem_dep)
) -> None:
    filesystem.delete(file_path)
