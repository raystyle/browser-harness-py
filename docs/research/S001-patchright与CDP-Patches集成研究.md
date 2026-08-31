# S001 patchright 与 CDP-Patches 集成研究

> 研究原型过程（为什么）。登记日 2026-08-31。
> 来源：`patchright` / `patchright-python` / `patchright-nodejs` / `CDP-Patches` 的 README 与 PyPI，以及 browser-harness 源码（`src\browser_harness\`）。

## 结论速览

- **patchright** = Playwright 的免检测 fork，只支持 Chromium/Chrome，Apache-2.0。Python 包叫 `patchright`，Node 包叫 `patchright-nodejs`，两者共用同一个 patched driver（`patchright install chromium|chrome` 下载）。
- **browser-harness** 是「薄 CDP 层」：用 `cdp-use` 附着到用户**真实 Chrome**（远程调试 / 本机 / Browser Use Cloud），agent 通过 `cdp(method, ...)` 原语写 helper。真实浏览器天然无 `navigator.webdriver`、指纹真实、登录态真实——这部分 stealth 优势已经具备。
- 源码确认 browser-harness 只发送极少的 CDP 方法，**不发送 `Runtime.enable` / `Console.enable`**（patchright 最大的两个补丁），因此这两处不适用。
- **POC 实证（Chrome Dev 154.0.8025.0，125% DPI）**：CDP `Input.dispatchMouseEvent` 与 OS 级 `WM_LBUTTONDOWN/UP` 两种方式下 `screenX != pageX`、`is_bot` 均为 false——输入域 page==screen 泄漏在 Chrome 142+ 已修复，本机同样不存在。
- **结论：不建议集成**。browser-harness 附着真实浏览器，patchright 解决的两大问题（Runtime.enable、command flags）本就不存在，输入域泄漏又被新版 Chrome 修掉了；OS 级输入「只能作用于活动标签页」的局限反而更差，不构成收益。

## 组件一览

| 组件 | 语言 | 许可证 | 作用 |
| --- | --- | --- | --- |
| `patchright`（driver） | 驱动 | Apache-2.0 | patched Playwright driver，补丁清单见其 README |
| `patchright-python` | Python | Apache-2.0 | Playwright Python 的 drop-in 替换，`patchright.sync_api` / `async_api` |
| `patchright-nodejs` | Node | Apache-2.0 | Playwright Node 的 drop-in 替换 |
| `cdp-patches` | Python | GPL | 修 CDP 输入域泄漏，用 OS 级事件分发点击/键盘/滚动 |

## browser-harness 现状（源码核实）

- 连接：`cdp_use.client.CDPClient`（依赖 `cdp-use==1.4.5`）；`BROWSER_KIND` = cloud / cdp / local。
- JS 求值：只用 `Runtime.evaluate`（`helpers.py`、`daemon.py`）；**不发送** `Runtime.enable` / `Console.enable` / `Page.enable` / `Network.enable`。完整 CDP 方法面：`Target.*`、`Page.navigate`、`Runtime.evaluate`、`DOM.*`、`Input.*`、`Browser.getVersion`、`Network.disable`（仅清理旧会话）。
- 输入：`Input.dispatchMouseEvent` / `Input.dispatchKeyEvent` / `Input.insertText`（`helpers.py` 的 `click_at_xy` / `type_text` / `press_key` / `scroll`）。
- 启动：`admin.py` `_launch_browser` 用 `start chrome` / `open -a` / 二进制直启，只加 `--profile-directory`，**不加** `--enable-automation` 等自动化旗标；远程调试靠 `chrome://inspect` 的「允许远程调试」开关，非启动旗标。因此 command-flag 泄漏对 browser-harness 不成立。

## 泄漏点映射

| 泄漏点 | patchright 的处理 | browser-harness 现状 | 是否适用 |
| --- | --- | --- | --- |
| `Runtime.enable` | 用 isolated ExecutionContext，不发 Runtime.enable | 不发送（只用 `Runtime.evaluate`） | 不适用 |
| `Console.enable` | 整体禁用 Console API | 不发送 | 不适用 |
| command flags（`--enable-automation` 等） | 改默认 args | 不注入自动化旗标 | 不适用（已干净） |
| `Input.dispatch*`（page==screen、无 CoalescedEvent） | 不处理（Playwright 本身用 CDP Input） | 用 CDP Input | 不适用（Chrome 142+ 已修复；实测 154 无泄漏） |
| Closed Shadow Root | 支持交互与 XPath | 未覆盖 | 可选移植 |

## POC 实证（2026-08-31）

探针 `examples\poc-os-input.py`（纯 ctypes，无 GPL 依赖）起一个临时 Chrome Dev 154.0.8025.0（125% DPI，临时 profile），在按钮点击事件里记录 `pageX/pageY/screenX/screenY`，用两种方式各点一次并对比：

| 输入方式 | pageX/pageY | screenX/screenY | `is_bot`（page==screen） |
| --- | --- | --- | --- |
| CDP `Input.dispatchMouseEvent` | 200 / 125 | 218 / 222 | **false**（无泄漏） |
| OS 级 `WM_LBUTTONDOWN/UP` | 200 / 125 | 218 / 222 | **false**（无泄漏） |

