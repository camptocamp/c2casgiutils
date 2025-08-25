import pytest
import requests


@pytest.mark.parametrize(
    ("params"),
    [
        {"tags": "redis"},
        {"name": "Redis"},
    ],
)
def test_health_checks(params: dict[str, str]) -> None:
    """
    Test the API endpoints.
    """
    response = requests.get("http://localhost:8085/c2c/health", params=params)
    assert response.status_code == 200
    response_json = response.json()
    assert {"status_code", "time_taken", "entities"} == set(response_json.keys())
    assert response_json["status_code"] == 200
    assert len(response_json["entities"]) == 1
    assert response_json["entities"][0].keys() == {"name", "tags", "status_code", "payload", "time_taken"}
    assert response_json["entities"][0]["name"] == "Redis"
    assert response_json["entities"][0]["status_code"] == 200
    assert response_json["entities"][0]["payload"] == {}


@pytest.mark.parametrize(
    ("params"),
    [
        {"tags": "wrong"},
        {"name": "Wrong"},
    ],
)
def test_health_checks_wrong(params: dict[str, str]) -> None:
    """
    Test the API endpoints.
    """
    response = requests.get("http://localhost:8085/c2c/health", params=params)
    assert response.status_code == 500
    response_json = response.json()
    assert response_json["status_code"] == 500
    assert len(response_json["entities"]) == 1
    assert response_json["entities"][0]["name"] == "Wrong"
    assert response_json["entities"][0]["status_code"] == 500
    assert response_json["entities"][0]["payload"] == {
        "error": "This is an always-failing check for testing purposes",
    }


@pytest.mark.parametrize(
    ("params"),
    [
        {"tags": "all"},
        {},
    ],
)
def test_health_checks_all(params: dict[str, str]) -> None:
    response = requests.get("http://localhost:8085/c2c/health", params=params)
    assert response.status_code == 500
    response_json = response.json()
    assert response_json["status_code"] == 500
    assert len(response_json["entities"]) == 2


@pytest.mark.parametrize(
    ("params"),
    [
        {"tags": "none"},
        {"name": "None"},
    ],
)
def test_health_checks_none(params: dict[str, str]) -> None:
    response = requests.get("http://localhost:8085/c2c/health", params=params)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["status_code"] == 200
    assert len(response_json["entities"]) == 0
