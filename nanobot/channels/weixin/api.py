"""iLink Bot API HTTP client."""

import asyncio
import base64
import random
from dataclasses import dataclass
from typing import Any

import httpx

from loguru import logger


class NetworkError(Exception):
    """Network/API error."""
    pass


@dataclass
class QRCodeResult:
    """Result from get_bot_qrcode."""
    qrcode: str
    qrcode_url: str


@dataclass
class QRStatusResult:
    """Result from get_qrcode_status."""
    status: str  # "wait", "scaned", "confirmed", "expired"
    bot_token: str | None = None
    ilink_bot_id: str | None = None
    ilink_user_id: str | None = None
    baseurl: str | None = None


@dataclass
class UpdatesResult:
    """Result from get_updates."""
    msgs: list[dict[str, Any]]
    get_updates_buf: str
    ret: int
    longpolling_timeout_ms: int = 35000


@dataclass
class SendResult:
    """Result from send_message."""
    ret: int
    message_id: str | None = None


@dataclass
class UploadUrlResult:
    """Result from get_upload_url."""
    url: str
    filekey: str
    encrypt_query_param: str


class IlinkApiClient:
    """HTTP client for iLink Bot API."""

    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(35.0))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_headers(self) -> dict[str, str]:
        """Build request headers with auth and anti-replay."""
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            # Random UIN for anti-replay
            uin = str(random.randint(0, 2**32 - 1))
            headers["X-WECHAT-UIN"] = base64.b64encode(uin.encode()).decode()
        return headers

    async def _post(self, endpoint: str, data: dict[str, Any], timeout: int = 15) -> dict[str, Any]:
        """Generic POST request."""
        url = f"{self.base_url}/{endpoint}"
        headers = self._build_headers()

        logger.debug(f"POST {url}")

        resp = await self._client.post(url, json=data, headers=headers, timeout=timeout)
        if not resp.is_success:
            text = resp.text
            logger.error(f"API error {resp.status_code}: {text}")
            raise NetworkError(f"API error {resp.status_code}: {text}")
        return resp.json() if resp.text else {}

    async def _post_with_retry(self, endpoint: str, data: dict[str, Any], max_retries: int = 3):
        """POST with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                return await self._post(endpoint, data)
            except (httpx.HTTPError, NetworkError, Exception) as e:
                if attempt == max_retries - 1:
                    raise
                delay = min(2 ** attempt, 30)
                logger.warning(f"Retry {attempt+1}/{max_retries} after {delay}s: {e}")
                await asyncio.sleep(delay)

    async def get_bot_qrcode(self, bot_type: str = "3") -> QRCodeResult:
        """Get login QR code."""
        url = f"{self.base_url}/ilink/bot/get_bot_qrcode?bot_type={bot_type}"
        resp = await self._client.get(url)
        data = resp.json()
        return QRCodeResult(
            qrcode=data["qrcode"],
            qrcode_url=data["qrcode_img_content"],
        )

    async def get_qrcode_status(self, qrcode: str) -> QRStatusResult:
        """Poll QR code scan status (long-poll, 35s timeout)."""
        url = f"{self.base_url}/ilink/bot/get_qrcode_status?qrcode={qrcode}"
        headers = {"iLink-App-ClientVersion": "1"}

        resp = await self._client.get(url, headers=headers, timeout=35.0)
        data = resp.json()
        return QRStatusResult(
            status=data["status"],
            bot_token=data.get("bot_token"),
            ilink_bot_id=data.get("ilink_bot_id"),
            ilink_user_id=data.get("ilink_user_id"),
            baseurl=data.get("baseurl"),
        )

    async def get_updates(self, get_updates_buf: str = "", timeout: int = 35) -> UpdatesResult:
        """Long-poll for new messages."""
        data = {
            "get_updates_buf": get_updates_buf,
            "base_info": {"channel_version": "1.0.2"},
        }

        result = await self._post("ilink/bot/getupdates", data, timeout=timeout)
        return UpdatesResult(
            msgs=result.get("msgs", []),
            get_updates_buf=result.get("get_updates_buf", ""),
            ret=result.get("ret", 0),
            longpolling_timeout_ms=result.get("longpolling_timeout_ms", 35000),
        )

    async def send_message(
        self, to: str, text: str, context_token: str, client_id: str
    ) -> SendResult:
        """Send text message."""
        data = {
            "msg": {
                "from_user_id": "",
                "to_user_id": to,
                "client_id": client_id,
                "message_type": 2,  # BOT
                "message_state": 2,  # FINISH
                "context_token": context_token,
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            }
        }

        result = await self._post("ilink/bot/sendmessage", data)
        return SendResult(ret=result.get("ret", 0), message_id=client_id)
