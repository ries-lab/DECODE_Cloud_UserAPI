from fastapi.testclient import TestClient
from tests.conftest import internal_api_key_secret, jobs
from api.main import app
from api.models import Job
import api.database


client = TestClient(app)
endpoint = "/_job_status"


def test_job_status_init(jobs):
    database = api.database.SessionLocal()
    assert database.query(Job).first().status == "queued"


def test_job_status_update_requires_internal_api_key(jobs):
    response = client.put(
        endpoint,
        json={"job_id": jobs[0].id, "status": "running"},
    )
    assert response.status_code == 422


def test_job_status_update(jobs):
    response = client.put(
        endpoint,
        json={"job_id": jobs[0].id, "status": "running"},
        headers={"x-api-key": internal_api_key_secret},
    )
    assert response.status_code == 204
    database = api.database.SessionLocal()
    assert database.query(Job).filter(Job.id == jobs[0].id).first().status == "running"
