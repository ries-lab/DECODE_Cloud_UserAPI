import abc
import io
import os
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Generator, cast

import boto3
import humanize
from botocore.client import Config
from botocore.response import StreamingBody
from botocore.utils import fix_s3_host
from fastapi import Request
from fastapi.responses import FileResponse, StreamingResponse
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.type_defs import ObjectIdentifierTypeDef

from api import models, settings
from api.schemas.file import FileHTTPRequest, FileInfo, FileTypes


class FileSystem(abc.ABC):
    def __init__(self, root_path: str, predef_dirs: list[str] | None = None):
        self.root_path = root_path
        self._predef_dirs = predef_dirs or []
        self.init()

    def init(self) -> None:
        for dir in self._predef_dirs + [""]:
            self.create_directory(dir + "/")

    def create_directory(self, path: str) -> None:
        raise NotImplementedError()

    def list_directory(
        self, path: str = "", dirs: bool = True, recursive: bool = False
    ) -> Generator[FileInfo, Any, None]:
        normalized_path = path if path.endswith("/") else path + "/"
        if not self.isdir(normalized_path):
            raise NotADirectoryError(path)
        return self._directory_contents(normalized_path, dirs=dirs, recursive=recursive)

    def _directory_contents(
        self, path: str, dirs: bool = True, recursive: bool = False
    ) -> Generator[FileInfo, Any, None]:
        raise NotImplementedError()

    def get_file_info(self, path: str) -> FileInfo:
        raise NotImplementedError()

    def create_file(self, path: str, file: BinaryIO) -> None:
        raise NotImplementedError()

    def create_file_url(
        self, path: str, request: Request, url_endpoint: str, upload_endpoint: str
    ) -> FileHTTPRequest:
        raise NotImplementedError()

    def rename(self, path: str, new_name: str) -> None:
        if not self.exists(path):
            raise FileNotFoundError(path)
        if self.isdir(path):
            if len(list(self.list_directory(path, dirs=True))):
                raise IsADirectoryError("Cannot rename a non-empty directory")
            elif path.strip("/") in self._predef_dirs:
                raise IsADirectoryError("Cannot rename a predefined directory")
        self._rename_file(path, new_name)

    def _rename_file(self, path: str, new_name: str) -> None:
        raise NotImplementedError()

    def delete(self, path: str, reinit_if_root: bool = True) -> None:
        if not self.exists(path):
            return
        if self.isdir(path):
            self._delete_directory(path)
            if (path == "/" or path == "") and reinit_if_root:
                self.init()
            elif path.strip("/") in self._predef_dirs:
                self.create_directory(path)
        else:
            self._delete_file(path)

    def _delete_file(self, path: str) -> None:
        raise NotImplementedError()

    def _delete_directory(self, path: str) -> None:
        raise NotImplementedError()

    def exists(self, path: str) -> bool:
        raise NotImplementedError()

    def isdir(self, path: str) -> bool:
        raise NotImplementedError()

    def full_path_uri(self, path: str) -> str:
        raise NotImplementedError()

    def full_path(self, path: str) -> str:
        # For some reason, PurePosixPath returns the root path if one of the components has root path
        full = str(
            PurePosixPath(self.root_path, path[1:] if path.startswith("/") else path)
        )
        return full if not path.endswith("/") else full + "/"

    def download(self, path: str) -> FileResponse | StreamingResponse:
        raise NotImplementedError()

    def download_url(
        self, path: str, request: Request, url_endpoint: str, download_endpoint: str
    ) -> FileHTTPRequest:
        raise NotImplementedError()


