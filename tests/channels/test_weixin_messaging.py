"""Test message conversion."""

from nanobot.channels.weixin.messaging import (
    WeixinMessageType,
    extract_text_from_items,
    extract_media_from_items,
    weixin_to_inbound,
    outbound_to_weixin,
)
from nanobot.bus.events import InboundMessage, OutboundMessage


def test_extract_text_from_text_item():
    """Test extracting text from text item."""
    item = {"type": WeixinMessageType.TEXT, "text_item": {"text": "hello"}}
    result = extract_text_from_items([item])
    assert result == "hello"


def test_extract_text_from_voice_item():
    """Test extracting text from voice item."""
    item = {"type": WeixinMessageType.VOICE, "voice_item": {"text": "transcription"}}
    result = extract_text_from_items([item])
    assert result == "transcription"


def test_extract_media_from_image_item():
    """Test extracting media from image item."""
    item = {"type": WeixinMessageType.IMAGE, "image_item": {"url": "http://example.com/image.jpg"}}
    result = extract_media_from_items([item])
    assert result is not None
    assert result["type"] == "image"
    assert result["data"]["url"] == "http://example.com/image.jpg"


def test_weixin_to_inbound():
    """Test converting iLink message to InboundMessage."""
    msg = {
        "from_user_id": "user123",
        "to_user_id": "bot456",
        "item_list": [
            {"type": 1, "text_item": {"text": "hello world"}}
        ]
    }
    inbound = weixin_to_inbound(msg, "bot456")

    assert inbound.channel == "weixin"
    assert inbound.sender_id == "user123"
    assert inbound.chat_id == "bot456"
    assert inbound.content == "hello world"
    assert inbound.metadata["account_id"] == "bot456"
    assert inbound.metadata["context_token"] is None


def test_outbound_to_weixin():
    """Test converting OutboundMessage to iLink message."""
    msg = OutboundMessage(
        channel="weixin",
        chat_id="user123",
        content="hello"
    )
    weixin_msg = outbound_to_weixin(msg, "test_token")

    assert weixin_msg["msg"]["to_user_id"] == "user123"
    assert weixin_msg["msg"]["item_list"][0]["text_item"]["text"] == "hello"
    assert weixin_msg["msg"]["context_token"] == "test_token"
