"""Long-poll message monitor for WeChat."""

import asyncio
from typing import Any

from .api import IlinkApiClient, UpdatesResult
from .messaging import weixin_to_inbound
from nanobot.bus.events import InboundMessage

from loguru import logger


class MonitorError(Exception):
    """Monitor error."""
    pass


class MessageMonitor:
    """Long-poll loop for receiving WeChat messages."""

    def __init__(
        self,
        api_client: IlinkApiClient,
        account_id: str,
        on_message,
    ):
        self.api_client = api_client
        self.account_id = account_id
        self.on_message = on_message
        self._stopped = False
        self._context_token_store: dict[str, str] = {}

    def _store_context_token(self, user_id: str, token: str):
        """Store context_token for reply."""
        key = f"{self.account_id}:{user_id}"
        self._context_token_store[key] = token
        logger.debug(f"Stored context_token for {user_id}")

    def get_context_token(self, user_id: str) -> str | None:
        """Retrieve context_token for user."""
        key = f"{self.account_id}:{user_id}"
        return self._context_token_store.get(key)

    def stop(self):
        """Stop the monitor."""
        self._stopped = True
        logger.info(f"Monitor stopped for {self.account_id}")

    async def run(self):
        """Run long-poll loop."""
        logger.info(f"Starting monitor for {self.account_id}")
        get_updates_buf = ""

        while not self._stopped:
            try:
                result = await self.api_client.get_updates(
                    get_updates_buf=get_updates_buf,
                    timeout=35,
                )

                if result.get_updates_buf:
                    get_updates_buf = result.get_updates_buf

                for msg in result.msgs:
                    if msg.get("message_type") != 1:
                        continue

                    from_user = msg.get("from_user_id", "")
                    context_token = msg.get("context_token", "")

                    self._store_context_token(from_user, context_token)

                    inbound = weixin_to_inbound(msg, self.account_id)
                    await self.on_message(inbound)

            except asyncio.CancelledError:
                logger.info("Monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}", exc_info=True)
                await asyncio.sleep(5)

        logger.info(f"Monitor exited for {self.account_id}")
