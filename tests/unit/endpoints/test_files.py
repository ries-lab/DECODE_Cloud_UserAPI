import os
import pytest
from io import BytesIO
from tests.conftest import (
    data_file1_name,
    data_file1_contents,
    data_file2_name,
    data_file2_contents,
    config_file1_name,
    config_file1_contents,
    config_file2_name,
    config_file2_contents,
    data_files,
    config_files,
    cleanup_files,
    data_file1,
)
from fastapi.testclient import TestClient
from api.main import app
from api.schemas.file import FileHTTPRequest


client = TestClient(app)
endpoint = "/files"


def test_auth_required(require_auth):
    original_overrides = app.dependency_overrides
    app.dependency_overrides = {}
    response = client.get(endpoint)
    assert response.status_code == 401
    app.dependency_overrides = original_overrides


def test_get_files_happy(data_files, config_files):
    response = client.get(f"{endpoint}//")
    assert response.status_code == 200
    assert len(response.json()) == 2, response.text
    assert {"path": "data/", "type": "directory", "size": ""} in response.json()
    assert {"path": "config/", "type": "directory", "size": ""} in response.json()


def test_get_files_empty_happy():
    response = client.get(f"{endpoint}//")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_get_files_recursive_happy(data_files, config_files):
    response = client.get(f"{endpoint}//", params={"recursive": True})
    assert response.status_code == 200
    assert len(response.json()) == 8
    assert {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } in response.json()
    assert {
        "path": data_file2_name,
        "type": "file",
        "size": f"{len(data_file2_contents)} Bytes",
    } in response.json()
    assert {
        "path": config_file1_name,
        "type": "file",
        "size": f"{len(config_file1_contents)} Bytes",
    } in response.json()
    assert {
        "path": config_file2_name,
        "type": "file",
        "size": f"{len(config_file2_contents)} Bytes",
    } in response.json()
    assert {"path": "data/", "type": "directory", "size": ""} in response.json()
    assert {"path": "config/", "type": "directory", "size": ""} in response.json()
    assert {"path": "data/test/", "type": "directory", "size": ""} in response.json()
    assert {"path": "config/test/", "type": "directory", "size": ""} in response.json()


def test_get_files_nodir_happy(data_files):
    response = client.get(
        f"{endpoint}//", params={"show_dirs": False, "recursive": True}
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } in response.json()
    assert {
        "path": data_file2_name,
        "type": "file",
        "size": f"{len(data_file2_contents)} Bytes",
    } in response.json()


def test_get_files_subdir_happy(config_files):
    response = client.get(f"{endpoint}/config/", params={"recursive": True})
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert {"path": "config/test/", "type": "directory", "size": ""} in response.json()
    assert {
        "path": config_file1_name,
        "type": "file",
        "size": f"{len(config_file1_contents)} Bytes",
    } in response.json()
    assert {
        "path": config_file2_name,
        "type": "file",
        "size": f"{len(config_file2_contents)} Bytes",
    } in response.json()


def test_get_files_fail_not_a_directory():
    response = client.get(f"{endpoint}/does_not_exist")
    assert response.status_code == 404


def test_post_files_happy(cleanup_files):
    files = {
        "file": (
            os.path.split(data_file1_name)[-1],
            BytesIO(bytes(data_file1_contents, "utf-8")),
            "text/plain",
        )
    }
    response = client.post(
        f"{endpoint}/{os.path.dirname(data_file1_name)}//upload", files=files
    )
    assert response.status_code == 201
    assert response.json() == {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    }
    cleanup_files.append(data_file1_name)
    response = client.get(
        f"{endpoint}//", params={"recursive": True, "show_dirs": False}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } in response.json()


def test_post_files_fail_not_config_or_data():
    files = {
        "file": (
            data_file1_name,
            BytesIO(bytes(data_file1_contents, "utf-8")),
            "text/plain",
        )
    }
    response = client.post(f"{endpoint}/does_not_exist", files=files)
    assert response.status_code == 405


def rename_test_implementation(response, cleanup_files):
    assert response.status_code == 200
    assert response.json() == {
        "path": data_file2_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    }
    cleanup_files.append(data_file2_name)
    response = client.get(f"{endpoint}//", params={"recursive": True})
    assert response.status_code == 200
    assert {
        "path": data_file2_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } in response.json()


def test_put_files_happy(data_file1, cleanup_files):
    response = client.put(
        f"{endpoint}/{data_file1_name}", json={"path": data_file2_name}
    )
    rename_test_implementation(response, cleanup_files)


def test_put_files_fail_is_a_directory(data_files):
    response = client.put(f"{endpoint}/data/", json={"path": data_file2_name})
    assert response.status_code == 400


def test_delete_files_happy(data_file1):
    response = client.delete(f"{endpoint}/{data_file1_name}")
    assert response.status_code == 204
    response = client.get(f"{endpoint}//")
    assert response.status_code == 200
    assert response.json() == []


def test_download_file_happy(data_file1):
    response = client.get(f"{endpoint}/{data_file1_name}/download")
    assert response.status_code == 200
    assert response.content.decode("utf-8") == data_file1_contents


def test_get_url_file_happy(data_file1):
    response = client.get(f"{endpoint}/{data_file1_name}/url")
    assert response.status_code == 200
    FileHTTPRequest(**response.json())  # check parsable


def test_post_url_file_happy(data_file1):
    response = client.post(f"{endpoint}/{os.path.dirname(data_file1_name)}//url")
    assert response.status_code == 201
    FileHTTPRequest(**response.json())
