from tests.conftest import (
    data_file1_name,
    data_file2_name,
    data_file1_contents,
    data_file2_contents,
    data_files,
    data_file1,
    user_filesystem as filesystem,
)
import pytest
from io import BytesIO
from api.core.filesystem import FileTypes, FileInfo, FileSystem


user_dir = "test_user_dir"


class TestFilesystemBase:
    def test_list_directory_file(self, filesystem, monkeypatch):
        monkeypatch.setattr(filesystem, "isdir", lambda path: False)
        with pytest.raises(NotADirectoryError):
            filesystem.list_directory(data_file1_name)

    def test_rename_nonexistent_raises(self, filesystem, monkeypatch):
        monkeypatch.setattr(filesystem, "exists", lambda path: False)
        with pytest.raises(FileNotFoundError):
            filesystem.rename(data_file1_name, "new_name")

    def test_rename_directory_fails(self, filesystem, monkeypatch):
        monkeypatch.setattr(filesystem, "exists", lambda path: True)
        monkeypatch.setattr(filesystem, "isdir", lambda path: True)
        with pytest.raises(IsADirectoryError):
            filesystem.rename(data_file1_name, "new_name")

    def test_delete_idempotent(self, filesystem, monkeypatch):
        monkeypatch.setattr(filesystem, "exists", lambda path: False)
        filesystem.delete(data_file1_name)


class TestFilesystem:
    def test_init(self, filesystem):
        filesystem.init()
        assert filesystem.exists("/")

    def test_list_directory_empty(self, filesystem):
        files = list(filesystem.list_directory("/"))
        assert files == []

    def test_list_directory_root_empty_string(self, filesystem):
        files = list(filesystem.list_directory(""))
        assert files == []

    def test_list_directory(self, filesystem, data_files):
        files = list(filesystem.list_directory("data/", recursive=True))
        assert len(files) == 3
        assert FileInfo("data/test/", FileTypes.directory, "") in files
        assert (
            FileInfo(
                data_file2_name,
                FileTypes.file,
                "{} Bytes".format(len(data_file2_contents)),
            )
            in files
        )
        assert (
            FileInfo(
                data_file1_name,
                FileTypes.file,
                "{} Bytes".format(len(data_file1_contents)),
            )
            in files
        )

    def test_list_directory_subdir(self, filesystem, data_file1):
        files = list(filesystem.list_directory("data/test/"))
        assert len(files) == 1
        assert files[0] == FileInfo(
            data_file1_name, FileTypes.file, "{} Bytes".format(len(data_file1_contents))
        )

    def test_get_file_info(self, filesystem, data_files):
        info = filesystem.get_file_info(data_file1_name)
        assert info == FileInfo(
            data_file1_name, FileTypes.file, "{} Bytes".format(len(data_file1_contents))
        )

    def test_create_file(self, filesystem, cleanup_files):
        filesystem.create_file(
            data_file1_name, BytesIO(bytes(data_file1_contents, "utf-8"))
        )
        cleanup_files.append(data_file1_name)
        assert filesystem.exists(data_file1_name)

    def test_create_file_subdir(self, filesystem, cleanup_files):
        filesystem.create_file(
            data_file1_name, BytesIO(bytes(data_file1_contents, "utf-8"))
        )
        cleanup_files.append(data_file1_name)
        assert filesystem.exists(data_file1_name)

    def test_rename(self, filesystem, data_file1, cleanup_files):
        filesystem.rename(data_file1_name, data_file2_name)
        cleanup_files.append(data_file2_name)
        assert filesystem.exists(data_file2_name)
        assert not filesystem.exists(data_file1_name)

    def test_exists_true_for_existing_file(self, filesystem, data_file1):
        assert filesystem.exists(data_file1_name)

    def test_exists_true_for_existing_directory(self, filesystem, data_files):
        assert filesystem.exists("data/")

    def test_exists_false_for_nonexistent_object(self, filesystem):
        assert not filesystem.exists(data_file1_name)

    def test_exists_root(self, filesystem):
        assert filesystem.exists("/")

    def test_isdir_true_for_existing_directory(self, filesystem, data_files):
        assert filesystem.isdir("data/")

    def test_isdir_false_for_existing_file(self, filesystem, data_file1):
        assert not filesystem.isdir(data_file1_name)

    def test_isdir_false_for_nonexistent_object(self, filesystem):
        assert not filesystem.isdir(data_file1_name)

    def test_isdir_root(self, filesystem):
        assert filesystem.isdir("/")

    def test_delete_file(self, filesystem, data_file1):
        filesystem.delete(data_file1_name)
        assert not filesystem.exists(data_file1_name)

    def test_delete_directory(self, filesystem, data_files):
        filesystem.delete("data/")
        assert not filesystem.exists("data/")

    def test_empty_directories_are_deleted(self, filesystem, data_file1):
        filesystem.delete(data_file1_name)
        assert not filesystem.exists("data/test/")
