from marketplace_chat.models import SupportSessionRequest
from marketplace_chat.support_handoff import SupportHandoffService


class FakeRealtime:
    def __init__(self) -> None:
        self.created_channels: list[str] = []
        self.deleted_channels: list[str] = []
        self.issued_tokens: list[dict] = []
        self.published: list[dict] = []

    def channel_create(self, channel: str) -> None:
        self.created_channels.append(channel)

    def channel_delete(self, channel: str) -> None:
        self.deleted_channels.append(channel)

    def token_issue(self, client_id: str, channels: list[str], capabilities: list[str], ttl_seconds: int) -> str:
        self.issued_tokens.append(
            {
                "client_id": client_id,
                "channels": channels,
                "capabilities": capabilities,
                "ttl_seconds": ttl_seconds,
            }
        )
        return "buyer-token-123"

    def publish_event(self, channel: str, event: str, data: dict, account_id: str) -> None:
        self.published.append(
            {
                "channel": channel,
                "event": event,
                "data": data,
                "account_id": account_id,
            }
        )


def test_missing_seller_asset_routes_to_ops_handoff_and_publishes_order_handoff() -> None:
    realtime = FakeRealtime()
    service = SupportHandoffService(realtime=realtime)
    request = SupportSessionRequest(
        order_id="ord_1001",
        buyer_id="buyer_22",
        seller_id="seller_9",
        listing_id="listing_77",
        seller_asset_status="missing",
        buyer_update_kind="shipping_delay",
        buyer_message="Tracking stopped two days ago",
    )

    result = service.open_session(request)

    assert result.route == "ops_handoff"
    assert result.channel == "support.order.ord_1001"
    assert result.buyer_token == "buyer-token-123"
    assert realtime.created_channels == ["support.order.ord_1001"]
    assert realtime.issued_tokens == [
        {
            "client_id": "buyer_22",
            "channels": ["support.order.ord_1001"],
            "capabilities": ["publish", "subscribe", "presence"],
            "ttl_seconds": 3600,
        }
    ]
    assert realtime.published == [
        {
            "channel": "support.order.ord_1001",
            "event": "order.handoff.requested",
            "data": {
                "order_id": "ord_1001",
                "buyer_id": "buyer_22",
                "seller_id": "seller_9",
                "listing_id": "listing_77",
                "buyer_update_kind": "shipping_delay",
                "seller_asset_status": "missing",
                "route": "ops_handoff",
                "buyer_message": "Tracking stopped two days ago",
            },
            "account_id": "seller_9",
        }
    ]
    assert realtime.deleted_channels == []


def test_channel_is_deleted_when_session_setup_fails() -> None:
    realtime = FakeRealtime()
    service = SupportHandoffService(realtime=realtime)
    request = SupportSessionRequest(
        order_id="ord_failed",
        buyer_id="buyer_22",
        seller_id="seller_9",
        listing_id="listing_77",
        seller_asset_status="missing",
        buyer_update_kind="shipping_delay",
        buyer_message="Tracking stopped two days ago",
    )

    def fail_token_issue(*args, **kwargs):
        raise RuntimeError("token issue failed")

    realtime.token_issue = fail_token_issue

    try:
        service.open_session(request)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected session setup to fail")

    assert realtime.deleted_channels == ["support.order.ord_failed"]
