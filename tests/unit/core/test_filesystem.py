import os
import shutil
from abc import ABC, abstractmethod
from contextlib import nullcontext
from io import BytesIO
from typing import Any, Generator, cast

import pytest
from moto import mock_aws

from api.core.filesystem import FileSystem, LocalFilesystem, S3Filesystem
from api.schemas.file import FileInfo, FileTypes
from tests.conftest import S3TestingBucket


@pytest.fixture(scope="class")
def base_dir() -> str:
    return "fs_test_dir"


@pytest.fixture(scope="class")
def data_file1_name() -> str:
    return "data/test/data_file1.txt"


@pytest.fixture(scope="class")
def data_file2_name() -> str:
    return "data/test2/data_file2.txt"


@pytest.fixture(scope="class")
def data_file1_contents() -> str:
    return "data file1 contents"


class _TestFilesystem(ABC):
    @abstractmethod
    @pytest.fixture(scope="class")
    def filesystem(self, *args: Any, **kwargs: Any) -> Generator[FileSystem, Any, None]:
        raise NotImplementedError

    @pytest.fixture(autouse=True)
    def cleanup(self, filesystem: FileSystem) -> Generator[None, Any, None]:
        yield
        filesystem.delete("/")

    @abstractmethod
    @pytest.fixture
    def data_file1(
        self,
        filesystem: FileSystem,
        data_file1_name: str,
        data_file1_contents: str,
    ) -> None:
        raise NotImplementedError

    def test_list_directory_file(
        self,
        filesystem: FileSystem,
        monkeypatch: pytest.MonkeyPatch,
        data_file1_name: str,
    ) -> None:
        monkeypatch.setattr(filesystem, "isdir", lambda path: False)
        with pytest.raises(NotADirectoryError):
            filesystem.list_directory(data_file1_name)

    def test_rename_nonexistent_raises(
        self,
        filesystem: FileSystem,
        monkeypatch: pytest.MonkeyPatch,
        data_file1_name: str,
    ) -> None:
        monkeypatch.setattr(filesystem, "exists", lambda path: False)
        with pytest.raises(FileNotFoundError):
            filesystem.rename(data_file1_name, "new_name")

    def test_rename_directory_fails(
        self,
        filesystem: FileSystem,
        monkeypatch: pytest.MonkeyPatch,
        data_file1_name: str,
    ) -> None:
        monkeypatch.setattr(filesystem, "exists", lambda path: True)
        monkeypatch.setattr(filesystem, "isdir", lambda path: True)
        with pytest.raises(Exception):
            filesystem.rename(data_file1_name, "new_name")

    def test_delete_idempotent(
        self,
        filesystem: FileSystem,
        monkeypatch: pytest.MonkeyPatch,
        data_file1_name: str,
    ) -> None:
        monkeypatch.setattr(filesystem, "exists", lambda path: False)
        filesystem.delete(data_file1_name)

    def test_init(self, filesystem: FileSystem) -> None:
        filesystem.init()
        assert filesystem.exists("/")

    def test_list_directory_empty(self, filesystem: FileSystem) -> None:
        files = list(filesystem.list_directory("/", dirs=False, recursive=True))
        assert files == []

    def test_list_directory_root_empty_string(self, filesystem: FileSystem) -> None:
        files = list(filesystem.list_directory("", dirs=False, recursive=True))
        assert files == []

    def test_list_directory(
        self,
        filesystem: FileSystem,
        data_file1_name: str,
        data_file1_contents: str,
        data_file1: None,
    ) -> None:
        files = list(filesystem.list_directory("data/", recursive=True))
        assert len(files) == 2
        assert FileInfo(path="data/test/", type=FileTypes.directory, size="") in files
        assert (
            FileInfo(
                path=data_file1_name,
                type=FileTypes.file,
                size="{} Bytes".format(len(data_file1_contents)),
            )
            in files
        )

    def test_list_directory_subdir(
        self,
        filesystem: FileSystem,
        data_file1_name: str,
        data_file1_contents: str,
        data_file1: None,
    ) -> None:
        files = list(filesystem.list_directory("data/test/"))
        assert len(files) == 1
        assert files[0] == FileInfo(
            path=data_file1_name,
            type=FileTypes.file,
            size="{} Bytes".format(len(data_file1_contents)),
        )

    def test_get_file_info(
        self,
        filesystem: FileSystem,
        data_file1_name: str,
        data_file1_contents: str,
        data_file1: None,
    ) -> None:
        info = filesystem.get_file_info(data_file1_name)
        assert info == FileInfo(
            path=data_file1_name,
            type=FileTypes.file,
            size="{} Bytes".format(len(data_file1_contents)),
        )

    def test_create_file(
        self, filesystem: FileSystem, data_file1_name: str, data_file1_contents: str
    ) -> None:
        filesystem.create_file(
            data_file1_name, BytesIO(bytes(data_file1_contents, "utf-8"))
        )
        assert filesystem.exists(data_file1_name)
        assert filesystem.get_file_info(data_file1_name) == FileInfo(
            path=data_file1_name,
            type=FileTypes.file,
            size="{} Bytes".format(len(data_file1_contents)),
        )

    def test_rename(
        self,
        filesystem: FileSystem,
        data_file1_name: str,
        data_file1_contents: str,
        data_file1: None,
        data_file2_name: str,
    ) -> None:
        filesystem.rename(data_file1_name, data_file2_name)
        assert filesystem.exists(data_file2_name)
        assert filesystem.get_file_info(data_file2_name) == FileInfo(
            path=data_file2_name,
            type=FileTypes.file,
            size="{} Bytes".format(len(data_file1_contents)),
        )
        assert not filesystem.exists(data_file1_name)

    def test_exists_true_for_existing_file(
        self, filesystem: FileSystem, data_file1_name: str, data_file1: None
    ) -> None:
        assert filesystem.exists(data_file1_name)

    def test_exists_true_for_existing_directory(
        self, filesystem: FileSystem, data_file1: None
    ) -> None:
        assert filesystem.exists("data/")

    def test_exists_false_for_nonexistent_object(
        self, filesystem: FileSystem, data_file1_name: str
    ) -> None:
        assert not filesystem.exists(data_file1_name)

    def test_exists_root(self, filesystem: FileSystem) -> None:
        assert filesystem.exists("/")

    def test_isdir_true_for_existing_directory(
        self, filesystem: FileSystem, data_file1: None
    ) -> None:
        assert filesystem.isdir("data/")

    def test_isdir_false_for_existing_file(
        self, filesystem: FileSystem, data_file1_name: str, data_file1: None
    ) -> None:
        assert not filesystem.isdir(data_file1_name)

    def test_isdir_false_for_nonexistent_object(
        self, filesystem: FileSystem, data_file1_name: str
    ) -> None:
        assert not filesystem.isdir(data_file1_name)

    def test_isdir_root(self, filesystem: FileSystem) -> None:
        assert filesystem.isdir("/")

    def test_delete_file(
        self, filesystem: FileSystem, data_file1_name: str, data_file1: None
    ) -> None:
        filesystem.delete(data_file1_name)
        assert not filesystem.exists(data_file1_name)

    def test_delete_directory(
        self, filesystem: FileSystem, data_file1_name: str, data_file1: None
    ) -> None:
        filesystem.delete("data/test/")
        assert not filesystem.exists("data/test/")
        assert not filesystem.exists(data_file1_name)


