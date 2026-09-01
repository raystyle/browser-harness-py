# PLAN：当前目标实施计划

> 角色：**当前目标方案文档**——怎么做。分工：`TODO.md`=做到哪；本文件=怎么做；通用工作流见 `docs/guide/G003-*.md`。

## 当前目标：v0.2.0 封版（已完成）

> 对应 `GOAL.md`，登记日 2026-08-31，封版日 2026-09-01。

## 路线总览

| 阶段 | 范围 | 状态 |
| --- | --- | --- |
| 0 | 基础设施：fork 分支维护 + 项目结构对齐 | 已完成 |
| 1 | 核心应用：X 监控 + 网页正文 + 搜索引擎 | 已完成 |
| 2 | 资源隔离：用户/agent 浏览器分离 + rmux 原子隔离 + 资源视图 | 已完成 |
| 3 | 打包与文档：uv tool install + 应用集成主包 + 文档体系对齐 | 已完成 |

## 完成的定义

- 单元测试 `uv run --with pytest python -m pytest tests/unit -q` 通过（189 passed / 9 skipped）。
- `browser-harness --doctor` / `x-monitor` / `x-search` / `web-fetch` / `google-search` / `bing-search` / `browsers` / `current` / `rmux` 全部可用。
- 用户 Chrome 与 agent Chrome 分离、rmux label 原子隔离、应用 tab 绑定互斥均验证。
- 版本 v0.2.0 已 tag 并推 `mine/dev/work`。

## 下一目标

WSL2 无头接管（已完成，2026-09-01）。方案与过程见 `docs/research/S006-WSL2无头环境适配研究.md`：

1. 环境：WSL 内装原生 google-chrome-stable（.deb，非 snap）；launcher 行尾修 LF（`.gitattributes`）。
2. 代码：`BH_AGENT_CDP_PORT` 端口可配（mirrored 网络下 WSL 用 9224 避开 Windows 侧 9223）、`BH_CHROME_HEADLESS` 无头启动（无显示 Linux 自动无头）、`BH_CHROME_EXTRA_FLAGS` 透传、`browsers` 视图 Linux `/proc` 枚举（M104）。
3. 本机：`.browser-harness-dev/.env` 四键（BU_CDP_URL / BH_AGENT_CDP_PORT / BH_CHROME_HEADLESS / BH_AGENT_CHROME_PROFILE→ext4）。
4. 完成的定义：单测 207 全绿 ✓、`--doctor` 全绿 ✓、web-fetch 浏览器链路 ✓、管道自动化（goto_url/page_info）✓。
5. 遗留：WSL 侧 agent profile 登录 X 后 x-monitor 才可跑（待用户）；macOS 半仍排后。

再下一目标待用户定向。候选：WSL x-monitor 实跑、站点专用提取规则扩充（domain-skills）、MCP 集成。
