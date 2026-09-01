# Downloads

Point the browser at a known directory before triggering the download, then watch
the filesystem — no dialog interaction needed.

## Pattern

```python
import pathlib
dl = str(pathlib.Path.home() / "Downloads" / "bh")

cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath=dl)
js("document.querySelector('a[href$=\".pdf\"]').click()")   # or click_at_xy

target = pathlib.Path(dl) / "report.pdf"
for _ in range(40):                     # .crdownload suffix while in flight
    if target.exists() and target.suffix != ".crdownload":
        break
    wait(0.5)
print("downloaded:", target, target.stat().st_size)
```

## Rules that held up in practice

- Set the behavior **before** the click; it applies to downloads initiated after the call.
- `behavior="allowAndName"` saves with the GUID name; plain `"allow"` keeps the
  server-provided filename — usually what you want.
- Chrome writes `<name>.crdownload` while in flight; poll for the rename, not just existence.
- The download is served by the **profile's** browser — with the default daemon that
  is the isolated agent Chrome, so `downloadPath` lands wherever you point it,
  independent of which machine user runs the script.
