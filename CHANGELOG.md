# CHANGELOG

版本里程碑：本 fork 相对上游的本地改动记录。

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
