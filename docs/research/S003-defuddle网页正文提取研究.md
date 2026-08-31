# S003 defuddle 网页正文提取研究

> 研究原型过程（为什么）。登记日 2026-08-31。
> 来源：`kepano/defuddle`（JS 库 + CLI）、PyPI `pydefuddle`、npm `defuddle`，本机 Node 24 / uv 实测。

## 结论速览

- **defuddle** 是 JS 库，把网页正文提取为干净 HTML / Markdown，并附带元数据（title、author、description、domain、favicon、image、language、published、site、wordCount）。
- 命令行：`defuddle parse <url|file|stdin> [--markdown|--json|--property <name>|--user-agent ...]`；无 `<source>` 或 `-` 时从 stdin 读 HTML。
- 本机 Node 24 已有，`npx defuddle` 可直接用，**无需安装**。
- PyPI 有 Python 移植 **`pydefuddle` 0.1.0**（依赖 beautifulsoup4 / lxml / markdownify / click / httpx / rich / pyperclip）。API：`pydefuddle.defuddle(html, url="", markdown=True) -> DefuddleResult`。

## 集成决策

三层回退，优先本地、依赖可选：

1. `pydefuddle`（Python 移植）—— 若可导入。
2. `npx defuddle parse - --json`（Node CLI）—— 本机已有 Node。
3. stdlib +（若存在）bs4 的最简正文回退。

`pydefuddle` 作为可选依赖组 `content`（`pip install browser-harness[content]`），不进入核心依赖；浏览器端解析优先走浏览器（复用登录会话 / JS），公开页走纯 HTTP。

## 关键实测

```powershell
# JS CLI（stdin HTML -> JSON，字段：content / contentMarkdown / title / domain / wordCount ...）
echo '<html>...</html>' | npx -y defuddle parse - --json

# Python 移植
from pydefuddle import defuddle
r = defuddle(html, url=url, markdown=True)  # -> content / markdown / title / domain / word_count ...
```

## 实现位置

- `agent-workspace\agent_helpers.py`：`_pydefuddle_parse / _npx_defuddle_parse / _fallback_parse / _defuddle_html`（归一化分发）、`extract_page_content()`、`extract_url_content(url, markdown, use_browser)`。
- `agent-workspace\page_text.py`：CLI（`URL [--markdown|--text|--json] [--browser]`、`--current`）。
- 归一化返回字段统一：`title / url / domain / author / published / description / image / favicon / language / site / word_count / content_html / markdown / text / engine`。
