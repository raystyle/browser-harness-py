# Shadow DOM

`document.querySelector` cannot see through a shadow boundary — two ways through.

## 1. Don't look, click (preferred)

CDP mouse events are dispatched at the **compositor** with viewport coordinates —
shadow DOM (open or closed) is transparent to them. Get coordinates from the AX tree
or a bounding rect, then `click_at_xy(x, y)`. This is the default answer.

## 2. Pierce open shadow roots in JS

```python
js("""(() => {
  const deep = (root, sel) => {
    const el = root.querySelector(sel);
    if (el) return el;
    for (const host of root.querySelectorAll('*')) {
      if (host.shadowRoot) { const hit = deep(host.shadowRoot, sel); if (hit) return hit; }
    }
    return null;
  };
  const el = deep(document, 'ion-button[class*="submit"]');
  return el ? el.getBoundingClientRect().toJSON() : null;
})()""")
```

## Rules that held up in practice

- `element.shadowRoot` is **null on closed** roots — no JS path in; coordinates and
  the AX tree (`Accessibility.getFullAXTree` exposes shadow content with
  `backendDOMNodeId`s) are the only routes.
- One `>>>`-style combinator does not exist in a CDP `Runtime.evaluate`; walk
  `shadowRoot` per level like the snippet above.
- Web-components frameworks (Ionic/Lit/Material) nest roots several levels deep —
  budget for recursion, and cache nothing across navigations.
