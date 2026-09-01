# M103 uv tool uninstall 删除 dangling 环境连带 shim 目录

> 环境错误。登记日 2026-09-01。关联 M102。

## 现象

`uv tool list` 报 `warning: Ignoring malformed tool bin (run uv tool uninstall bin to remove)`。执行 `uv tool uninstall bin` 后输出 `Removed dangling environment for bin`，随后 `browser-harness` 命令消失（command not found）：`D:\ohmyenv\uv-tools\bin\`（shim 目录，browser-harness.exe 所在地）被整体删除，venv 本体完好。

## 根因

历史安装事故把 shim 目录 `uv-tools\bin\` 注册成了名为 `bin` 的 tool 环境（uv 注册表按目录名对号）。`uv tool uninstall` 忠实执行：删注册项 = 删它"拥有"的目录 —— 而 uv 的警告文案只说 "malformed / to remove"，没有任何该目录承载其他工具 shim 的提示。[实证: 删后 bin\ 消失，重装 `uv tool install --force` 后 bin\ 重建]

## 正确处理

- 见到 `malformed tool` 警告**先查它指向的目录里有什么**（是否承载在用 shim），再决定删除；不要按 uv 提示盲删。
- 已中招恢复：外部 shell 停栈（M102 流程）→ `uv tool install --upgrade --force git+...@main`（重建 venv 与 shim）→ `x-monitor` 恢复栈。[实证: 2026-09-01 本机恢复]

## 教训

- 「清理残留」类操作动手前必须确认删除目标不承载在用资产；uv/包管理器的修复建议是提示，不是安全保证。
- 本条与 M102 同主题：**动 uv 工具层（装/卸/升级）前后都要验证 `browser-harness --version` 可用**，一条命令即可确认 CLI 链路完整。
