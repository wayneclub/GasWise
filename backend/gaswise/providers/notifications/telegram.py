"""Fixed-host Bot API sender; never logs credential-bearing request URLs."""
import asyncio
import http.client
import json
import ssl


class TelegramDeliveryError(Exception):
    def __init__(self, code, retry_seconds=30):
        self.code, self.retry_seconds = code, retry_seconds
        super().__init__(code)


class TelegramSender:
    def __init__(self, token, chat_id, thread_id=None, *, connection_factory=None):
        self.token, self.chat_id, self.thread_id = token, chat_id, thread_id
        self.connection_factory = connection_factory or (
            lambda: http.client.HTTPSConnection('api.telegram.org', context=ssl.create_default_context(), timeout=10))

    def _send(self, text):
        connection = None
        payload = {'chat_id': self.chat_id.get_secret_value(), 'text': text[:3800], 'disable_web_page_preview': True}
        if self.thread_id is not None:
            payload['message_thread_id'] = self.thread_id
        try:
            connection = self.connection_factory()
            connection.request('POST', '/bot' + self.token.get_secret_value() + '/sendMessage',
                               json.dumps(payload).encode(), {'Content-Type': 'application/json'})
            response = connection.getresponse()
            data = json.loads(response.read(65536))
            if response.status == 200 and data.get('ok'):
                message_id = data.get('result', {}).get('message_id')
                if type(message_id) is int:
                    return message_id
            status = data.get('error_code', response.status)
            status = status if type(status) is int and 100 <= status <= 599 else 500
            retry = data.get('parameters', {}).get('retry_after', 30)
            retry = min(86400, max(3, retry)) if type(retry) is int else 30
            raise TelegramDeliveryError(f'telegram_api_{status}', retry)
        except TelegramDeliveryError:
            raise
        except (OSError, ValueError, TypeError, AttributeError, http.client.HTTPException):
            raise TelegramDeliveryError('telegram_transport_or_response_error') from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except OSError:
                    pass

    async def send(self, text):
        return await asyncio.to_thread(self._send, text)
