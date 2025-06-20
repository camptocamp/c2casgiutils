from pathlib import Path

import pytest
import requests
from c2cwsgiutils.acceptance import image


@pytest.mark.parametrize(
    ("expected_file_name", "width", "height", "headers", "media"),
    [
        pytest.param("c2c.expected.png", 650, 500, {}, [{"name": "prefers-color-scheme", "value": "dark"}]),
        pytest.param(
            "c2c-auth.expected.png",
            650,
            1000,
            {"X-API-Key": "changeme"},
            [{"name": "prefers-color-scheme", "value": "light"}],
        ),
        pytest.param(
            "c2c-auth-dark.expected.png",
            650,
            1000,
            {"X-API-Key": "changeme"},
            [
                {"name": "prefers-color-scheme", "value": "dark"},
            ],
        ),
    ],
)
def test_screenshot(expected_file_name, width, height, headers, media):
    image.check_screenshot(
        "http://localhost:8085/c2c",
        headers=headers,
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
        pytest.param("/api/broadcast", {"result": ["Broadcast echo"]}),
    ],
)
def test_endpoints(path, expected):
    """
    Test the API endpoints.
    """
    response = requests.get(f"http://localhost:8085{path}")
    assert response.ok
    assert response.json() == expected
