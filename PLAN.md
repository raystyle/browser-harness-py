# PLAN：当前目标实施计划

> 角色：**当前目标方案文档**——怎么做。分工：`TODO.md`=做到哪；本文件=怎么做；通用工作流见 `docs\guide\`。

## 当前目标：browser-harness 测试（Windows 收尾 + macOS 接管）

> 对应 `GOAL.md`，登记日 2026-08-31。

## 路线总览

| 阶段 | 范围 | 状态 |
| --- | --- | --- |
| 0 | Windows：doctor + 真实 Chrome 连接/会话复用 + 单元测试 | 已完成（181/190，9 个 Windows 环境失败） |
| 1 | Windows 收尾：只读冒烟 + 集成测试 + 修 9 用例到 190/190 | 待办 |
| 2 | macOS 接管：环境 + mac-approve + 冒烟 + 单元/集成 | 待办 |
| 3 | Linux（可选）：冒烟 + 单元（注意 Snap Chromium CDP 阻断） | 待办 |

## 1. Windows 收尾

1. 真实浏览器只读冒烟：`list_tabs()` / `js("document.title")` / `capture_screenshot()`（不改变浏览器状态）。
2. 集成测试：`uv run --with pytest python -m pytest tests/integration/test_js.py -q`（实为 mock，无需 CDP）。
3. 修 9 个 Windows 用例：6 个 `os.killpg`（POSIX 专用）+ 2 个 `os.symlink`（需开发者模式）+ 1 个 SKILL.md 软链（`core.symlinks=false`）。加 `skipif(sys.platform == "win32")`，保留 Mac/Linux 覆盖 → 190/190。

## 2. macOS 接管

1. 环境：Python 3.12 + uv。
2. `./browser-harness --doctor`。
3. 远程调试批准：`./browser-harness mac-approve`（AppleScript 自动点 Allow；需 System Settings > Privacy & Security > Accessibility 授权）。
4. 冒烟：`./browser-harness` + `print(page_info())`，复用 Mac Chrome 的 cookie/会话。
5. 单元测试：`uv run --with pytest python -m pytest tests/unit -q` → 预期 Mac 上 190/190（killpg / symlink / 软链都可用）。
6. 集成测试：`tests/integration/test_js.py`。
7. Mac 专属：验证 `macos.py` 的 mac-approve 与真实 Chrome 连接。

## 3. 跨平台原则

- 测试修复只 `skipif(win32)`，不在 Mac/Linux 跳过。
- 核心验收：`page_info()` 必须返回用户已打开的标签页（证明会话复用）。

## 完成的定义

- Windows 单元测试 190/190。
- macOS 上 doctor + 冒烟 + 单元测试全绿。
