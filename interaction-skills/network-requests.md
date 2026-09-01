# Network Requests

The daemon enables `Network` on the attached session and buffers events; drain them
to see what the page did, or wait for quiet.

## What fired

```python
cdp("Network.enable")  # already enabled on the attached session; idempotent

events = drain_events()          # returns and clears the daemon's buffer (last ~500)
for e in events:
    if e["method"] == "Network.requestWillBeSent":
        r = e["params"]["request"]
        print(r["method"], r["url"])
    if e["method"] == "Network.responseReceived":
        print("  ->", e["params"]["response"]["status"], e["params"]["response"]["url"][:90])
```

Drain **before** the action, then drain again — the delta is the traffic your click caused.

## Response body

```python
rid = next(e["params"]["requestId"] for e in drain_events()
           if e["method"] == "Network.responseReceived"
           and "/api/cart" in e["params"]["response"]["url"])
body = cdp("Network.getResponseBody", requestId=rid)
import json; cart = json.loads(body["body"])
```

## Quiet down

```python
wait_for_network_idle(timeout=10, idle_ms=500)   # no Network.* events for 500ms
```

Use after form submits and SPA route changes that fetch without a visible DOM change.

## Plain fetch — skip the browser

```python
html = http_get("https://example.com/data.json")          # no browser involved
```

## Rules that held up in practice

- The event buffer is bounded (~500) — drain early, drain often on chatty pages.
- Events are filtered to the **attached session**; after `switch_tab`/`new_tab` the
  fresh session re-enables domains automatically, but old-tab events are gone.
- `getResponseBody` works only while the response is still in the browser's cache —
  fetch it soon after the event.
