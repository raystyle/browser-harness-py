# Drag and drop

Two flavors — pick by what the page listens to.

## 1. Mouse-event drags (sortables, sliders, map pan)

Interpolate the move: a jump from A to B in one event is ignored by most drag logic.

```python
def drag(x1, y1, x2, y2, steps=12):
    cdp("Input.dispatchMouseEvent", type="mouseMoved", x=x1, y=y1)
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x1, y=y1, button="left", clickCount=1)
    for i in range(1, steps + 1):
        cdp("Input.dispatchMouseEvent", type="mouseMoved",
            x=x1 + (x2 - x1) * i / steps, y=y1 + (y2 - y1) * i / steps, button="left")
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x2, y=y2, button="left", clickCount=1)
```

Get the coordinates from box models / the AX tree, then verify the result with a
targeted `js(...)` check (order attribute, class change, slider value).

## 2. HTML5 DnD (dragstart/dragover/drop listeners)

CDP mouse events do NOT synthesize `dragstart`. Dispatch the DOM events instead:

```python
js("""(() => {
  const src = document.querySelector('#item'), dst = document.querySelector('#bin');
  const dt = new DataTransfer();
  src.dispatchEvent(new DragEvent('dragstart', {bubbles: true, dataTransfer: dt}));
  dst.dispatchEvent(new DragEvent('dragover',  {bubbles: true, dataTransfer: dt}));
  dst.dispatchEvent(new DragEvent('drop',      {bubbles: true, dataTransfer: dt}));
  src.dispatchEvent(new DragEvent('dragend',   {bubbles: true, dataTransfer: dt}));
})()""")
```

## Rules that held up in practice

- Try the DOM-event path first for "drag into folder/trash/upload" UIs — it is
  deterministic and does not need the window visible.
- Sliders: skip drags entirely; find the fill percentage and compute the x for the
  target value, or set the value via `js` and fire `input`/`change` like `fill_input` does.
