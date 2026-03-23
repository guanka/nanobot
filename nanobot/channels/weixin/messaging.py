"""Message conversion between iLink and nanobot."""

from typing import Any
from enum import IntEnum

from nanobot.bus.events import InboundMessage, OutboundMessage

from loguru import logger


class WeixinMessageType(IntEnum):
    """iLink message item types."""
    TEXT = 1
    IMAGE = 2
    VOICE = 3
    FILE = 4
    VIDEO = 5


def extract_text_from_items(item_list: list[dict[str, Any]]) -> str:
    """Extract text content from message items."""
    for item in item_list:
        if item.get("type") == WeixinMessageType.TEXT:
            return item.get("text_item", {}).get("text", "")
        if item.get("type") == WeixinMessageType.VOICE:
            return item.get("voice_item", {}).get("text", "")
    return ""


def extract_media_from_items(item_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Extract media information from message items."""
    for item in item_list:
        msg_type = item.get("type")
        if msg_type == WeixinMessageType.IMAGE:
            return {"type": "image", "data": item.get("image_item")}
        if msg_type == WeixinMessageType.FILE:
            return {"type": "file", "data": item.get("file_item")}
        if msg_type == WeixinMessageType.VOICE:
            return {"type": "voice", "data": item.get("voice_item")}
        if msg_type == WeixinMessageType.VIDEO:
            return {"type": "video", "data": item.get("video_item")}
    return None


def weixin_to_inbound(msg: dict[str, Any], account_id: str) -> InboundMessage:
    """Convert iLink message to nanobot InboundMessage."""
    from_user_id = msg.get("from_user_id", "")
    to_user_id = msg.get("to_user_id", "")
    item_list = msg.get("item_list", [])

    # Extract text
    text = extract_text_from_items(item_list)

    # Extract media
    media = extract_media_from_items(item_list)
    media_urls = [media.get("url")] if media and media.get("url") else []

    # Build metadata with context_token for replies
    metadata = {
        "account_id": account_id,
        "context_token": msg.get("context_token"),
        "create_time_ms": msg.get("create_time_ms"),
        "group_id": msg.get("group_id"),
    }

    inbound = InboundMessage(
        channel="weixin",
        sender_id=from_user_id,
        chat_id=to_user_id,
        content=text,
        media=media_urls,
        metadata=metadata,
    )

    return inbound


def outbound_to_weixin(msg: OutboundMessage, context_token: str) -> dict[str, Any]:
    """Convert nanobot OutboundMessage to iLink message."""
    return {
        "msg": {
            "from_user_id": "",
            "to_user_id": msg.chat_id,
            "message_type": 2,  # BOT
            "message_state": 2,  # FINISH
            "context_token": context_token,
            "item_list": [
                {"type": WeixinMessageType.TEXT, "text_item": {"text": msg.content}}
            ],
        }
    }
