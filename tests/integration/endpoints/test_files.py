import os
from io import BytesIO

import requests
from fastapi.testclient import TestClient

ENDPOINT = "/files"


def test_auth_required(client: TestClient, require_auth: None) -> None:
    response = client.get(ENDPOINT)
    assert response.status_code == 401


def test_get_files_happy(client: TestClient) -> None:
    response = client.get(f"{ENDPOINT}//")
    assert response.status_code == 200
    assert len(response.json()) == 5, response.text
    assert {"path": "data/", "type": "directory", "size": ""} in response.json()
    assert {"path": "config/", "type": "directory", "size": ""} in response.json()
    assert {"path": "artifact/", "type": "directory", "size": ""} in response.json()
    assert {"path": "log/", "type": "directory", "size": ""} in response.json()
    assert {"path": "output/", "type": "directory", "size": ""} in response.json()


def test_get_files_recursive_happy(
    client: TestClient, data_files: dict[str, str], config_files: dict[str, str]
) -> None:
    response = client.get(f"{ENDPOINT}//", params={"recursive": True})
    assert response.status_code == 200
    assert len(response.json()) == 11
    for files in [data_files, config_files]:
        for file_name, file_contents in files.items():
            assert {
                "path": file_name,
                "type": "file",
                "size": f"{len(file_contents)} Bytes",
            } in response.json()
    assert {"path": "data/", "type": "directory", "size": ""} in response.json()
    assert {"path": "config/", "type": "directory", "size": ""} in response.json()
    assert {"path": "data/test/", "type": "directory", "size": ""} in response.json()
    assert {"path": "config/test/", "type": "directory", "size": ""} in response.json()


def test_get_files_nodir_happy(client: TestClient, data_files: dict[str, str]) -> None:
    response = client.get(
        f"{ENDPOINT}//", params={"show_dirs": False, "recursive": True}
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
    data_file1_name, data_file1_contents = list(data_files.items())[0]
    assert {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } in response.json()


def test_get_files_subdir_happy(
    client: TestClient, config_files: dict[str, str]
) -> None:
    response = client.get(f"{ENDPOINT}/config/", params={"recursive": True})
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert {"path": "config/test/", "type": "directory", "size": ""} in response.json()
    config_file1_name, config_file1_contents = list(config_files.items())[0]
    assert {
        "path": config_file1_name,
        "type": "file",
        "size": f"{len(config_file1_contents)} Bytes",
    } in response.json()


def test_get_files_fail_not_a_directory(client: TestClient) -> None:
    response = client.get(f"{ENDPOINT}/does_not_exist")
    assert response.status_code == 404


def test_post_files_happy(client: TestClient) -> None:
    data_file1_name = "data/test/data_file1.txt"
    data_file1_contents = "data file1 contents"
    files = {
        "file": (
            os.path.split(data_file1_name)[-1],
            BytesIO(bytes(data_file1_contents, "utf-8")),
            "text/plain",
        )
    }
    response = client.post(
        f"{ENDPOINT}/{os.path.dirname(data_file1_name)}//upload", files=files
    )
    assert response.status_code == 201
    assert response.json() == {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    }
    response = client.get(
        f"{ENDPOINT}//", params={"recursive": True, "show_dirs": False}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } in response.json()


def test_post_files_fail_not_config_or_data(client: TestClient) -> None:
    files = {
        "file": (
            "file.txt",
            BytesIO(bytes("file contents", "utf-8")),
            "text/plain",
        )
    }
    response = client.post(f"{ENDPOINT}/does_not_exist", files=files)
    assert response.status_code == 405


def test_put_files_happy(client: TestClient, data_files: dict[str, str]) -> None:
    data_file1_name, data_file1_contents = list(data_files.items())[0]
    data_file2_name, data_file2_contents = list(data_files.items())[1]
    response = client.put(
        f"{ENDPOINT}/{data_file1_name}", json={"path": data_file2_name}
    )
    assert response.status_code == 200
    assert response.json() == {
        "path": data_file2_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    }
    response = client.get(f"{ENDPOINT}//", params={"recursive": True})
    assert response.status_code == 200
    assert {
        "path": data_file2_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } in response.json()
    assert {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } not in response.json()


def test_put_files_fail_is_a_directory(client: TestClient) -> None:
    response = client.put(f"{ENDPOINT}/data/", json={"path": "/data/new"})
    assert response.status_code == 405


def test_delete_files_happy(client: TestClient, data_files: dict[str, str]) -> None:
    data_file1_name = list(data_files.keys())[0]
    response = client.delete(f"{ENDPOINT}/{data_file1_name}")
    assert response.status_code == 204
    response = client.get(f"{ENDPOINT}/?show_dirs=false")
    assert response.status_code == 200
    assert response.json() == []


def test_download_file_happy(client: TestClient, data_files: dict[str, str]) -> None:
    data_file1_name, data_file1_contents = list(data_files.items())[0]
    response = client.get(f"{ENDPOINT}/{data_file1_name}/download")
    assert response.status_code == 200
    assert response.content.decode("utf-8") == data_file1_contents


def test_get_url_file_happy(
    env: str, client: TestClient, data_files: dict[str, str]
) -> None:
    data_file1_name, data_file1_contents = list(data_files.items())[0]
    response = client.get(f"{ENDPOINT}/{data_file1_name}/url")
    assert response.status_code == 200
    request_params = response.json()
    if "authorization" in request_params["headers"]:
        del request_params["headers"]["authorization"]
    request_client = client if env == "local" else requests
    response = request_client.request(**request_params)
    assert response.status_code == 200, response.text
    assert response.content.decode("utf-8") == data_file1_contents


def test_post_url_file_happy(env: str, client: TestClient) -> None:
    data_file1_name = "data/test/data_file1.txt"
    data_file1_contents = "data file1 contents"
    response = client.post(f"{ENDPOINT}/{os.path.dirname(data_file1_name)}//url")
    assert response.status_code == 201
    request_params = response.json()
    if "authorization" in request_params["headers"]:
        del request_params["headers"]["authorization"]
    files = {
        "file": (
            os.path.split(data_file1_name)[-1],
            BytesIO(bytes(data_file1_contents, "utf-8")),
            "text/plain",
        )
    }
    request_client = client if env == "local" else requests
    request_client.request(**request_params, files=files)
    response = client.get(
        f"{ENDPOINT}//", params={"recursive": True, "show_dirs": False}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert {
        "path": data_file1_name,
        "type": "file",
        "size": f"{len(data_file1_contents)} Bytes",
    } in response.json()
