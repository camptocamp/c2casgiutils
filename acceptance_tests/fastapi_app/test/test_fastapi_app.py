from pathlib import Path

import pytest
import requests
from c2cwsgiutils.acceptance import image


@pytest.mark.parametrize(
    ("port", "expected_file_name", "width", "height", "media"),
    [
        pytest.param(
            "8085",
            "c2c.expected.png",
            650,
            500,
            [{"name": "prefers-color-scheme", "value": "dark"}],
        ),
        pytest.param(
            "8086",
            "c2c-auth.expected.png",
            650,
            1000,
            [{"name": "prefers-color-scheme", "value": "light"}],
        ),
        pytest.param(
            "8086",
            "c2c-auth-dark.expected.png",
            650,
            1000,
            [
                {"name": "prefers-color-scheme", "value": "dark"},
            ],
        ),
    ],
)
def test_screenshot(port: str, expected_file_name, width, height, media):
    image.check_screenshot(
        f"http://localhost:{port}/c2c",
        media=media,
        width=width,
        height=height,
        result_folder="results",
        expected_filename=str(Path(__file__).parent / expected_file_name),
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param("/api/hello", {"message": "hello"}),
    ],
)
def test_endpoints(path, expected):
    """
    Test the API endpoints.
    """
    response = requests.get(f"http://localhost:8085{path}")
    assert response.ok
    assert response.json() == expected


def test_broadcast():
    """
    Test the API endpoints.
    """
    response = requests.get("http://localhost:8085/api/broadcast")
    assert response.ok
    response_json = response.json()
    assert "result" in response_json
    assert isinstance(response_json["result"], list)
    assert len(response_json["result"]) == 2
    for response_data in response_json["result"]:
        assert isinstance(response_data, dict)
        assert set(response_data.keys()) == {"message", "hostname", "pid"}
        assert response_data["message"] == "Broadcast echo"
