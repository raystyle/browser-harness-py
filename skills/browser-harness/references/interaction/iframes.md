# Iframes

Same-origin iframes are reachable straight from `js(...)` through
`contentDocument` / `contentWindow`.

## Read and act inside a same-origin frame

```python
js("const f = document.querySelector('iframe'); f.contentDocument.title")
js("const b = document.querySelector('iframe').contentDocument.querySelector('button'); b.click()")
```

## The coordinate warning

`click_at_xy(x, y)` takes **viewport** coordinates — the compositor resolves which
frame sits at that point, so a viewport coordinate inside an iframe works with no
frame math. But element rects read *inside* a frame (`getBoundingClientRect` via
`contentDocument`) are **frame-local**: add the iframe's own viewport rect before
using them as click coordinates.

```python
# frame-local -> viewport
js("""(() => {
  const f = document.querySelector('iframe');
  const fr = f.getBoundingClientRect();
  const el = f.contentDocument.querySelector('button');
  const er = el.getBoundingClientRect();
  return {x: fr.left + er.left + er.width/2, y: fr.top + er.top + er.height/2};
})()""")
```

Or skip coordinates entirely: find the element's `backendDOMNodeId` via the AX tree
(`Accessibility.getFullAXTree` reaches into same-origin frames) and use its box model.

## Rules that held up in practice

- `wait_for_element(selector)` polls the **top** document only; for frame content,
  poll `js("!!document.querySelector('iframe')?.contentDocument?.querySelector('...')")`.
- Cross-origin frames are separate targets — see cross-origin-iframes.md.
- After any frame navigation, re-grab `contentDocument`; a cached reference points
  at a detached document.
