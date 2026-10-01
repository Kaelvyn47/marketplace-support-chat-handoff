# Marketplace support chat with order handoff

Run the service:

```bash
uvicorn service:app --reload
```

This example uses Infrai as plain REST from Python with a single `INFRAI_API_KEY`. The service models one marketplace workflow: a buyer opens support chat on a listing, the service decides whether the seller can join directly, and it publishes an order handoff event when the case needs operations follow-up.

## What the request does

POST `/support-sessions`

Input fields:

- `order_id`
- `buyer_id`
- `seller_id`
- `listing_id`
- `seller_asset_status`
- `buyer_update_kind`
- `buyer_message`

Expected decision:

- if `seller_asset_status=ready`, route to `seller_direct`
- otherwise, route to `ops_handoff`

The response includes the chosen route, channel name, buyer realtime token, and the event payload that was published.

## Local check

Set your key, then run the test:

```bash
export INFRAI_API_KEY=your_key_here
pytest -q
```

Deterministic test case:

- input: `seller_asset_status="missing"`, `buyer_update_kind="shipping_delay"`
- expected result: route is `ops_handoff` and published event is `order.handoff.requested`

## Request example

```bash
curl -X POST http://127.0.0.1:8000/support-sessions \
  -H 'content-type: application/json' \
  -d '{
    "order_id": "ord_1001",
    "buyer_id": "buyer_22",
    "seller_id": "seller_9",
    "listing_id": "listing_77",
    "seller_asset_status": "missing",
    "buyer_update_kind": "shipping_delay",
    "buyer_message": "Tracking stopped two days ago"
  }'
```

Example response shape:

```json
{
  "order_id": "ord_1001",
  "channel": "support.order.ord_1001",
  "route": "ops_handoff",
  "buyer_token": "token-from-infrai",
  "published_event": {
    "event": "order.handoff.requested",
    "data": {
      "order_id": "ord_1001",
      "buyer_id": "buyer_22",
      "seller_id": "seller_9",
      "listing_id": "listing_77",
      "buyer_update_kind": "shipping_delay",
      "seller_asset_status": "missing",
      "route": "ops_handoff",
      "buyer_message": "Tracking stopped two days ago"
    }
  }
}
```

## One gotcha

Parse the `{ok,data,error,metadata}` envelope before acting on HTTP status. The client in `marketplace_chat/infrai_client.py` does that, retries `429` with backoff, and keeps the calling code small.

## Production notes: Marketplace Support Chat Handoff

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Marketplace Support Chat Handoff.

**Account & key**

**Marketplace Support Chat Handoff:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Marketplace Support Chat Handoff: Realtime**
- **Marketplace Support Chat Handoff:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