滚动：OS 级 `WM_MOUSEWHEEL` 使 `window.scrollY` 从 0 → 100，生效。

结论：本机 Chrome 上 CDP 输入域已正确产出 `screenX != pageX`，`cdp-patches` 要修的那个泄漏已被 Chrome 上游修复（crbug#1477537，Chrome 142+），因此无集成价值。

## 跨平台结论（Linux / macOS）

结论与 Windows 一致：**三处泄漏都不构成集成理由**，因为它们是 Chromium/协议层，而非 OS 层。

- `Runtime.enable` / `Console.enable` / command flags：browser-harness 的 `src\browser_harness\` 与启动逻辑三端共用，同样不发送 / 不注入自动化旗标。
- 输入域 page==screen 泄漏：crbug#1477537 的修复在 Chromium 主线（Chrome 142+），Windows / Linux / macOS 的 Chrome 同样受益。
- `cdp-patches` 平台现状：**macOS 不支持**（`__init__` 发 RuntimeWarning，`SyncInput` 直接 SystemError）；**Linux 用 Xlib/XTEST**（依赖 X11，Wayland 原生不可靠）；且包导入时自带 DeprecationWarning「no reason to use this package anymore」。

唯一例外：`cdp-patches` 自述仅对「原生 `<select>` 下拉」仍有价值（crbug#40943840，功能问题而非反检测），与 stealth 无关。

## 集成方案

### 方案 A：移植 stealth 补丁（推荐主集成）

保持薄 CDP 哲学与真实浏览器模型，只补两个点：

1. **输入走 OS 级**：点击/键盘/滚动改用 OS 级事件（`cdp-patches` 的 `SyncInput`/`AsyncInput`，或复用 `macos.py` 思路扩展到 Windows/Linux）。这是 browser-harness 最实际的 stealth 缺口。
2. **审计 `Runtime.enable` / `Console.enable`**：确认 `cdp-use` 未隐式发送；若发送则改 isolated context 求值。

优点：改动小、依赖轻、不破坏 agent 的 `cdp()` 原语与已有 domain-skills。

### 方案 B：patchright 作为可选「一次性隐身浏览器」后端（可选）

当用户要一个不碰真实浏览器、可丢弃的隐身浏览器（反爬场景）时，用 `patchright.chromium.launch_persistent_context(user_data_dir=..., channel="chrome", headless=False, no_viewport=True)`，或对已有浏览器 `connect_over_cdp()`。

优点：完整 Playwright API + patchright stealth；缺点：引入 Playwright 级重依赖与第二条代码路径。

### 方案 C：用 patchright 替换 `cdp-use`（不推荐）

会把 `cdp(method, ...)` 原语和 agent helper 模型整个换成 Playwright API，破坏现有 domain-skills，丢失薄层哲学。仅当彻底放弃 raw CDP 时才考虑。

## 运行时与依赖

- Python：`uv` + Python 3.12.14（与 ohmypwsh 接管一致；browser-harness `requires-python >=3.11`）。
- 安装（方案 B 时）：`uv add patchright`，再 `uv run patchright install chrome`（或 chromium）。
- Node（备用，本仓用不到）：fnm v24.20.0 + corepack + pnpm 11.24.0，若需 Node 版 patchright 走 `pnpm add patchright`。
- 镜像：uv/pip 走 aliyun、node 走 npmmirror（ohmypwsh 已配）；patchright 下载浏览器二进制可能需要镜像/代理，见「风险」。

## 许可证与风险

- `patchright`（driver + python + nodejs）Apache-2.0，与 browser-harness 的 MIT 兼容。
- `cdp-patches` 是 **GPL**，copyleft；作为 Python 依赖引入有许可证传播风险，需评估后决定是否内置或替换为自己实现的 OS 级输入。
- `cdp-patches` 的 Windows 实现只是「按 PID 找 `Chrome_RenderWidgetHostHWND` + `PostMessage` WM_LBUTTONDOWN/UP、WM_MOUSEWHEEL」，用 ctypes 自写约 50 行即可绕开 GPL（见 `examples\poc-os-input.py`）。
- patchright 只支持 Chromium；Console API 被禁用（功能取舍）；输入域泄漏在 Chrome v142+ 已修复（`cdp-patches` 自身 README 标注）。

## 下一步

1. ~~核实 `Runtime.enable` / `Console.enable`~~ 已确认不发送：`cdp-use` 的 `CDPClient.start()` 仅连 WebSocket，`send_raw` 只发目标方法，无自动 enable；browser-harness 源码也未见 `Runtime.enable` / `Console.enable`。
2. ~~原型验证输入域泄漏~~ POC 已实证：Chrome 154 上 CDP 输入与 OS 输入 `screenX != pageX`，泄漏已修复（`examples\poc-os-input.py`）。
3. 结论：**不建议集成 patchright / cdp-patches**。如未来确需「一次性隐身浏览器」再单独评估方案 B。
