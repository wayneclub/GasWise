from fastapi import APIRouter, Depends, HTTPException

from gaswise.api.dependencies import authorize, get_services
from gaswise.app.runtime import Services
from gaswise.contracts.alerts import (
    AlertConfig,
    AlertStatus,
    AlertTestRequest,
    InboxResult,
    InstallationAuth,
    InstallationCreate,
    InstallationCreated,
    NeedStateUpdate,
    WatchResult,
    WatchUpdate,
)
from gaswise.services.pricing.alerts import AlertAuthorizationError, AlertWatchLimitError

router = APIRouter()


def available(services: Services):
    if services.alerts is None:
        raise HTTPException(503, "smart_alerts_unavailable")
    return services.alerts


@router.post("/v1/alerts/config", response_model=AlertConfig, dependencies=[Depends(authorize)])
async def alert_config(services: Services = Depends(get_services)):
    alerts = services.alerts
    return {"enabled": alerts is not None, "vapid_public_key": alerts.public_key if alerts else None}


@router.post("/v1/alerts/installations", response_model=InstallationCreated, dependencies=[Depends(authorize)])
async def create_installation(body: InstallationCreate, services: Services = Depends(get_services)):
    alerts = available(services)
    return await alerts.create(body.subscription.model_dump(mode="json"), body.timezone, body.locale)


async def authorized(operation):
    try:
        await operation
    except AlertAuthorizationError:
        raise HTTPException(404, "alert_installation_not_found") from None


@router.post("/v1/alerts/need-state", response_model=AlertStatus, dependencies=[Depends(authorize)])
async def update_need(body: NeedStateUpdate, services: Services = Depends(get_services)):
    await authorized(available(services).update_need(body.installation_id, body.installation_token,
                                                      body.state, body.confidence, body.ttl_hours))
    return {"status": "updated"}


@router.post("/v1/alerts/test", response_model=AlertStatus, dependencies=[Depends(authorize)])
async def test_alert(body: AlertTestRequest, services: Services = Depends(get_services)):
    await authorized(available(services).queue_test(body.installation_id, body.installation_token, body.locale))
    return {"status": "queued"}


@router.post("/v1/alerts/disable", response_model=AlertStatus, dependencies=[Depends(authorize)])
async def disable_alerts(body: InstallationAuth, services: Services = Depends(get_services)):
    await authorized(available(services).disable(body.installation_id, body.installation_token))
    return {"status": "disabled"}


@router.post("/v1/alerts/watches", response_model=WatchResult, dependencies=[Depends(authorize)])
async def update_watch(body: WatchUpdate, services: Services = Depends(get_services)):
    alerts = available(services)
    try:
        await authorized(alerts.update_watch(body.model_dump()))
    except AlertWatchLimitError:
        raise HTTPException(409, "alert_watch_limit") from None
    return {"status": "watched" if body.enabled else "removed"}


@router.post("/v1/alerts/inbox", response_model=InboxResult, dependencies=[Depends(authorize)])
async def alert_inbox(body: InstallationAuth, services: Services = Depends(get_services)):
    try:
        return {"items": await available(services).inbox(body.installation_id, body.installation_token)}
    except AlertAuthorizationError:
        raise HTTPException(404, "alert_installation_not_found") from None
