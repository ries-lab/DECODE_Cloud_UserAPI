import abc
import boto3
import enum
import humanize
import io
import os
import re
import shutil
import zipfile
from collections import namedtuple
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path, PurePosixPath

from api import models, settings


class FileTypes(enum.Enum):
    file = "file"
    directory = "directory"


FileInfo = namedtuple("File", ["path", "type", "size"])


class FileSystem(abc.ABC):
    def __init__(self, root_path: str, predef_dirs: list[str] | None = None):
        self.root_path = root_path
        self._predef_dirs = predef_dirs or []
        self.init()

    def init(self):
        for dir in self._predef_dirs + [""]:
            self.create_directory(dir + "/")

    def create_directory(self, path: str):
        raise NotImplementedError()

    def list_directory(
        self, path: str = "", dirs: bool = True, recursive: bool = False
    ):
        normalized_path = path if path.endswith("/") else path + "/"
        if not self.isdir(normalized_path):
            raise NotADirectoryError(path)
        return self._directory_contents(normalized_path, dirs=dirs, recursive=recursive)

    def _directory_contents(
        self, path: str, dirs: bool = True, recursive: bool = False
    ):
        raise NotImplementedError()

    def get_file_info(self, path: str):
        raise NotImplementedError()

    def create_file(self, path: str, file):
        raise NotImplementedError()

    def create_file_url(
        self, path: str, request, url_endpoint: str, upload_endpoint: str
    ):
        raise NotImplementedError()

    def rename(self, path: str, new_name: str):
        if not self.exists(path):
            raise FileNotFoundError(path)
        if self.isdir(path):
            if len(list(self.list_directory(path, dirs=True))):
                raise IsADirectoryError("Cannot rename a non-empty directory")
            elif path.strip("/") in self._predef_dirs:
                raise IsADirectoryError("Cannot rename a predefined directory")
        return self._rename_file(path, new_name)

    def _rename_file(self, path: str, new_name: str):
        raise NotImplementedError()

    def delete(self, path: str, reinit_if_root: bool = True):
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

    def _delete_file(self, path: str):
        raise NotImplementedError()

    def _delete_directory(self, path: str):
        raise NotImplementedError()

    def exists(self, path: str):
        raise NotImplementedError()

    def isdir(self, path: str):
        raise NotImplementedError()

    def full_path_uri(self, path: str):
        raise NotImplementedError()

    def full_path(self, path: str):
        # For some reason, PurePosixPath returns the root path if one of the components has root path
        full = str(
            PurePosixPath(self.root_path, path[1:] if path.startswith("/") else path)
        )
        return full if not path.endswith("/") else full + "/"

    def download(self, path: str):
        raise NotImplementedError()

    def download_url(
        self, path: str, request, url_endpoint: str, download_endpoint: str
    ):
        raise NotImplementedError()


class LocalFilesystem(FileSystem):
    """A filesystem that uses the local filesystem."""

    def create_directory(self, path: str):
        os.makedirs(self.full_path(path), exist_ok=True)

    def _directory_contents(
        self, path: str, dirs: bool = True, recursive: bool = False
    ):
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

    def get_file_info(self, path: str):
        """Get file info."""
        metadata = os.stat(self.full_path(path))
        isdir = self.isdir(path)
        return FileInfo(
            path=path + "/" if isdir else path,
            type=FileTypes.directory if isdir else FileTypes.file,
            size=humanize.naturalsize(metadata.st_size) if not isdir else "",
        )

    def create_file(self, path, file):
        dir_path = self.full_path(os.path.join(*os.path.split(path)[:-1]))
        os.makedirs(dir_path, exist_ok=True)
        with open(self.full_path(path), "wb") as f:
            shutil.copyfileobj(file, f)

    def create_file_url(
        self, path: str, request, url_endpoint: str, upload_endpoint: str
    ):
        return {
            "url": re.sub(url_endpoint, upload_endpoint, request.url._url),
            "headers": {"authorization": request.headers.get("authorization")},
            "method": "post",
        }

    def delete(self, path: str, reinit_if_root: bool = True):
        if not self.exists(path):
            return
        super().delete(path, reinit_if_root)

    def _rename_file(self, path, new_path):
        os.rename(self.full_path(path), self.full_path(new_path))

    def _delete_file(self, path):
        os.remove(self.full_path(path))

    def _delete_directory(self, path):
        shutil.rmtree(self.full_path(path))

    def exists(self, path):
        """Check if a path exists."""
        return os.path.exists(self.full_path(path))

    def isdir(self, path):
        """Check if a path is a directory."""
        if path == "/":
            return True
        return os.path.isdir(self.full_path(path))

    def full_path_uri(self, path):
        return self.full_path(path)

    def download(self, path):
        if not self.exists(path):
            return None
        if self.isdir(path):
            zip_io = io.BytesIO()
            with zipfile.ZipFile(
                zip_io, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as temp_zip:
                for fpath in self.list_directory(path, dirs=False, recursive=True):
                    fpath = str(fpath.path)
                    temp_zip.write(self.full_path(fpath), os.path.relpath(fpath, path))
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
        self, path: str, request, url_endpoint: str, download_endpoint: str
    ):
        if self.exists(path):
            return {
                "url": re.sub(url_endpoint, download_endpoint, request.url._url),
                "headers": {"authorization": request.headers.get("authorization")},
                "method": "get",
            }
        return None


