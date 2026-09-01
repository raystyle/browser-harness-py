# Uploads

Set files directly on the `<input type="file">` — never click through the OS file dialog.

## The helper

```python
upload_file('input[type="file"]', r"C:\path\to\file.pdf")   # absolute path required
upload_file('#multi', [r"C:\a.png", r"C:\b.png"])            # list for multi-file inputs
```

Backed by `DOM.setFileInputFiles`: the file lands on the input without any dialog,
even when the input is hidden behind a styled drop zone.

## Pattern

```python
t = new_tab("https://example.com/upload")
wait_for_element('input[type="file"]', visible=False)   # hidden inputs exist in the DOM
upload_file('input[type="file"]', str(Path("report.pdf").resolve()))
wait_for_network_idle()                                  # upload POST fires with no DOM change
print(js("document.querySelector('.upload-status')?.innerText"))
```

## Rules that held up in practice

- `path` must be absolute; build one with `tempfile.mkstemp` when generating the file on the fly.
- Many drop zones accept the file once the hidden input has it — the site's own
  "drag & drop" UI is optional, not required.
- After `upload_file`, a submit button often flips to enabled only after the site's
  change event: if it stays disabled, `dispatch_key('input[type="file"]', 'change')`
  is the wrong tool — `upload_file` already sets files at the DOM level; check for a
  JS-rendered status region with `wait_for_element` instead.
- `Network.setFileInputFiles` needs no visibility: do not `activate_tab` for uploads.
