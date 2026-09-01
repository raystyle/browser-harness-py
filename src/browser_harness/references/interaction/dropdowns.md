# Dropdowns

Opening a dropdown **changes the DOM** — coordinates read before the open are stale.

## Pattern (custom widget)

```python
# 1. open it (coordinate click on the trigger)
q = cdp("DOM.getBoxModel", backendNodeId=trigger_node)["model"]["content"]
click_at_xy(sum(q[0::2])/4, sum(q[1::2])/4)
wait_for_element('[role="listbox"]', timeout=5, visible=True)

# 2. RE-READ rects from the freshly rendered list — never reuse step-1 coordinates
opt = js("""(() => {
  const el = [...document.querySelectorAll('[role="option"]')]
    .find(o => o.innerText.includes('Ship'));
  const r = el.getBoundingClientRect();
  return {x: r.left + r.width/2, y: r.top + r.height/2};
})()""")
click_at_xy(opt["x"], opt["y"])

# 3. verify
print(js("document.querySelector('.selected')?.innerText"))
```

## Native `<select>` — no clicks at all

```python
js("""(() => {
  const s = document.querySelector('select#country');
  s.value = 'DE';
  s.dispatchEvent(new Event('input',  {bubbles: true}));
  s.dispatchEvent(new Event('change', {bubbles: true}));
})()""")
```

## Keyboard alternative (comboboxes)

Focus the trigger, then `press_key("ArrowDown")` / `press_key("Enter")` — works when
the widget listens to keys and the menu renders per keystroke.

## Rules that held up in practice

- Re-read element rects after every open/hover that can render new DOM — the #1
  source of "clicked and nothing happened".
- Options can render in a portal at `<body>` level, far from the trigger in the DOM
  tree — select by role/text, not by DOM ancestry.
