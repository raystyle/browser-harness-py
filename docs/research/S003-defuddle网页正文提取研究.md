# S003 defuddle 网页正文提取研究

> 研究原型过程（为什么）。登记日 2026-08-31。
> 来源：`kepano/defuddle`（JS 库 + CLI）、PyPI `pydefuddle`、npm `defuddle`，本机 Node 24 / uv 实测。

## 结论速览

- **defuddle** 是 JS 库，把网页正文提取为干净 HTML / Markdown，并附带元数据。[实证: npx 实测输出字段]
- 命令行：`defuddle parse <url|file|stdin> [--markdown|--json|--property <name>|--user-agent ...]`。[实证: CLI 实测]
- PyPI 有 Python 移植 **`pydefuddle` 0.1.0**。API：`pydefuddle.defuddle(html, url="", markdown=True) -> DefuddleResult`。[实证: PyPI JSON 核实]

## 集成决策

两层回退（后来 npx 回退已移除，改为纯 Python）：

1. `pydefuddle`（Python 移植，核心依赖）—— 若可导入。
2. stdlib +（若存在）bs4 的最简正文回退。

`pydefuddle` 现为核心依赖（`pip install browser-harness` 自带）；浏览器端解析优先走浏览器（复用登录会话 / JS），公开页走纯 HTTP。[实证: pyproject.toml dependencies 含 pydefuddle]

## 关键实测

```powershell
# JS CLI（stdin HTML -> JSON，字段：content / contentMarkdown / title / domain / wordCount ...）
echo '<html>...</html>' | npx -y defuddle parse - --json

# Python 移植
from pydefuddle import defuddle
r = defuddle(html, url=url, markdown=True)  # -> content / markdown / title / domain / word_count ...
```

## 实现位置

- `src\browser_harness\agent_helpers.py`：`_pydefuddle_parse / _fallback_parse / _defuddle_html`（归一化分发）、`extract_page_content()`、`extract_url_content()`。
- `src\browser_harness\web_fetch.py`：CLI（`URL [--markdown|--text|--json] [--browser]`、`--current`）。
- 归一化返回字段统一：`title / url / domain / author / published / description / image / favicon / language / site / word_count / content_html / markdown / text / engine`。
