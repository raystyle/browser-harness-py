# ROADMAP

项目全局路线：**大里程碑**。状态：`未开始` / `进行中` / `已完成` / `排后`。细碎轨迹见 `docs/diary/`；方案详情见 `docs/proven/`。

## 阶段总览

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 0 | 基础设施：fork 分支维护 + 项目结构对齐 | 已完成 |
| 1 | 核心应用：X 监控 + 网页正文 + 搜索引擎 | 已完成 |
| 2 | 资源隔离：用户/agent 浏览器分离 + rmux 原子隔离 + 资源视图 | 已完成 |
| 3 | 打包与文档：uv tool install + 应用集成主包 + 文档体系对齐 | 已完成 |
| 4 | 站点专用提取（跨平台接管 2026-09-01 已收口；MCP 用户定向不做） | 排后 |

## 阶段 0：基础设施

个人 fork 远程（origin/mine）、`dev/work` 分支、三原语 + INDEX + docs 六目录。

## 阶段 1：核心应用

X 监控（rmux 自愈 supervisor + worker + 空闲门控刷新 + SQLite）、`web-fetch` 正文提取（defuddle + 站点选择器 + 反爬升级）、`google-search`/`bing-search`（搜索→正文 + 翻页）。

## 阶段 2：资源隔离

用户/agent 浏览器分离（独立 profile + BU_CDP_URL，S004）、应用 tab 精确域名绑定互斥、rmux label 原子隔离（kill-server）、`browsers`/`current` 资源视图。

## 阶段 3：打包与文档

`uv tool install git+...` 安装、应用集成进 `browser_harness` 主包、`AGENTS/GOAL/PLAN/TODO/ROADMAP` + `G002/G003` 对齐 ohmyagents。

## 阶段 4：扩展

站点专用提取规则扩充（domain-skills）。跨平台接管 2026-09-01 收口（S006/S007/R004/S008）；MCP 集成 2026-09-03 用户定向不做。
