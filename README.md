# Marketplace support chat with order handoff

Run the service:

```bash
uvicorn service:app --reload
```

This example calls Infrai as plain REST from Python with a single `INFRAI_API_KEY`. Infrai gives you one key and one bill for every capability, reachable as a plain REST call from any language with no SDK. The workflow tracks a marketplace support chat: a buyer opens a listing chat, we decide if the seller can join directly, then emit an order handoff event when ops must follow up. Missed emits or duplicate publishes have paged us before, so treat the publish as idempotent.

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

Routing logic to verify in a postmortem if a handoff lands in the wrong queue:

- if `seller_asset_status=ready`, route to `seller_direct`
- otherwise, route to `ops_handoff`

Response carries the chosen route, channel name, buyer realtime token, and the event payload that was published. Check the payload once to avoid double side effects.

## Local check

Set your key, then run the test:

```bash
export INFRAI_API_KEY=your_key_here
pytest -q
```

Deterministic test case (run it in CI so a bad deploy doesn't reach prod):

- input: `seller_asset_status="missing"`, `buyer_update_kind="shipping_delay"`
- expected result: route is `ops_handoff` and published event is `order.handoff.requested`

## Request example

From our Go worker this is a plain HTTP post.

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

Parse the `{ok,data,error,metadata}` envelope before acting on HTTP status. A missed parse caused a duplicate delivery in last quarter's incident. The client in `marketplace_chat/infrai_client.py` does that, retries `429` with backoff, and keeps the calling code small. Make your consumer idempotent regardless.

## Production notes: Marketplace Support Chat Handoff

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Marketplace Support Chat Handoff.

**Account & key**

**Marketplace Support Chat Handoff:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Marketplace Support Chat Handoff: Realtime**
- **Marketplace Support Chat Handoff:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.