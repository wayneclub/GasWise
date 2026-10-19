"""Failure alerts and hourly batch digests; durable work stays in PostgreSQL."""
import asyncio
import json
import logging
import uuid
from datetime import datetime

from gaswise.domain.pricing.collection_reporting import failure_message, summary_message
from gaswise.providers.notifications.telegram import TelegramDeliveryError

logger = logging.getLogger(__name__)


class CollectionNotifications:
    def __init__(self, store, sender):
        self.store, self.sender = store, sender

    async def step(self):
        await self.store.queue_collection_summaries()
        owner = uuid.uuid4().hex
        notice = await self.store.claim_collection_notice(owner)
        if notice is None:
            return False
        try:
            payload = json.loads(notice['payload']) if isinstance(notice['payload'], str) else notice['payload']
            if notice['kind'] == 'failure':
                run = await self.store.collection_run(payload['run_id'])
                if run is None:
                    raise TelegramDeliveryError('collection_run_missing', 86400)
                text = failure_message(run)
            elif notice['kind'] == 'summary':
                report = await self.store.collection_report(datetime.fromisoformat(payload['start']), datetime.fromisoformat(payload['end']))
                text = summary_message(report)
            else:
                raise TelegramDeliveryError('notification_kind_invalid', 86400)
            message_id = await self.sender.send(text)
        except TelegramDeliveryError as error:
            delay = max(error.retry_seconds, min(3600, 30 * 2 ** min(notice['attempts'] - 1, 7)))
            await self.store.finish_collection_notice(notice['id'], owner, error=error.code, retry_seconds=delay)
            logger.warning('Collection Telegram delivery deferred: %s', error.code)
            return False
        await self.store.finish_collection_notice(notice['id'], owner, message_id=message_id)
        return True

    async def run(self):
        while True:
            try:
                await self.step()
            except Exception:
                # No exception strings: sender URLs and database credentials stay private.
                logger.warning('Collection notification processing deferred')
            await asyncio.sleep(15)
