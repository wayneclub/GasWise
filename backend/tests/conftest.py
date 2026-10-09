"""Local live credentials/configuration must not change automated test behavior."""

import pytest


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    for key, value in {
        "GASWISE_MODE": "demo",
        "GASWISE_GASBUDDY_WEB_ENABLED": "false",
        "GASWISE_API_TOKEN": "",
        "GASWISE_GOOGLE_API_KEY": "",
    }.items():
        monkeypatch.setenv(key, value)