class LocalFilesystem(FileSystem):
    """A filesystem that uses the local filesystem."""

    def create_directory(self, path: str) -> None:
        os.makedirs(self.full_path(path), exist_ok=True)

    def _directory_contents(
        self, path: str, dirs: bool = True, recursive: bool = False
    ) -> Generator[FileInfo, Any, None]:
        if not recursive:
            files = os.listdir(self.full_path(path))
        else:
            files = [
                os.path.relpath(str(f), self.full_path(path))
                for f in Path(self.full_path(path)).rglob("*")
            ]
        if not dirs:
            files = [
                f
                for f in files
                if not os.path.isdir(os.path.join(self.full_path(path), f))
            ]
        for file in files:
            yield self.get_file_info((path if path != "/" else "") + file)

    def get_file_info(self, path: str) -> FileInfo:
        metadata = os.stat(self.full_path(path))
        isdir = self.isdir(path)
        return FileInfo(
            path=path + "/" if isdir else path,
            type=FileTypes.directory if isdir else FileTypes.file,
            size=humanize.naturalsize(metadata.st_size) if not isdir else "",
        )

    def create_file(self, path: str, file: BinaryIO) -> None:
        dir_path = self.full_path(os.path.join(*os.path.split(path)[:-1]))
        os.makedirs(dir_path, exist_ok=True)
        with open(self.full_path(path), "wb") as f:
            shutil.copyfileobj(file, f)

    def create_file_url(
        self, path: str, request: Request, url_endpoint: str, upload_endpoint: str
    ) -> FileHTTPRequest:
        return FileHTTPRequest(
            url=re.sub(url_endpoint, upload_endpoint, request.url._url),
            headers={"authorization": request.headers.get("authorization")},
            method="post",
        )

    def delete(self, path: str, reinit_if_root: bool = True) -> None:
        if not self.exists(path):
            return
        super().delete(path, reinit_if_root)

    def _rename_file(self, path: str, new_path: str) -> None:
        self.create_directory(os.path.dirname(new_path))
        os.rename(self.full_path(path), self.full_path(new_path))

    def _delete_file(self, path: str) -> None:
        os.remove(self.full_path(path))

    def _delete_directory(self, path: str) -> None:
        shutil.rmtree(self.full_path(path))

    def exists(self, path: str) -> bool:
        return os.path.exists(self.full_path(path))

    def isdir(self, path: str) -> bool:
        if path == "/":
            return True
        return os.path.isdir(self.full_path(path))

    def full_path_uri(self, path: str) -> str:
        return self.full_path(path)

    def download(self, path: str) -> FileResponse | StreamingResponse:
        if not self.exists(path):
            raise FileNotFoundError()
        if self.isdir(path):
            zip_io = io.BytesIO()
            with zipfile.ZipFile(
                zip_io, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as temp_zip:
                for fpath in self.list_directory(path, dirs=False, recursive=True):
                    temp_zip.write(
                        self.full_path(str(fpath.path)),
                        os.path.relpath(str(fpath.path), path),
                    )
            return StreamingResponse(
                iter([zip_io.getvalue()]),
                media_type="application/x-zip-compressed",
                headers={
                    "Content-Disposition": f"attachment; filename={path[:-1]}.zip"
                },
            )
        else:
            return FileResponse(self.full_path(path))

    def download_url(
        self, path: str, request: Request, url_endpoint: str, download_endpoint: str
    ) -> FileHTTPRequest:
        if not self.exists(path):
            raise FileNotFoundError()
        return FileHTTPRequest(
            url=re.sub(url_endpoint, download_endpoint, request.url._url),
            headers={"authorization": request.headers.get("authorization")},
            method="get",
        )


class S3Filesystem(FileSystem):
    """A filesystem that uses S3."""

    def __init__(
        self,
        root_path: str,
        s3_client: S3Client,
        bucket: str,
        predef_dirs: list[str] | None = None,
    ):
        self.s3_client = s3_client
        self.bucket = bucket
        super().__init__(root_path=root_path, predef_dirs=predef_dirs)

    def create_directory(self, path: str) -> None:
        self.s3_client.put_object(Bucket=self.bucket, Key=self.full_path(path))

    def _directory_contents(
        self, path: str, dirs: bool = True, recursive: bool = False
    ) -> Generator[FileInfo, Any, None]:
        full_path = self.full_path(path)
        paginator = self.s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(
            Bucket=self.bucket, Prefix=full_path, Delimiter="/"
        )

        for page in page_iterator:
            for key in page.get("Contents", []):
                if key["Key"] == full_path:
                    continue
                yield FileInfo(
                    path=key["Key"][len(str(self.root_path)) + 1 :],
                    type=FileTypes.file,
                    size=humanize.naturalsize(key["Size"]),
                )
            for key_prefix in page.get("CommonPrefixes", []):
                dir_path = key_prefix["Prefix"][len(str(self.root_path)) + 1 :]
                if dirs:
                    yield FileInfo(path=dir_path, type=FileTypes.directory, size="")
                if recursive:
                    for ret in self._directory_contents(
                        dir_path, dirs=dirs, recursive=recursive
                    ):
                        yield ret

    def get_file_info(self, path: str) -> FileInfo:
        metadata = self.s3_client.head_object(
            Bucket=self.bucket, Key=self.full_path(path)
        )
        return FileInfo(
            path=path,
            type=FileTypes.file,
            size=humanize.naturalsize(metadata["ContentLength"]),
        )

    def create_file(self, path: str, file: BinaryIO) -> None:
        self.s3_client.upload_fileobj(file, self.bucket, self.full_path(path))

    def create_file_url(
        self, path: str, request: Request, url_endpoint: str, upload_endpoint: str
    ) -> FileHTTPRequest:
        bucket = self.bucket
        path = self.full_path(path)
        if path[-1] != "/":
            path = path + "/"

        ret = self.s3_client.generate_presigned_post(
            Bucket=bucket,
            Key=path + "${filename}",
            Fields=None,
            Conditions=[
                ["starts-with", "$key", path]
            ],  # can be used for multiple uploads to folder
            ExpiresIn=60 * 10,
        )
        return FileHTTPRequest(
            url=ret["url"],
            data=ret["fields"],
            method="post",
        )

    def _rename_file(self, path: str, new_path: str) -> None:
        self.s3_client.copy_object(
            Bucket=self.bucket,
            Key=self.full_path(new_path),
            CopySource={"Bucket": self.bucket, "Key": self.full_path(path)},
        )
        self.s3_client.delete_object(Bucket=self.bucket, Key=self.full_path(path))

    def _delete_file(self, path: str) -> None:
        self.s3_client.delete_object(Bucket=self.bucket, Key=self.full_path(path))

    def _delete_directory(self, path: str) -> None:
        paginator = self.s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(
            Bucket=self.bucket, Prefix=self.full_path(path)
        )
        delete_objects: list[ObjectIdentifierTypeDef] = []
        for page in page_iterator:
            for key in page.get("Contents", []):
                delete_objects.append({"Key": key["Key"]})
        self.s3_client.delete_objects(
            Bucket=self.bucket, Delete={"Objects": delete_objects}
        )

    def exists(self, path: str) -> bool:
        objects = self.s3_client.list_objects_v2(
            Bucket=self.bucket, Prefix=self.full_path(path), MaxKeys=1
        )
        return "Contents" in objects

    def isdir(self, path: str) -> bool:
        if path == "/":
            return True
        return self.exists(path) and path.endswith("/")

    def full_path_uri(self, path: str) -> str:
        return "s3://" + self.bucket + "/" + self.full_path(path)

    def download(self, path: str) -> StreamingResponse:
        if not self.exists(path):
            raise FileNotFoundError()

        def _get_file_content(path: str) -> StreamingBody:
            return self.s3_client.get_object(
                Bucket=self.bucket, Key=self.full_path(path)
            )["Body"]

        if self.isdir(path):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file in self.list_directory(path, dirs=False, recursive=True):
                    fpath = str(file.path)
                    zipf.writestr(
                        os.path.relpath(fpath, path), _get_file_content(fpath).read()
                    )
            zip_buffer.seek(0)
            headers = {
                "Content-Disposition": f"attachment; filename={path[:-1]}.zip",
                "Content-Type": "application/zip",
            }
            return StreamingResponse(io.BytesIO(zip_buffer.read()), headers=headers)
        else:
            return StreamingResponse(content=_get_file_content(path).iter_chunks())

    def download_url(
        self, path: str, request: Request, url_endpoint: str, download_endpoint: str
    ) -> FileHTTPRequest:
        bucket = self.bucket
        path = self.full_path(path)
        response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=path)
        if "Contents" not in response:
            raise FileNotFoundError()
        return FileHTTPRequest(
            url=self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": path},
                ExpiresIn=60 * 10,
            ),
            method="get",
        )


def get_filesystem_with_root(root_path: str) -> FileSystem:
    """Get the filesystem to use."""
    predef_dirs = [e.value for e in models.UploadFileTypes] + [
        e.value for e in models.OutputEndpoints
    ]
    if settings.filesystem == "s3":
        s3_client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=f"https://s3.{settings.s3_region}.amazonaws.com",
            config=Config(signature_version="v4", s3={"addressing_style": "path"}),
        )
        # this and config=... required to avoid DNS problems with new buckets
        s3_client.meta.events.unregister("before-sign.s3", fix_s3_host)
        return S3Filesystem(
            root_path, s3_client, cast(str, settings.s3_bucket), predef_dirs=predef_dirs
        )
    elif settings.filesystem == "local":
        return LocalFilesystem(root_path, predef_dirs=predef_dirs)
    else:
        raise ValueError("Invalid filesystem setting")


def get_user_filesystem(user_id: str) -> FileSystem:
    """Get the filesystem to use for a user."""
    return get_filesystem_with_root(str(Path(settings.user_data_root_path) / user_id))
