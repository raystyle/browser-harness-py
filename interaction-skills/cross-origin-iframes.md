# Cross-origin iframes

Cross-origin (out-of-process) iframes are **separate CDP targets** — `js()` from the
top page cannot reach them, and `contentDocument` is null. Attach to the frame's own
target instead.

## Find the frame target, evaluate in it

```python
tid = iframe_target("login-widget.example.com")   # first iframe target whose URL contains the substring
if tid:
    js("document.querySelector('input#email')?.value", target_id=tid)
```

`js(expression, target_id=...)` evaluates inside that frame; coordinate clicks still
work with plain viewport coordinates (the compositor routes them into the frame).

## Patterns

```python
tid = iframe_target("recaptcha") or iframe_target("google.com")
# inside-frame wait:
for _ in range(20):
    if js("!!document.querySelector('#ready')", target_id=tid): break
    wait(0.5)
```

## Rules that held up in practice

- `Target.getTargets` lists type `"iframe"` targets — that is the giveaway for
  cross-origin frames; same-origin frames never appear there.
- If `iframe_target` returns None, the frame may not have spawned yet — wait and
  retry after `wait_for_load()` + a beat.
- Login/SSO widgets are usually cross-origin: look for their target before assuming
  a selector failed.
- The AX tree (`Accessibility.getFullAXTree`) spans frames; a `backendDOMNodeId`
  from it can be clicked via its box model without touching `target_id` at all.
