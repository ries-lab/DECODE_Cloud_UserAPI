from typing import Generator

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # run everything in lifespan context
    with TestClient(app) as client:
        yield client