class S3Filesystem(FileSystem):
    """A filesystem that uses S3."""

    def __init__(
        self, root_path: str, s3_client, bucket, predef_dirs: list[str] | None = None
    ):
        self.s3_client = s3_client
        self.bucket = bucket
        super().__init__(root_path=root_path, predef_dirs=predef_dirs)

    def create_directory(self, path: str):
        self.s3_client.put_object(Bucket=self.bucket, Key=self.full_path(path))

    def _directory_contents(
        self, path: str, dirs: bool = True, recursive: bool = False
    ):
        # Get contents of S3 directory
        full_path = self.full_path(path)
        paginator = self.s3_client.get_paginator("list_objects_v2")
        operation_parameters = {"Bucket": self.bucket, "Prefix": full_path}
        operation_parameters["Delimiter"] = "/"
        page_iterator = paginator.paginate(**operation_parameters)

        for page in page_iterator:
            for key in page.get("Contents", []):
                if key["Key"] == full_path:
                    continue
                yield FileInfo(
                    path=key["Key"][len(str(self.root_path)) + 1 :],
                    type=FileTypes.file,
                    size=humanize.naturalsize(key["Size"]),
                )
            for key in page.get("CommonPrefixes", []):
                dir_path = key["Prefix"][len(str(self.root_path)) + 1 :]
                if dirs:
                    yield FileInfo(path=dir_path, type=FileTypes.directory, size="")
                if recursive:
                    for ret in self._directory_contents(
                        dir_path, dirs=dirs, recursive=recursive
                    ):
                        yield ret

    def get_file_info(self, path: str):
        metadata = self.s3_client.head_object(
            Bucket=self.bucket, Key=self.full_path(path)
        )
        return FileInfo(
            path=path,
            type=FileTypes.file,
            size=humanize.naturalsize(metadata["ContentLength"]),
        )

    def create_file(self, path, file):
        # Upload file to S3 efficiently
        self.s3_client.upload_fileobj(file, self.bucket, self.full_path(path))

    def create_file_url(
        self, path: str, request, url_endpoint: str, upload_endpoint: str
    ):
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
        return {"url": ret["url"], "data": ret["fields"], "method": "post"}

    def _rename_file(self, path, new_path):
        # Rename file on S3
        self.s3_client.copy_object(
            Bucket=self.bucket,
            Key=self.full_path(new_path),
            CopySource={"Bucket": self.bucket, "Key": self.full_path(path)},
        )
        self.s3_client.delete_object(Bucket=self.bucket, Key=self.full_path(path))

    def _delete_file(self, path):
        # Delete a file from S3
        self.s3_client.delete_object(Bucket=self.bucket, Key=self.full_path(path))

    def _delete_directory(self, path):
        # Delete entire folder from S3
        paginator = self.s3_client.get_paginator("list_objects_v2")
        operation_parameters = {"Bucket": self.bucket, "Prefix": self.full_path(path)}
        page_iterator = paginator.paginate(**operation_parameters)
        delete_keys = {"Objects": []}
        for page in page_iterator:
            for key in page.get("Contents"):
                delete_keys["Objects"].append({"Key": key["Key"]})
        self.s3_client.delete_objects(Bucket=self.bucket, Delete=delete_keys)

    def exists(self, path):
        # Check if there is any S3 object with the given path as prefix
        objects = self.s3_client.list_objects_v2(
            Bucket=self.bucket, Prefix=self.full_path(path), MaxKeys=1
        )
        return "Contents" in objects

    def isdir(self, path):
        if path == "/":
            return True
        return self.exists(path) and path.endswith("/")

    def full_path_uri(self, path):
        return "s3://" + self.bucket + "/" + self.full_path(path)

    def download(self, path):
        if not self.exists(path):
            return None
        _get_file_content = lambda path: self.s3_client.get_object(
            Bucket=self.bucket, Key=self.full_path(path)
        )["Body"]
        if self.isdir(path):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for fpath in self.list_directory(path, dirs=False, recursive=True):
                    fpath = str(fpath.path)
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
        self, path: str, request, url_endpoint: str, download_endpoint: str
    ):
        bucket = self.bucket
        path = self.full_path(path)

        response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=path)

        if not "Contents" in response:
            return None
        return {
            "url": self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": path},
                ExpiresIn=60 * 10,
            ),
            "method": "get",
        }


def get_filesystem_with_root(root_path: str):
    """Get the filesystem to use."""
    predef_dirs = [e.value for e in models.UploadFileTypes] + [
        e.value for e in models.OutputEndpoints
    ]
    if settings.filesystem == "s3":
        s3_client = boto3.client("s3")
        return S3Filesystem(
            root_path, s3_client, settings.s3_bucket, predef_dirs=predef_dirs
        )
    elif settings.filesystem == "local":
        return LocalFilesystem(root_path, predef_dirs=predef_dirs)
    else:
        raise ValueError("Invalid filesystem setting")


def get_user_filesystem(user_id: str):
    """Get the filesystem to use for a user."""
    return get_filesystem_with_root(str(Path(settings.user_data_root_path) / user_id))
