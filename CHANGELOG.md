# CHANGELOG

版本里程碑：本 fork 相对上游的本地改动记录。

## v0.4.1 — 2026-09-01

- **修复 about:blank 标签页泄漏**（实证：71 个空白 / 203 次 worker 重拉，1:1 对应）：根因是 worker 心跳只在轮末打一次，而 `HEARTBEAT_TIMEOUT=120s < INTERVAL=600s` —— 连健康 worker 也会在睡眠期被判死，supervisor 每 ~2 分钟杀掉重拉；每次重拉使 x-monitor daemon 随之重启，命名 daemon 的 `dedicated_target_id` 只存内存，冷启动即新开一个空白，旧空白永久孤儿。两层修复：
  - x-worker 睡眠改为分段心跳（`_sleep_with_heartbeat`，每 2 秒 tick），根治误杀循环；
  - 命名 daemon 冷启动先**复用孤儿空白**（`is_reusable_blank_page`）再创建，杜绝重启泄漏。
- 教训：升级/重装 CLI 前须先停 rmux 栈 —— 运行中的 worker/supervisor 锁住 venv `Scripts\`，导致 `uv tool install` 访问拒绝、shim 丢失（已实证）。

## v0.4.0 — 2026-09-01

- **插件化架构**：X（x-monitor/x-supervisor/x-worker/x-search）、web-fetch、google/bing-search 七个应用从包内抽离为 `agent-workspace/apps/` 插件；包收敛为薄核心（daemon/helpers/admin/rmux/browsers/skills/recordings）。命令入口 `browser-harness <app名>` 自动路由到 `apps/<app名>.py`（参数经 `APP_ARGS` 注入，支持直接 python 调试）。
- `agent_helpers.py` 改为**合并**加载（包内置打底、workspace 按函数名覆盖），消除"旧 workspace 副本整体遮蔽新版内置"的坑。
- agent Chrome 生命周期函数（`_launch_agent_chrome` 等）从 xapps 归入核心 `admin.py`，包内删除 xapps/x_worker/x_supervisor/x_search/web_fetch。
- `skills sync` 铺装面扩展：domain-skills + **apps**（均增量、绝不删除本地内容）。
- 新增《插件开发与测试规范》（docs/references/R003）；README 全面改写（插件使用、skills sync 三落点、数据目录统一 BH_HOME、升级流程）。
- 测试 195 passed：新增 apps 防漂移、包内无应用模块、合并加载、app 路由用例。

## v0.3.0 — 2026-09-01

- **skills sync 目标分治**：CLI 技能目录（claude/codex）只装技能包本体（SKILL.md + install.md + interaction，19 文件）；domain-skills（107 个站点配方，含 `claude-ai/extract-share-transcript.py` 脚本，此前被 `*.md` 打包规则漏掉）只增量铺到 `<BH_HOME>/agent-workspace/domain-skills/`，绝不删除用户自加内容。
- 打包规则补 `**/*.py`；`_skill_files` 哈希范围同步收窄，CLI 目录不再出现 107 个无关站点文件。

## v0.2.9 — 2026-09-01

- **domain skills 打包与铺装**：109 个站点配方（1.3MB）以 `references/domain-skills/` 随 wheel 分发；`browser-harness skills sync` 现在同步三类目标——`~/.claude` 技能目录、`~/.codex` 技能目录、`<BH_HOME>/agent-workspace/domain-skills/`（**增量覆盖、绝不删除**，保护用户自加站点技能）。新装机器不再有 domain skills 空缺。
- SKILL.md Domain Skills 章节补充 sync 说明；新增 domain-skills 防漂移测试（190 passed）。

## v0.2.8 — 2026-09-01

- **interaction-skills 十个占位专题全部充实**：uploads（DOM.setFileInputFiles）、cookies（读取/回写与浏览器态 vs 页面态）、iframes（同源穿越 + 帧坐标换算警告）、cross-origin-iframes（OOPIF 独立 target + `js(target_id=)`）、downloads（setDownloadBehavior + .crdownload 轮询）、drag-and-drop（插值鼠标拖拽 + HTML5 DnD DOM 事件两路）、dropdowns（先开后重读坐标 + 原生 select 直设）、network-requests（drain_events 差分 + getResponseBody + 网络空闲）、shadow-dom（合成器坐标穿透 + shadowRoot 递归）、print-as-pdf（printToPDF 参数与坑）。
- 关键声明实测验证：事件流、响应体读取、PDF 输出、cookies 读取均在 agent Chrome 上跑通；所有 helper 签名取自源码（`upload_file`/`iframe_target`/`drain_events`/`wait_for_network_idle`/`dispatch_key` 等）。

## v0.2.7 — 2026-09-01

- **X 栈独立 daemon**：x_monitor worker 改用 `BU_NAME=x-monitor` 专属 daemon（`x_worker` 导入前 setdefault + `x-monitor` 启动器同步设置），抓取轮次不再与随手 CLI 脚本争夺 default daemon 的标签页附着；两个 daemon 可同时附着同一 agent Chrome（实测共存）。
- SKILL.md 更新 daemon 共享说明（原"mid-script 附着可能被切走"的 gotcha 已消除）。

## v0.2.6 — 2026-09-01

- 修复 `x-search --author` 只匹配显示名列：传 handle（`Rainmaker1973` / `@Rainmaker1973`）返回 0 条；现同时匹配显示名与 handle。
- `x_search` usage 文本从 repo 时代的 `uv run python agent-workspace/x_search.py` 更新为 `browser-harness x-search`。
- SKILL 全面验收（两个 agent CLI 实际加载；SKILL 内文档的代码片段、flag、链接、幂等声明逐一实测）并补充 `--author` 语义与主模式要求说明。

## v0.2.5 — 2026-09-01

- 新增 `browser-harness skills [sync]`：把打包的技能（SKILL.md + references/）同步到 agent CLI 技能目录（`~/.claude/skills/browser-harness/`、`~/.codex/skills/browser-harness/`），支持状态查看与内容哈希比对。
- 技能打包完整化：17 个 interaction-skills 专题 + install.md 以 `references/` 形式随包分发；SKILL.md 的 Interaction Skills 章节改为优先指向本地 `references/interaction/`。
- 修复 `skills/browser-harness/SKILL.md` 与 plugin.json 版本过期（0.2.2）；新增防漂移测试覆盖包内副本、插件副本与 interaction 引用。

## v0.2.4 — 2026-09-01

- **默认 daemon 永久钉住 agent Chrome**：`<BH_HOME>/.env` 写入 `BU_CDP_URL=http://127.0.0.1:9223`。根因实证：用户 Chrome 的 chrome://inspect 调试开关（DevToolsActivePort=9222）会被 daemon 发现链优先命中（Chrome 147+ /json 404 时走 WS 绕行），导致默认 daemon 连上用户浏览器。
- `ensure_daemon`：BU_CDP_URL 钉住 9223 且 agent Chrome 未运行时自动拉起（仅此端点允许自动启动，绝不启动用户浏览器）。
- `browsers` 新增 `[inspect-toggle]` 段：列出标准 profile 目录的 DevToolsActivePort 及 TCP 探活结果，修复"命令行解析看不到 inspect 开关端口"的诊断盲区。
- 修复 `browser-harness skill` 打印 `../../SKILL.md` 占位符：包内 SKILL.md 改为真实内容并加防漂移测试；`--help` 的 rmux 行补 `status` / `kill-server`。
- SKILL.md 修订：连接模型（默认钉 9223）、workspace 恒在应用数据目录、X 区路径、inspect-toggle gotcha、wizard 脚本标注 repo-only。

## v0.2.3 — 2026-09-01

- 运行时数据默认全部收敛到应用数据目录（`BH_HOME`，默认 `~/.config/browser-harness`）：agent Chrome profile 不再优先落在 repo 的 `agent-chrome-profile/`（`xapps._agent_profile` 移除 repo 分支）；`AGENT_WORKSPACE` 不再优先用 repo 的 `agent-workspace/`（`helpers.py`）。
- `.env` 读取位置从 repo 根改为 `<BH_HOME>/.env` 与 `<BH_HOME>/agent-workspace/.env`（原 repo 根路径在 uv 安装环境下会解析到 site-packages 的无意义目录）。
- 既有 repo 内 profile/workspace 数据已迁移至应用数据目录（profile 保留 X 登录态）。
- X 抓取栈（`x_search` / `x_worker` / `x_supervisor`）的 `_data_dir()` 移除 repo 优先分支，统一落 `<BH_HOME>/agent-workspace`。
- 修复推文 `author` 字段污染：`User-Name` innerText 原样入库（"名字\n@handle\n·\n相对时间"），现只存显示名，`handle` 由 JS 单独提取；存量 696 行已回填清洗。

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
