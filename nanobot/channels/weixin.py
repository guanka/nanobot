"""WeChat iLink Bot API channel."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import Field
from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.paths import get_config_dir
from nanobot.config.schema import Base

from .weixin.auth import AuthManager, AuthResult
from .weixin.api import IlinkApiClient
from .weixin.monitor import MessageMonitor
from .weixin.messaging import outbound_to_weixin


class WeixinConfig(Base):
    """WeChat channel configuration."""

    enabled: bool = False
    allow_from: list[str] = Field(default_factory=list)
    base_url: str = "https://ilinkai.weixin.qq.com"
    cdn_base_url: str = "https://novac2c.cdn.weixin.qq.com/c2c"
    bot_type: str = "3"
    login_timeout: int = 480


class WeixinChannel(BaseChannel):
    """WeChat channel using iLink Bot API."""

    name = "weixin"
    display_name = "WeChat (iLink Bot API)"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return WeixinConfig().model_dump(by_alias=True)

    def __init__(self, config: Any, bus: MessageBus):
        if isinstance(config, dict):
            config = WeixinConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: WeixinConfig = config

        # Components
        self.api_client: IlinkApiClient | None = None
        self.auth_manager: AuthManager | None = None
        self.monitor: MessageMonitor | None = None
        self._monitor_task: asyncio.Task | None = None

        # Token data
        self._token_data: dict[str, Any] | None = None

    @property
    def config_path(self) -> Path:
        """Get configuration directory path."""
        return get_config_dir()

    async def start(self) -> None:
        """Start channel: login + start monitor."""
        if not self.config.enabled:
            logger.info("Weixin channel disabled")
            return

        logger.info("Starting Weixin channel")

        # Initialize API client
        self.api_client = IlinkApiClient(self.config.base_url)
        await self.api_client.__aenter__()

        # Login
        self.auth_manager = AuthManager(
            self.config.base_url, str(self.config_path), self.api_client
        )
        auth_result = await self.auth_manager.login()

        if not auth_result.success:
            raise Exception(f"Login failed: {auth_result.error}")

        # Update API client with token
        self._token_data = auth_result.data
        self.api_client.token = self._token_data["bot_token"]

        account_id = self._token_data.get("account_id", "unknown")
        logger.info(f"Logged in as {account_id}")

        # Start monitor
        self.monitor = MessageMonitor(
            self.api_client,
            account_id,
            self._handle_inbound,
        )
        self._monitor_task = asyncio.create_task(self.monitor.run())

        logger.info("Weixin channel started")

    async def stop(self) -> None:
        """Stop channel: cancel monitor."""
        logger.info("Stopping Weixin channel")

        if self.monitor:
            self.monitor.stop()

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self.api_client:
            await self.api_client.__aexit__(None, None, None)

        logger.info("Weixin channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send outbound message."""
        if not self.api_client:
            raise Exception("API client not initialized")

        # Get context_token
        if not self.monitor:
            raise Exception("Monitor not initialized")

        context_token = self.monitor.get_context_token(msg.chat_id)
        if not context_token:
            raise Exception(
                f"Cannot send to {msg.chat_id}: context_token missing. "
                "User must send a message first."
            )

        # Convert to iLink format
        weixin_msg = outbound_to_weixin(msg, context_token)

        # Send
        await self.api_client._post("ilink/bot/sendmessage", weixin_msg)

    async def _handle_inbound(self, inbound_msg):
        """Handle inbound message."""
        # Publish to bus
        await self.bus.publish_inbound(inbound_msg)
