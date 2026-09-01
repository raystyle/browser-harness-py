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

待用户定向。候选：Linux/macOS 接管、站点专用提取规则扩充（domain-skills）、MCP 集成。
