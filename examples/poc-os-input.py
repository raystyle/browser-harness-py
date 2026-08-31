"""POC: OS-level input vs CDP Input domain leak (Windows).

Proves the CDP Input domain leak (pageX==screenX) and shows that posting
WM_LBUTTONDOWN/UP to the Chrome render widget fixes it. Self-contained ctypes
implementation (no GPL dependency).

Run (from repo root):
  uv run --no-project --with websockets python examples/poc-os-input.py
"""

import asyncio
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

import websockets


user32 = ctypes.windll.user32
WS_CHILD = 1
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEWHEEL = 0x020A
MK_LBUTTON = 0x0001


def _chrome_path():
    for key in ("CHROME_PATH", "BH_CHROME_PATH"):
        p = os.environ.get(key, "").strip()
        if p and Path(p).exists():
            return p
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise SystemExit("chrome.exe not found; set CHROME_PATH")


def _render_hwnd_for_pid(pid):
    """Find the Chrome_RenderWidgetHostHWND child window for a browser pid."""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_top(hwnd, _lparam):
        proc = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
        if proc.value == pid and user32.IsWindowVisible(hwnd):
            child = wintypes.HWND()
            user32.EnumChildWindows(hwnd, _enum_child, 0)
        return True

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_child(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "Chrome_RenderWidgetHostHWND":
            found.append(hwnd)
        return True

    user32.EnumWindows(_enum_top, 0)
    return found[0] if found else None


def _post_click(hwnd, x, y):
    lp = (int(y) << 16) | (int(x) & 0xFFFF)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def _post_wheel(hwnd, x, y, delta):
    lp = (int(y) << 16) | (int(x) & 0xFFFF)
    user32.PostMessageW(hwnd, WM_MOUSEWHEEL, delta << 16, lp)


def _dpi_scale(hwnd):
    try:
        dpi = user32.GetDpiForWindow(hwnd)
    except Exception:
        dpi = 96
    return dpi / 96.0


PAGE_HTML = """<!doctype html><meta charset="utf-8">
<button id="btn" style="position:fixed;left:100px;top:100px;width:200px;height:50px">click</button>
<div style="position:fixed;left:100px;top:180px">scroll marker</div>
<div style="height:3000px"></div>
<script>
window.__info = null;
document.getElementById('btn').addEventListener('click', function(e){
  window.__info = {pageX:e.pageX, pageY:e.pageY, screenX:e.screenX, screenY:e.screenY,
    is_bot:(e.pageX===e.screenX && e.pageY===e.screenY)};
});
</script>"""


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self._id = 0

    async def send(self, method, params=None):
        self._id += 1
        await self.ws.send(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    async def eval(self, expr):
        r = await self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return r.get("result", {}).get("value")


async def main():
    profile = tempfile.mkdtemp(prefix="poc-chrome-")
    page = Path(profile) / "page.html"
    page.write_text(PAGE_HTML, encoding="utf-8")
    port = 9223
    proc = subprocess.Popen(
        [_chrome_path(), f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", page.as_uri()],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = None
        for _ in range(60):
            try:
                data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1))
                for t in data:
                    if t.get("type") == "page" and page.as_uri() in t.get("url", ""):
                        ws_url = t["webSocketDebuggerUrl"]
                if ws_url:
                    break
            except Exception:
                time.sleep(0.3)
        if not ws_url:
            raise RuntimeError("Chrome DevTools target not found")

        async with websockets.connect(ws_url, max_size=None) as ws:
            cdp = CDP(ws)
            for _ in range(60):
                ready = await cdp.eval("!!document.getElementById('btn')")
                if ready:
                    break
                await asyncio.sleep(0.2)

            rect = await cdp.eval(
                "JSON.stringify(document.getElementById('btn').getBoundingClientRect())"
            )
            rect = json.loads(rect)
            cx, cy = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2

            hwnd = _render_hwnd_for_pid(proc.pid)
            if not hwnd:
                raise RuntimeError("Chrome_RenderWidgetHostHWND not found")
            scale = _dpi_scale(hwnd)
            px, py = int(cx * scale), int(cy * scale)

            # (A) CDP Input domain -> leak (page == screen)
            await cdp.send("Input.dispatchMouseEvent",
                           {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
            await cdp.send("Input.dispatchMouseEvent",
                           {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
            cdp_info = await cdp.eval("window.__info")

            # (B) OS-level WM click -> no leak
            _post_click(hwnd, px, py)
            os_info = await cdp.eval("window.__info")

            scroll_before = await cdp.eval("window.scrollY")
            _post_wheel(hwnd, px, py, -120)
            await asyncio.sleep(0.2)
            scroll_after = await cdp.eval("window.scrollY")

            print(json.dumps({
                "scale": scale,
                "button_viewport_css": [cx, cy],
                "button_client_px": [px, py],
                "cdp_input": cdp_info,
                "os_level_input": os_info,
                "scroll_before": scroll_before,
                "scroll_after": scroll_after,
            }, ensure_ascii=False, indent=2))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("This POC is Windows-only (SendInput/PostMessage)")
    asyncio.run(main())
