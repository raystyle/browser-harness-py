# S002 rmux 集成研究

> 研究原型过程（为什么）。登记日 2026-08-31。
> 来源：`Helvesec/rmux`、`Helvesec/rmux-python`（PyPI `librmux`）README 与源码，本机 rmux 0.10.0 实测，`D:\ohmyagents\docs\research\S004-win-rmux既有rmux研究吸收.md`。

## 结论速览

- **rmux** 是通用 Rust 终端多路复用器（tmux 兼容），带 Rust / Python / TypeScript SDK。Python SDK 是 **`librmux`**（PyPI，0.6.1）。[实证: README/PyPI]
- **本机已装 rmux 0.10.0**：`C:\Users\ray\AppData\Local\rmux\bin\rmux.exe`，布局含分发器 / daemon / libexec 三层。[实证: rmux -V 与目录实测]
- **`librmux` 0.6.1 与本机 rmux 0.10.0 不兼容**：`start_server()` 在 Windows 是 no-op，默认 socket 名嵌进程级可变哈希，跨进程打不到同一 daemon。[实证: 实测 start-server no-op、list-sessions 连不上]
- **可行方案是直接驱动 `rmux` CLI**，并统一用 `-L <label>` 提供跨进程稳定的 socket。[实证: -L label 跨进程可见会话]

## 组件与检测

| 组件 | 说明 |
| --- | --- |
| `rmux`（CLI，0.10.0） | 已装；`rmux -V` = `rmux 0.10.0` |
| `librmux`（Python SDK，0.6.1） | PyPI 最新 0.6.1，目标 rmux 0.6.1，落后于本机 0.10.0 |

检测：`shutil.which("rmux")`，Windows 回退 `%LOCALAPPDATA%\rmux\bin\rmux.exe`；版本 `rmux -V`。

## 关键实测

### librmux 不兼容

```python
from librmux import RMUX
r = RMUX(check_compatibility=False)
r.start_server()            # rmux start-server → Windows 上不真正起 daemon
r.list_sessions()           # → "no server running" / "error connecting"
```

根因：Windows 下默认 socket 名形如 `\\.\pipe\rmux-<SID>-<label>-g-<hashA>-<hashB>`，`<hashB>` 每进程可变，跨进程连不上；正确启动方式是 `new-session -d`（而非 `start-server`）。

### CLI 可行（含跨进程）

```powershell
rmux -L bh new-session -d -s s1 cmd     # 起 daemon + 会话（daemon 会继承管道导致前台挂起）
rmux -L bh ls                            # 另一进程可见 s1 → -L 提供稳定 socket
rmux -L bh send-keys -t s1 "echo hi" Enter
rmux -L bh capture-pane -p -t s1
rmux -L bh kill-session -t s1
```

## 集成实现

`src\browser_harness\rmux.py`：

- `rmux_binary()` → `(path, version)` 或 `None`。
- `class Rmux`（SDK 形态，CLI 后端）：`list_sessions / has_session / new_session / ensure_session / send_keys / send_text / send_command / capture_pane / kill_session`。
- `new-session -d` 用 `subprocess.Popen` + `stdout/stderr=DEVNULL` + `ipc.spawn_kwargs()`（`CREATE_NO_WINDOW`），规避 daemon 继承管道导致的挂起。
- `_run` 用 `errors="replace"` 解码（本机中文 Windows 的 GBK 控制台输出），`capture_pane` 失败返回空串。
- 统一 `-L browser-harness` 标签，跨进程可达。

CLI：`browser-harness rmux list|new|ensure|send|keys|capture|kill|version`（见 `run.py`）。

## Windows 注意事项（吸收自 ohmyagents S004）

- 进程三层：`rmux.exe` 分发器、`rmux-daemon.exe`、`libexec\rmux\rmux.exe`；安装不能只拷一个 exe。
- 默认 shell 别依赖 `show-options`，spawn 时显式给 shell 命令（如 `cmd`）。
- `remain-on-exit` 默认 off：会话命令退即关 pane，长驻要 keep-alive。
- 中文输入走 paste-buffer UTF-8 更稳（`send-keys` 可能乱码/截断）。

## 后续

- 若需用官方 SDK，等 `librmux` 追到 0.10.x 后再切；当前 CLI 封装等价且更稳。
- 「多路复用浏览器脚本程序」= 用 `Rmux.new_session(name, command=...)` 各 pane 跑一个 `python -m browser_harness.run < script.py`，配合 `send_command` / `capture_pane` / `kill_session` 管理。
