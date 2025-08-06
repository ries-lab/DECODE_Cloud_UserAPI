import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse

from api import models
from api.core.filesystem import FileSystem
from api.dependencies import filesystem_dep
from api.schemas import file as file_schemas
from api.schemas.common import ErrorResponse

router = APIRouter()


@router.get(
    "/files/{file_path:path}/download",
    response_model=None,
    response_class=Response,
    status_code=status.HTTP_200_OK,
    description="Download a file from the file system",
    responses={
        200: {"description": "File successfully downloaded"},
        404: {"description": "File not found", "model": ErrorResponse}
    }
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
    status_code=status.HTTP_200_OK,
    description="Get request parameters (pre-signed URL) to download a file",
    responses={
        200: {"description": "Successfully generated download URL", "model": file_schemas.FileHTTPRequest},
        404: {"description": "File not found", "model": ErrorResponse}
    }
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
    status_code=status.HTTP_200_OK,
    description="List files and directories in a specified path",
    responses={
        200: {"description": "Successfully retrieved file listing", "model": list[file_schemas.FileInfo]},
        404: {"description": "Directory not found", "model": ErrorResponse}
    }
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
    description="Upload a file to the specified path",
    responses={
        201: {"description": "File successfully uploaded", "model": file_schemas.FileInfo},
        400: {"description": "Invalid upload parameters", "model": ErrorResponse}
    }
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
    responses={
        201: {"description": "Successfully generated upload URL", "model": file_schemas.FileHTTPRequest},
        400: {"description": "Invalid parameters", "model": ErrorResponse}
    }
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
    response_model=None,
    description="Create a new directory at the specified path",
    responses={
        201: {"description": "Directory successfully created"},
        400: {"description": "Invalid directory parameters", "model": ErrorResponse}
    }
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
    status_code=status.HTTP_200_OK,
    description="Rename or move a file to a new path",
    responses={
        200: {"description": "File successfully renamed/moved", "model": file_schemas.FileInfo},
        404: {"description": "File not found", "model": ErrorResponse},
        405: {"description": "Operation not allowed (e.g., trying to rename directory)", "model": ErrorResponse}
    }
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
    description="Delete a file or directory and all its contents",
    responses={
        204: {"description": "File or directory successfully deleted"},
        404: {"description": "File or directory not found", "model": ErrorResponse}
    }
)
def delete_file(
    file_path: str, filesystem: FileSystem = Depends(filesystem_dep)
) -> None:
    filesystem.delete(file_path)
