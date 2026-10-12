"""Request-scoped dependencies, overrideable using FastAPI's dependency_overrides."""

import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from gaswise.api.operations import OperationRunner
from gaswise.app.runtime import Services
from gaswise.app.settings import Settings

bearer = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_operations(request: Request) -> OperationRunner:
    return request.app.state.operations


async def authorize(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
):
    supplied = credentials.credentials if credentials else ""
    token = settings.api_token.get_secret_value()
    if token and not secrets.compare_digest(supplied, token):
        raise HTTPException(401, "invalid_api_token")