class TestLocalFilesystem(_TestFilesystem):
    @pytest.fixture(scope="class")
    def filesystem(self, base_dir: str) -> Generator[LocalFilesystem, Any, None]:
        fs = LocalFilesystem(base_dir)
        yield fs
        shutil.rmtree(base_dir, ignore_errors=True)

    @pytest.fixture
    def data_file1(
        self,
        filesystem: FileSystem,
        data_file1_name: str,
        data_file1_contents: str,
    ) -> None:
        data_file1_name = os.path.join(filesystem.root_path, data_file1_name)
        os.makedirs(os.path.dirname(data_file1_name), exist_ok=True)
        with open(data_file1_name, "w") as f:
            f.write(data_file1_contents)


class TestS3Filesystem(_TestFilesystem):
    @pytest.fixture(
        scope="class", params=[True, pytest.param(False, marks=pytest.mark.aws)]
    )
    def mock_aws_(self, request: pytest.FixtureRequest) -> bool:
        return cast(bool, request.param)

    @pytest.fixture(scope="class")
    def filesystem(
        self, base_dir: str, mock_aws_: bool, bucket_suffix: str
    ) -> Generator[S3Filesystem, Any, None]:
        context_manager = mock_aws if mock_aws_ else nullcontext
        with context_manager():
            testing_bucket = S3TestingBucket(bucket_suffix)
            yield S3Filesystem(
                base_dir, testing_bucket.s3_client, testing_bucket.bucket_name
            )
            testing_bucket.cleanup()

    @pytest.fixture
    def data_file1(
        self,
        filesystem: FileSystem,
        data_file1_name: str,
        data_file1_contents: str,
    ) -> None:
        filesystem = cast(S3Filesystem, filesystem)
        data_file1_name = os.path.join(filesystem.root_path, data_file1_name)
        filesystem.s3_client.put_object(
            Bucket=filesystem.bucket,
            Key=data_file1_name,
            Body=BytesIO(data_file1_contents.encode("utf-8")),
        )
