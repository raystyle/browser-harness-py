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

Linux/macOS 接管已整体收口（2026-09-01）：WSL 半（S006/S007）、Windows 复测（R004 路径 A）、macOS 半（R005 验收全过 + S008 钥匙串发现 + `chrome-mode` 双模落地）。三侧同构：专用 agent profile + 显式 `BH_CHROME_HEADLESS` + x-monitor 幂等拉起；macOS 差异两条——拉起必须走 LaunchServices（daemon 即是，勿手动直拉二进制）、登录录入走有头人工登录（S008）。

再下一目标待用户定向。候选：chrome-mode 翻转双拉起竞态观察（TODO 已挂）、agent Chrome 独立应用身份（macOS Dock 顶包）、站点专用提取规则扩充（domain-skills）；MCP 集成用户定向不做（2026-09-03 出队）。
