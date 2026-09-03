import base64
import io
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# browser_harness resolves BH_HOME-dependent paths eagerly at import (the
# workspace constant in helpers, and since v0.6.8 default-path resolution can
# even rename a legacy agent-workspace). Pin BH_HOME to a scratch dir BEFORE
# any browser_harness import so the suite never touches the real
# ~/.config/browser-harness — per-test setenv/monkeypatch still overrides.
_TEST_HOME = Path(tempfile.gettempdir()) / "bh-unit-test-home"
if _TEST_HOME.exists():
    shutil.rmtree(_TEST_HOME)
_TEST_HOME.mkdir(parents=True)
os.environ["BH_HOME"] = str(_TEST_HOME)


def make_png(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def fake_png():
    return make_png
