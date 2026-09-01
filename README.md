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

### 2. 启动 agent 专属 Chrome + X 监控

```powershell
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

## Skill 安装部署

本仓库的 `SKILL.md` 是 agent 操作路由；`browser-harness skill` 会把安装包内的同一份 SKILL.md 输出到 stdout。先把 CLI 升级到本仓库最新版，再注册 skill：

```powershell
uv tool install --upgrade git+https://github.com/raystyle/browser-harness@dev/work
```

### Codex

```powershell
$skillDir = "$env:USERPROFILE\.codex\skills\browser-harness"
New-Item -ItemType Directory -Force $skillDir | Out-Null
browser-harness skill | Set-Content -LiteralPath "$skillDir\SKILL.md" -Encoding utf8
```

注册后 skill 名称为 `browser-harness`，触发器使用 SKILL frontmatter 里的 description：

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

### Claude Code / 其他 agent

本仓库同时提供 Claude plugin 结构：

- `.claude-plugin/plugin.json`：plugin 元数据。
- `.claude-plugin/marketplace.json`：marketplace 索引。
- `skills/browser-harness/`：skill 目录，其中 `references/install.md` 是 CLI 安装前置说明。

也可以用和 Codex 相同的方式手动注册：skill 名 `browser-harness`，skill body 由 `browser-harness skill` 生成，trigger 同上。

如果旧的用户级 `browser` 或 `browser-use` skill 抢占了同名意图，手动删除那个 stale skill 目录；不要改 bundled/vendor plugin cache。

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

## agent-workspace（agent 临时/运行目录）

`agent-workspace` 不是源码开发目录，而是 agent 运行时的**临时开发目录**。agent 只在这个目录里放自己的辅助函数、技能和数据，不改主包代码。

加载优先级：

1. `agent-workspace/agent_helpers.py`（存在时优先加载）。
2. 包内置 `browser_harness.agent_helpers`（没有 workspace 文件时回退）。

全局 `uv tool install` 后的默认位置：

```powershell
$ws = "$env:USERPROFILE\.config\browser-harness\agent-workspace"
New-Item -ItemType Directory -Force $ws | Out-Null
```

在该目录创建 `agent_helpers.py`：

```powershell
def summarize_current_page():
    info = page_info() or {}
    body = js("(document.body && document.body.innerText || '').slice(0, 3000)")
    return {"url": info.get("url"), "title": info.get("title"), "body": body}
```

然后直接调用：

```powershell
@'
print(summarize_current_page())
'@ | browser-harness
```

开发仓库 checkout 下同名目录 `D:\browser-harness\agent-workspace\` 也会被优先使用；如果要强制指向其他目录，设置 `BH_AGENT_WORKSPACE`。

站点技能放在 `agent-workspace/domain-skills/<host>/`，设置 `BH_DOMAIN_SKILLS=1` 后 `goto_url` 会把当前域名匹配到的技能文件一并返回。核心应用已经迁入主包：`web_fetch.py`、`x_search.py`、`x_worker.py`、`x_supervisor.py`。

## 部署细节与数据目录

开发仓库和全局 `uv tool install` 会使用不同位置：

| 内容 | 开发仓库 | 全局安装 |
| --- | --- | --- |
| 推文 DB / 心跳 / 日志 | `agent-workspace/`（`x_tweets.db` 等） | `~/.config/browser-harness/agent-workspace/` |
| agent 专属 Chrome profile | `agent-chrome-profile/` | `~/.config/browser-harness/agent-chrome-profile/` |
| daemon 配置 / 运行时 / 临时文件 | `.browser-harness-dev/`（仓库 launcher）；否则 `~/.config/browser-harness` | `~/.config/browser-harness/{runtime,tmp}/` |
| agent Chrome 调试端口 | `9223` | `9223` |

在 Windows 上 `~/.config/browser-harness` 实际为 `C:\Users\<user>\.config\browser-harness`（不走 `%APPDATA%`）。开发仓库的 `./browser-harness` launcher 会把 daemon 状态额外隔离到仓库内 `.browser-harness-dev/`，便于本地测试时不污染全局目录；如果直接使用 `uv run python -m browser_harness.run`，则 daemon 状态沿用 `~/.config/browser-harness`。

可用环境变量覆盖默认位置：

```powershell
$env:BH_HOME                 # browser-harness 根数据目录（全局）
$env:X_DB                    # 推文 SQLite 路径
$env:X_HEARTBEAT             # 心跳文件
$env:X_SUPERVISOR_LOG        # supervisor 日志
$env:BH_AGENT_WORKSPACE      # agent workspace 目录
$env:BH_AGENT_CHROME_PROFILE # agent Chrome profile
$env:BU_CDP_URL              # CDP http 地址
$env:BU_CDP_WS               # CDP websocket 地址
```

小版本升级（例如本机从 0.2.0 升到 0.2.1）：

```powershell
uv tool install --upgrade git+https://github.com/raystyle/browser-harness@dev/work
browser-harness --version
```

## 命令使用

### X 监控

```powershell
browser-harness x-monitor                    # 启动自愈监控（非阻塞）
browser-harness x-search --stats             # 统计已存推
browser-harness x-search --recent --limit 10 # 最近推
browser-harness x-search <关键词> --limit 10  # 关键词搜索
browser-harness x-search --since 1h --group-by hour
browser-harness rmux capture x-monitor       # 看 worker 输出
browser-harness rmux kill x-monitor          # 停 worker（supervisor 会自愈重拉）
```

### 网页正文提取

```powershell
browser-harness web-fetch <url>          # markdown
browser-harness web-fetch <url> --text   # 纯文本
browser-harness web-fetch <url> --json   # 完整元数据
browser-harness web-fetch --current      # 当前标签
```

### 搜索引擎搜索（搜索后自动接正文提取）

```powershell
browser-harness google-search <query>
browser-harness bing-search <query>
```

### rmux 会话管理

```powershell
browser-harness rmux list|new|ensure|send|keys|capture|kill|kill-server|version
```

`kill-server` 只销毁本项目 `browser-harness` label 的 daemon，不碰其他程序的 rmux 服务。

## 文档

- [AGENTS.md](AGENTS.md)：开发 / 交互 / 安全规范。
- [SKILL.md](SKILL.md)：agent 操作路由。
- [INDEX.md](INDEX.md)：项目唯一索引。
- `docs/proven/`、`docs/research/`、`docs/mistakes/`：方案、研究、错误沉淀。
