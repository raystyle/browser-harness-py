# browser-harness（raystyle fork）

本仓库是 [browser-use/browser-harness](https://github.com/browser-use/browser-harness) 的个人 fork，用于本地开发与测试，个人分支推送到 [raystyle/browser-harness](https://github.com/raystyle/browser-harness)。

本 README 只讲**本项目的部署方法与命令使用**。开发/交互规范见 [AGENTS.md](AGENTS.md)，agent 操作路由见 [SKILL.md](SKILL.md)，方案与研究沉淀见 [INDEX.md](INDEX.md) 及 `docs/`。

## 环境要求

- **本项目当前 Windows 专用**（本机 Windows 11 实测；macOS / Linux 待接管，见 `ROADMAP.md` 阶段 4）。
- `uv` + Python 3.12。
- Chrome（本机 Chrome Dev 154 已验证）。
- rmux 0.10.0（X 监控的多路复用；安装见下）。

### rmux 安装（Windows）

从 Helvesec/rmux 下载 release zip 解压到 `%LOCALAPPDATA%\rmux`（`browser-harness` 会自动检测该目录，无需加 PATH）：

```powershell
$url = "https://github.com/Helvesec/rmux/releases/download/v0.10.0/rmux-0.10.0-windows-x86_64.zip"
$dest = "$env:LOCALAPPDATA\rmux"
Invoke-WebRequest $url -OutFile "$env:TEMP\rmux.zip"
Expand-Archive "$env:TEMP\rmux.zip" -DestinationPath $dest -Force
rmux -V   # → rmux 0.10.0
```

## 部署方法

### 1. 安装依赖

```powershell
uv sync
```

### 1b. 全局安装成命令行（可选）

```powershell
uv tool install git+https://github.com/raystyle/browser-harness@dev/work
browser-harness --version     # 验证
browser-harness --doctor      # 依赖/连接自检
```

安装后全局 `browser-harness` 命令可用；`pydefuddle`（网页正文提取）已作为核心依赖随包安装，无需额外 `[content]`。

### 2. 安装技能与插件，启动 agent 专属 Chrome + X 监控

```powershell
browser-harness skills sync     # 一次性：装技能到 Claude/Codex + 铺装插件与站点技能到 workspace
browser-harness x-monitor
```

该命令会：

- 启动**独立的 agent Chrome**（`agent-chrome-profile` + 端口 `9223` + anti-throttle flags），不影响你日常用的 Chrome（`Profile 3`）。
- 用 `BU_CDP_URL` 让监控 worker 只连这个独立 Chrome。
- 在 rmux 里以 `x-supervisor`（自愈监督）+ `x-monitor`（抓取 worker）两个会话后台运行。

首次使用需要在弹出的独立 Chrome 窗口里登录一次 X（登录写在独立 profile，不影响你的 Profile 3）。

### 3. 查看状态

```powershell
browser-harness --doctor          # Chrome / daemon / 连接状态
browser-harness rmux status       # 两个 rmux 会话是否存活
```

## Skill 与插件安装部署

本仓库的 `SKILL.md` 是 agent 操作路由。一条命令完成全部安装（技能进 Claude Code / Codex，插件与站点技能进 workspace）：

```powershell
uv tool install --upgrade git+https://github.com/raystyle/browser-harness@dev/work
browser-harness skills sync     # 状态查看；加 sync 参数执行安装/更新
```

`skills sync` 的三个落点：

| 目标 | 内容 |
| --- | --- |
| `~/.claude/skills/browser-harness/` | 技能包（SKILL.md + install.md + 17 个 interaction 专题） |
| `~/.codex/skills/browser-harness/` | 同上 |
| `~/.config/browser-harness/agent-workspace/{apps,domain-skills}/` | 插件脚本 + 站点技能（**增量覆盖，绝不删除**本地自加内容） |

注册后 skill 名称为 `browser-harness`，触发器是 SKILL frontmatter 里的 description：

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

本仓库同时提供 Claude plugin 结构（`.claude-plugin/` + `skills/browser-harness/`），供 marketplace 方式安装。如果旧的用户级 `browser` / `browser-use` skill 抢占了同名意图，手动删除那个 stale skill 目录；不要改 bundled/vendor plugin cache。

## 自由执行指定代码

`browser-harness` 不带子命令、且 stdin 不是终端时，会把 stdin 当作 Python 执行；核心 helper（`page_info`、`js`、`goto_url`、`list_tabs` 等）已经预导入，无需 `import`。

全局安装版：

```powershell
@'
print(page_info())
print(js("document.title"))
'@ | browser-harness
```

开发仓库内等价写法：

```powershell
@'
print(page_info())
print(setup_browser_apps())
'@ | uv run python -m browser_harness.run
```

上面的代码会经 daemon 连上当前绑定的 Chrome，并把结果打印到 stdout。脚本执行失败会以非 0 退出码返回，适合被 agent 或 CI 直接调用。

## agent-workspace（agent 运行目录 + 应用层）

`agent-workspace` 是 agent 运行时的**应用层**，恒位于 `<BH_HOME>`（默认 `~/.config/browser-harness/agent-workspace`，repo checkout 不再特殊化）。结构：

```text
agent-workspace/
├── agent_helpers.py   # 可选：函数合并层（包内置打底，本文件按函数名覆盖）
├── apps/              # 插件：browser-harness <app名> 即调用 apps/<app名>.py
└── domain-skills/     # 站点技能（BH_DOMAIN_SKILLS=1 时 goto_url 自动匹配）
```

`agent_helpers.py` 是**合并**加载：包内置版填充默认函数，workspace 版按函数名覆盖 —— 只在想自定义时创建它；不存在则永远用最新内置版。

```powershell
# 在 ~/.config/browser-harness/agent-workspace/agent_helpers.py 里写：
def summarize_current_page():
    info = page_info() or {}
    body = js("(document.body && document.body.innerText || '').slice(0, 3000)")
    return {"url": info.get("url"), "title": info.get("title"), "body": body}

# 然后任何管道脚本里直接调：
@'
print(summarize_current_page())
'@ | browser-harness
```

插件开发与测试规范见 [docs/references/R003-插件开发与测试规范.md](docs/references/R003-插件开发与测试规范.md)。

## 部署细节与数据目录

v0.2.3 起**所有运行时数据统一在 `<BH_HOME>`**（默认 `~/.config/browser-harness`，Windows 即 `C:\Users\<user>\.config\browser-harness`，不走 `%APPDATA%`）；repo checkout 只是源码：

| 内容 | 位置 |
| --- | --- |
| 推文 DB / 心跳 / 日志 / 插件 / 站点技能 | `<BH_HOME>/agent-workspace/` |
| agent 专属 Chrome profile | `<BH_HOME>/agent-chrome-profile/`（调试端口 `9223`） |
| daemon 配置 / 运行时 / 临时文件 | `<BH_HOME>/{.env,runtime/,tmp/}` |

默认 daemon 由 `<BH_HOME>/.env` 的 `BU_CDP_URL=http://127.0.0.1:9223` 永久钉在 agent Chrome 上 —— 用户日常浏览器（即使开了 chrome://inspect 调试开关）永远不会被连上。

可用环境变量覆盖默认位置：

```powershell
$env:BH_HOME                 # browser-harness 根数据目录（全局）
$env:BH_AGENT_WORKSPACE      # agent workspace 目录
$env:BH_AGENT_CHROME_PROFILE # agent Chrome profile
$env:BU_CDP_URL              # CDP http 地址（钉住浏览器）
$env:BU_CDP_WS               # CDP websocket 地址
$env:BU_NAME                 # daemon 名（每个长跑插件应有专属 daemon）
$env:X_DB / X_HEARTBEAT / X_SUPERVISOR_LOG   # x-monitor 插件的数据落点
```

升级（CLI 与插件一起更新）：

```powershell
browser-harness --update -y        # 或 uv tool install --upgrade git+...@dev/work
browser-harness skills sync        # 铺装新版插件与技能
```

## 命令使用

### 插件（workspace apps，`skills sync` 安装后可用）

```powershell
browser-harness x-monitor                    # 启动自愈 X 监控（非阻塞）
browser-harness x-search --stats             # 统计已存推
browser-harness x-search --recent --limit 10 # 最近推
browser-harness x-search <关键词> --limit 10  # 关键词搜索
browser-harness x-search --since 1h --group-by hour
browser-harness web-fetch <url>              # 网页正文提取（--text/--json/--current/--browser）
browser-harness google-search <query>        # Google 搜索（自动接正文提取）
browser-harness bing-search <query>          # Bing 搜索
```

未安装插件时命令会报 usage —— 先跑 `browser-harness skills sync`。

### rmux 会话管理（框架核心）

```powershell
browser-harness rmux list|status|new|ensure|send|keys|capture|kill|kill-server|version
browser-harness rmux capture x-supervisor   # 看 x-monitor 监督输出
browser-harness rmux kill x-monitor         # 停抓取 worker（supervisor 自愈重拉）
```

`kill-server` 只销毁本项目 `browser-harness` label 的 daemon，不碰其他程序的 rmux 服务。

## 插件开发

包是**薄核心**（daemon / helpers / rmux / 诊断 / skills），应用一律做成 `agent-workspace/apps/` 下的插件。开发、测试、发布规范见 [docs/references/R003-插件开发与测试规范.md](docs/references/R003-插件开发与测试规范.md)。

## 文档

- [AGENTS.md](AGENTS.md)：开发 / 交互 / 安全规范。
- [SKILL.md](SKILL.md)：agent 操作路由。
- [INDEX.md](INDEX.md)：项目唯一索引。
- `docs/proven/`、`docs/research/`、`docs/mistakes/`：方案、研究、错误沉淀。
