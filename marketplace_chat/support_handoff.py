from dataclasses import dataclass
from typing import Protocol

from .infrai_client import InfraiClient
from .models import PublishedEvent, SupportSessionRequest, SupportSessionResponse


class RealtimePort(Protocol):
    def channel_create(self, channel: str) -> None:
        ...

    def channel_delete(self, channel: str) -> None:
        ...

    def token_issue(self, client_id: str, channels: list[str], capabilities: list[str], ttl_seconds: int) -> str:
        ...

    def publish_event(self, channel: str, event: str, data: dict, account_id: str) -> None:
        ...


@dataclass
class InfraiRealtimePort:
    infrai: InfraiClient

    def channel_create(self, channel: str) -> None:
        self.infrai.realtime.channel.create(channel=channel, type="presence", vendor="ably")

    def channel_delete(self, channel: str) -> None:
        self.infrai.realtime.channel.delete(channel=channel)

    def token_issue(self, client_id: str, channels: list[str], capabilities: list[str], ttl_seconds: int) -> str:
        data = self.infrai.realtime.token.issue(
            client_id=client_id,
            channels=channels,
            capabilities=capabilities,
            ttl_seconds=ttl_seconds,
        )
        token = data.get("token")
        if not isinstance(token, str) or not token:
            raise ValueError("token missing from token issue response")
        return token

    def publish_event(self, channel: str, event: str, data: dict, account_id: str) -> None:
        self.infrai.realtime.publish.publish(
            channel=channel,
            event=event,
            data=data,
            account_id=account_id,
        )


@dataclass
class SupportHandoffService:
    realtime: RealtimePort

    @classmethod
    def from_env(cls) -> "SupportHandoffService":
        infrai = InfraiClient.from_env()
        return cls(realtime=InfraiRealtimePort(infrai))

    def open_session(self, request: SupportSessionRequest) -> SupportSessionResponse:
        route = self._route(request)
        channel = f"support.order.{request.order_id}"
        self.realtime.channel_create(channel)
        try:
            buyer_token = self.realtime.token_issue(
                client_id=request.buyer_id,
                channels=[channel],
                capabilities=["publish", "subscribe", "presence"],
                ttl_seconds=3600,
            )
            event_name = "order.handoff.requested" if route == "ops_handoff" else "buyer.update.received"
            event_data = {
                "order_id": request.order_id,
                "buyer_id": request.buyer_id,
                "seller_id": request.seller_id,
                "listing_id": request.listing_id,
                "buyer_update_kind": request.buyer_update_kind,
                "seller_asset_status": request.seller_asset_status,
                "route": route,
                "buyer_message": request.buyer_message,
            }
            self.realtime.publish_event(
                channel=channel,
                event=event_name,
                data=event_data,
                account_id=request.seller_id,
            )
        except Exception:
            self.realtime.channel_delete(channel)
            raise
        return SupportSessionResponse(
            order_id=request.order_id,
            channel=channel,
            route=route,
            buyer_token=buyer_token,
            published_event=PublishedEvent(event=event_name, data=event_data),
        )

    def _route(self, request: SupportSessionRequest) -> str:
        if request.seller_asset_status == "ready":
            return "seller_direct"
        return "ops_handoff"
