# Print as PDF

One CDP call on the attached tab; write the base64 result to disk.

```python
import base64, pathlib
r = cdp("Page.printToPDF",
        printBackground=True,      # include CSS backgrounds (most pages look wrong without it)
        landscape=False,
        marginTop=0.4, marginBottom=0.4, marginLeft=0.4, marginRight=0.4,  # inches
        scale=1.0,
)
out = pathlib.Path("page.pdf")
out.write_bytes(base64.b64decode(r["data"]))
print(out, out.stat().st_size)
```

## Rules that held up in practice

- `printBackground=True` is almost always wanted; default False drops all backgrounds.
- The tab must have finished rendering: `wait_for_load()` first, plus
  `wait_for_element(...)` for the element you actually care about on SPAs.
- Printing a background tab works without `activate_tab` — but pages that pause
  rendering while hidden (canvas charts, lazy maps) need `activate_tab(current_tab())`
  first, same as a timed-out scroll.
- For the whole of a long page, pass `preferCSSPageSize=True` when the site ships a
  print stylesheet; otherwise Chrome paginates at default size.
