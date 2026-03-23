"""WeChat authentication and token management."""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

from .api import IlinkApiClient, QRCodeResult, QRStatusResult

from loguru import logger


class AuthError(Exception):
    """Authentication error."""
    pass


def redact_token(token: str) -> str:
    """Redact token for logging."""
    if len(token) > 16:
        return f"{token[:8]}...{token[-8:]}"
    return "***"


class TokenStorage:
    """Persist WeChat bot token to filesystem."""

    def __init__(self, config_path: str):
        self.token_file = os.path.join(config_path, ".weixin-token.json")

    def save_token(self, token_data: dict[str, Any]):
        """Save token with restricted permissions."""
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)
        os.chmod(self.token_file, 0o600)  # Owner read/write only
        logger.debug(f"Token saved to {self.token_file}")

    def load_token(self) -> dict[str, Any] | None:
        """Load existing token if exists."""
        if not os.path.exists(self.token_file):
            return None
        with open(self.token_file, "r") as f:
            return json.load(f)

    def clear_token(self):
        """Remove saved token."""
        if os.path.exists(self.token_file):
            os.remove(self.token_file)
            logger.info("Token cleared")


@dataclass
class AuthResult:
    """Result from login attempt."""
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


class AuthManager:
    """Handle QR code login flow."""

    def __init__(self, base_url: str, config_path: str, api_client: IlinkApiClient):
        self.base_url = base_url
        self.storage = TokenStorage(config_path)
        self.api_client = api_client

    async def login(self, force: bool = False) -> AuthResult:
        """Login via QR code or load existing token."""
        if not force:
            existing = self.storage.load_token()
            if existing:
                logger.info("Loaded existing token")
                return AuthResult(success=True, data=existing)

        try:
            import qrcode_terminal
        except ImportError:
            logger.error("qrcode-terminal not installed. Run: pip install qrcode-terminal")
            return AuthResult(success=False, error="qrcode-terminal required")

        # Get QR code
        logger.info("Fetching QR code for login...")
        qr_result = await self.api_client.get_bot_qrcode(bot_type="3")

        logger.info("Please scan QR code with WeChat:")
        qrcode_terminal.draw(qr_result.qrcode_url, small=True)

        # Poll QR status (8 min timeout)
        timeout = 480  # seconds
        attempts = 0

        while attempts < timeout:
            try:
                status = await self.api_client.get_qrcode_status(qr_result.qrcode)

                if status.status == "confirmed" and status.bot_token:
                    token_data = {
                        "bot_token": status.bot_token,
                        "base_url": status.baseurl or self.base_url,
                        "account_id": status.ilink_bot_id,
                        "user_id": status.ilink_user_id,
                        "saved_at": "now",
                    }
                    self.storage.save_token(token_data)
                    logger.info(f"Login successful! Account: {status.ilink_bot_id}")
                    logger.info(f"Token: {redact_token(status.bot_token)}")
                    return AuthResult(success=True, data=token_data)

                if status.status == "expired":
                    # Refresh QR code
                    qr_result = await self.api_client.get_bot_qrcode(bot_type="3")
                    logger.info("QR expired, scanning new code...")
                    qrcode_terminal.draw(qr_result.qrcode_url, small=True)

            except Exception as e:
                logger.warning(f"Error checking QR status: {e}")

            attempts += 1
            await asyncio.sleep(1)

        return AuthResult(success=False, error="Login timeout")

    def get_token(self) -> dict[str, Any] | None:
        """Get current token."""
        return self.storage.load_token()
