# R006：dev 环境平台分家与端口分配

> 状态：reference（2026-09-03 实证沉淀）。对应 TODO「dev 环境 Windows 侧真栈姿势」。
> 解决的问题：一个 repo checkout 被 Windows 与 WSL 两平台共用时，`<BH_HOME>/.env` 只有一份，WSL 侧写入的配置（9224 + `/home` profile 路径）让 Windows 侧 stdin/daemon 真栈实测连续两日受阻（M109、Issue #2 期间两次被迫把真栈验证挂到发版自验）。

## 方案：launcher 按平台分 BH_HOME

`browser-harness`（repo 开发 launcher）按 `uname -s` 分目录：

| 平台 | BH_HOME | 端口 | profile |
| --- | --- | --- | --- |
| Windows（MINGW/MSYS/CYGWIN） | `<repo>/.browser-harness-dev-win` | **9225** | BH_HOME 内全新 profile |
| WSL / Linux / macOS | `<repo>/.browser-harness-dev`（原有目录，存量数据不动） | 9224（WSL，mirrored 网络避撞 Windows 9223） | `/home/<user>/...`（ext4，避 DrvFS） |

端口分配全景：**9223 = 装机栈**（Windows 侧 installed CLI 的 agent Chrome）、**9224 = WSL 侧**、**9225 = Windows 侧 dev checkout**。三者可同时存活，`browser-harness browsers` 会并列显示多个 `[agent]` 实例（各持各的 profile/端口）。

要点：

- 各平台 `.env` 落在各自 BH_HOME 根（`.browser-harness-dev-win/.env` 写 9225 + `BH_CHROME_HEADLESS=1`；WSL 配置留在原目录原文件）。
- 显式 `BH_HOME` 环境变量仍然最高优先（launcher 用 `${BH_HOME:-...}` 默认值语义，不覆盖用户显式指定）。
- runtime/tmp 隔离沿用 launcher 原有逻辑（`/tmp/bh-dev-<id>/runtime`），与 BH_HOME 分家叠加后，dev daemon 与装机 daemon 的 IPC 天然不串。
- `.gitignore` 放宽为 `.browser-harness-dev*/`。
- 单测隔离另行根治（`tests/conftest.py` 强制 BH_HOME 指测试 scratch 目录，v0.6.8 随版）——测试面与 dev 面是两件事，勿混。
- 一次性/批量测试任务用 `./browser-harness --once ...`（或 `--batch`）：调用结束自动拆掉自己冷启动的栈（daemon + agent Chrome），不再留残余浏览器；已在跑的装机栈不受影响。

## 验证

[实证: 2026-09-03 Windows 发版机] `./browser-harness` stdin：BH_HOME 落 `.browser-harness-dev-win`、workspace 直落新默认 `browser-workspace`、daemon 冷启动 + 无头 Chrome 9225 拉起 + `goto_url`/`page_info` 真导航全过；装机栈（9223，agent-chrome-profile 原址）不受扰，installed CLI 0.6.8 正常。

## 边界

- macOS 侧 dev checkout 在 lan-mac，是另一份 clone（自带 BH_HOME 语义），本方案主要服务 Windows/WSL 共 checkout 场景；macOS 若也共 checkout，同型分目录即可。
- dev-win 的 profile 是全新 profile（无登录态）；需要登录态的 dev 测试用 `cookies` 插件导入，或临时把 `BH_AGENT_CHROME_PROFILE` 指到装机 profile（勿长期共用）。
