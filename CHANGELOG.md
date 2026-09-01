# CHANGELOG

版本里程碑：本 fork 相对上游的本地改动记录。

## v0.2.2 — 2026-09-01

- 移除 `browser-harness telemetry` 及 `telemetry.py`，CLI 不再上报匿名事件。
- 更新来源从 PyPI 官方包改为本 fork GitHub `dev/work`；`--update` / doctor 不再连官方 PyPI。
- 清理 Browser Use Cloud 残余文档与 skill：`browser-use-cloud`、`profile-sync.md`、AGENTS/INDEX 同步修正。
- 修正 SKILL 中的启动命令、链接、rmux 路由与 Windows PowerShell 示例。

## v0.2.1 — 2026-09-01

- 移除 Browser Use Cloud 支持：`auth login/status/logout`、`start_remote_daemon`、`stop_remote_daemon`、`fetch-use` 依赖、`Remote Browsers` 全部下线；daemon 简化为纯本地（cdp/local）。
- 文档体系完整对齐 ohmyagents：AGENTS 四段职责、G002（六态）、G003（五步）、G004（经验沉淀分治）、三原语重写、R002 实证工作流。

## v0.2.0 — 2026-09-01

- X 监控：rmux 自愈 supervisor + worker，10 分钟空闲门控刷新，SQLite 去重存储。
- 网页正文提取：`web-fetch`（defuddle pydefuddle + 站点选择器 + 反爬自动升级）。
- 搜索引擎：`google-search` / `bing-search`（搜索 → 正文提取，支持翻页）。
- rmux：label 原子隔离、`kill-server`、服务/会话/窗格状态查看。
- 资源管理：用户/agent 浏览器分离、应用 tab 绑定互斥、`browsers` / `current` 状态视图。
- 打包：`uv tool install git+...` 安装，agent 应用集成进 `browser_harness` 主包。

## 2026-08-31

- 建立个人 fork 分支维护（origin/mine、dev/work）。
- 建立项目结构：三原语 + INDEX + ROADMAP + CHANGELOG + docs 六目录。
- 新增 URL 网页正文提取（defuddle 三层回退 + `extract_url_content` / `page_text.py`）。
