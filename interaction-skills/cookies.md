# Cookies

Read and write cookies through CDP on the logged-in browser. Keep two states apart:
**browser state** (cookies, localStorage — belongs to the profile, survives pages)
vs **page state** (DOM, JS variables — dies on navigation). Never "fix" a login by
mutating page state; set cookies and reload.

## Read

```python
cookies = cdp("Network.getAllCookies")["cookies"]
mine = [c for c in cookies if "example.com" in c["domain"]]
import json; print(json.dumps(mine, indent=2))
```

`Storage.getCookies` is the newer flavor; `Network.getAllCookies` returns every
cookie in the profile regardless of the attached tab.

## Write / restore

```python
cdp("Network.setCookies", cookies=[{
    "name": "session", "value": "abc", "domain": ".example.com",
    "path": "/", "secure": True, "httpOnly": True,
}])
goto_url("https://example.com/")   # reload so the page picks them up
wait_for_load()
```

Restore a saved session by writing the full list back (drop `size`/`session` fields
the API won't accept), then navigate. Export first from the same profile the cookies
came from — cookies are profile-bound.

## Rules that held up in practice

- Cookie changes need a **navigation** to take effect; setting cookies on the
  current DOM does nothing until reload.
- `httpOnly` cookies are readable via CDP but not via `document.cookie` in `js(...)`.
- For "am I logged in?" checks, prefer `js("document.cookie")` presence of a known
  cookie or a URL check over scraping the page — cheaper and stabler.
- Never paste cookie values into logs or transcripts.
