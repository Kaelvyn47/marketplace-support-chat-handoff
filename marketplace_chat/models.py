from typing import Literal

from pydantic import BaseModel, Field


SellerAssetStatus = Literal["ready", "missing", "pending_review"]
BuyerUpdateKind = Literal["shipping_delay", "damaged_item", "address_change", "general_question"]
SupportRoute = Literal["seller_direct", "ops_handoff"]


class SupportSessionRequest(BaseModel):
    order_id: str = Field(min_length=1)
    buyer_id: str = Field(min_length=1)
    seller_id: str = Field(min_length=1)
    listing_id: str = Field(min_length=1)
    seller_asset_status: SellerAssetStatus
    buyer_update_kind: BuyerUpdateKind
    buyer_message: str = Field(min_length=1, max_length=1000)


class PublishedEvent(BaseModel):
    event: str
    data: dict


class SupportSessionResponse(BaseModel):
    order_id: str
    channel: str
    route: SupportRoute
    buyer_token: str
    published_event: PublishedEvent
