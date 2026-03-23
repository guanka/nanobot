"""Test iLink API client."""

import pytest

from nanobot.channels.weixin.api import IlinkApiClient


@pytest.mark.asyncio
async def test_get_bot_qrcode():
    """Test getting QR code."""
    api = IlinkApiClient("https://ilinkai.weixin.qq.com")
    async with api:
        result = await api.get_bot_qrcode()
        assert result.qrcode
        assert result.qrcode_url.startswith("http")


@pytest.mark.asyncio
async def test_get_qrcode_status():
    """Test polling QR status."""
    api = IlinkApiClient("https://ilinkai.weixin.qq.com")
    async with api:
        result = await api.get_qrcode_status("test_qrcode")
        assert result.status in ["wait", "scaned", "expired", "confirmed"]
