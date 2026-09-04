# browser-harness

本仓库是独立维护的主仓库 [raystyle/browser-harness](https://github.com/raystyle/browser-harness)。项目源自 [browser-use/browser-harness](https://github.com/browser-use/browser-harness) 的 v0.1.10 基线，此后架构独立演化——插件化应用层（apps/）、agent 专属浏览器隔离、本地 X 监控、skills 分发链等均为本项目特性；感谢上游的初始设计。

本 README 只讲**本项目的部署方法与命令使用**。开发/交互规范见 [AGENTS.md](AGENTS.md)，agent 操作路由见 [SKILL.md](SKILL.md)，方案与研究沉淀见 [INDEX.md](INDEX.md) 及 `docs/`。

## 环境要求

- **三平台实测**：Windows 11 / WSL2·Linux（S006）/ macOS（S008）；无头/有头双模均可（见下文「无头/有头双模」）。
- `uv` + Python 3.12。
- Chrome（Windows Chrome Dev 154 / Linux google-chrome-stable 152 / macOS Chrome 均已验证）。
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

非 Windows 平台从 [Helvesec/rmux releases](https://github.com/Helvesec/rmux/releases) 取对应包放入 PATH 即可（macOS 已实测 0.10.0）。

## 部署方法

### 1. 安装命令行

```powershell
uv tool install git+https://github.com/raystyle/browser-harness
browser-harness --version     # 验证
browser-harness --doctor      # 依赖/连接自检
```

一条命令完成安装：全局 `browser-harness` 可用，全部依赖（含 `pydefuddle` 网页正文提取）随包自带 —— 不需要 `uv sync`、不需要 clone 源码、不需要额外 extras。源码开发运行方式见下文「二次开发」。

### 2. 安装技能与插件，启动 agent 专属 Chrome + X 监控

```powershell
browser-harness skills sync     # 一次性：装技能到 Claude/Codex + 铺装插件与站点技能到 workspace
browser-harness x-monitor
```

该命令会：

- 启动**独立的 agent Chrome**（`agent-chrome-profile` + 端口 `9223` + anti-throttle flags），不影响你日常用的 Chrome（`Profile 3`）。
- 用 `BU_CDP_URL` 让监控 worker 只连这个独立 Chrome。
- 在 rmux 里以 `x-supervisor`（自愈监督）+ `x-monitor`（抓取 worker）两个会话后台运行。

首次使用需要在弹出的独立 Chrome 窗口里登录一次 X（登录写在独立 profile，不影响你的 Profile 3）。无头值守场景的登录录入标准姿势见下节 chrome-mode。

### 3. 查看状态

```powershell
browser-harness --doctor          # Chrome / daemon / 连接状态
browser-harness rmux status       # 两个 rmux 会话是否存活
```

### 4. 无头/有头双模（chrome-mode）

agent Chrome 支持无头/有头双模，`<BH_HOME>/.env` 是唯一事实源（`BH_CHROME_HEADLESS=1` 无头值守、`=0` 保窗）；翻转自动完成改写 `.env` + 按 pid 精确停 agent Chrome（绝不误伤你日常的 Chrome）+ 双 daemon 重启 + x-monitor 幂等恢复：

```powershell
browser-harness chrome-mode status     # 当前模式 + agent Chrome 是否在跑
browser-harness chrome-mode headed     # 翻有头：登录/录入用
browser-harness chrome-mode headless   # 翻无头：值守用
```

- **登录录入标准姿势**：`headed` 人工登录一次 → `headless` 翻回值守（S008：macOS 上 CDP 注入的 cookie 不跨重启存活，人工登录落钥匙串才持久；Linux/Windows 无此差异）。
- **跨设备免重登**（S007 cookies 插件）：`browser-harness cookies export --domain x.com` 导出（默认拒绝全量导，文件 0600）→ 拷到目标机 → `browser-harness cookies import --file <f.json>`。
- Linux 无 `DISPLAY`/`WAYLAND_DISPLAY` 时自动无头；WSL mirrored 网络可用 `BH_AGENT_CDP_PORT=9224` 避开 Windows 侧端口；`BH_CHROME_EXTRA_FLAGS` 透传任意启动 flag。

## 更新升级

日常升级一条命令（CLI、技能、workspace 插件一起到最新）：

```powershell
browser-harness --update -y
```

它自动完成四步，无需人工干预：

| 步骤 | 做什么 |
| --- | --- |
| 1 停栈 | `rmux kill-server` + 停 default/x-monitor 两个 daemon（解除 Windows venv 文件锁） |
| 2 升级 | `uv tool install --force`（默认分支即 main，单 venv 原地替换，不累积旧版本） |
| 3 铺装 | `skills sync`：Claude/Codex 技能 + workspace apps/domain-skills（增量；并清扫本项目退役的旧文件名，自加内容永不删除） |
| 4 恢复 | 升级前 x-monitor 在跑则自动重拉；尾部输出落地版本 |

- **Windows 细节**：升级命令自身跑在 venv 里无法原地替换自己，实际安装由脱离 venv 的 pwsh 接力进程在本命令退出后执行（同控制台可见输出）。
- **版本相同也会铺装**：`--update` 在 up-to-date 时仍执行第 3 步，修复"版本没变但 workspace 漂移"的机器。
- **手动路线**（备选）：`uv tool install --force git+https://github.com/raystyle/browser-harness` —— `--force` 单独即可升级（git 源每次解析到默认分支头）；前置要求先停栈（rmux + daemon，见 M102），且需另跑 `skills sync`。
- **动过 uv 工具层（装/卸/升级）前后**各跑一次 `browser-harness --version` 确认链路完整（M103：清理 uv 注册残留曾连带删掉 shim 目录）。

升级后验证：`browser-harness --version`（新版本号）+ `--doctor` 全绿 + `rmux list` 两会话。

## Skill 与插件安装部署

本仓库的 `SKILL.md` 是 agent 操作路由。升级与铺装一条命令见上节「更新升级」；单独查看/重铺用 `browser-harness skills sync`（不带参数只看状态）。

`skills sync` 的三个落点：

| 目标 | 内容 |
| --- | --- |
| `~/.claude/skills/browser-harness/` | 技能包（SKILL.md + install.md + 17 个 interaction 专题） |
| `~/.codex/skills/browser-harness/` | 同上 |
| `~/.config/browser-harness/browser-workspace/{apps,domain-skills}/` | 插件脚本 + 站点技能（**增量覆盖，绝不删除**本地自加内容） |

注册后 skill 名称为 `browser-harness`，触发器是 SKILL frontmatter 里的 description：

```text
Always use browser-harness for any web interaction: automation, scraping, testing, or site/app work.
```

本仓库同时提供 Claude plugin 结构（`.claude-plugin/` + `skills/browser-harness/`），供 marketplace 方式安装。如果旧的用户级 `browser` / `browser-use` skill 抢占了同名意图，手动删除那个 stale skill 目录；不要改 bundled/vendor plugin cache。

## 自由执行指定代码

`browser-harness` 不带子命令、且 stdin 不是终端时，会把 stdin 当作 Python 执行；核心 helper（`page_info`、`js`、`goto_url`、`list_tabs` 等）已经预导入，无需 `import`。

任务生命周期三分类（任意调用可加前缀旗标）：**持久**（默认）——daemon/Chrome 常驻，闲置 `BH_IDLE_TIMEOUT` 后自退（见环境变量表）；**批量** `--batch` / **一次性** `--once`——**默认运行在独立浏览器栈上**（专属 daemon 名 + 9230+ 端口 + 基础登录 profile 克隆，结束时整套拆除：CDP 优雅关闭 + profile 删除），任务间互不共浏览器、可真并行；加 `--shared` 或已钉栈（.env 设 `BU_NAME`/`BU_CDP_URL`）则退回共享栈（只拆自己冷启动的部分）。已在跑的栈（持久任务/监控）永不被动。

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

## browser-workspace（运行目录 + 应用层）

`browser-workspace` 是运行时的**应用层**，恒位于 `<BH_HOME>`（默认 `~/.config/browser-harness/browser-workspace`，repo checkout 不再特殊化）。结构：

```text
browser-workspace/
├── browser_helpers.py   # 可选：函数合并层（包内置打底，本文件按函数名覆盖）
├── apps/              # 插件：browser-harness <app名> 即调用 apps/<app名>.py
└── domain-skills/     # 站点技能（BH_DOMAIN_SKILLS=1 时 goto_url 自动匹配）
```

`browser_helpers.py` 是**合并**加载：包内置版填充默认函数，workspace 版按函数名覆盖 —— 只在想自定义时创建它；不存在则永远用最新内置版。

```powershell
# 在 ~/.config/browser-harness/browser-workspace/browser_helpers.py 里写：
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

## 完整结构与数据目录

### 1. 仓库结构（D:\browser-harness\，git 源）

```text
browser-harness/
├── src/browser_harness/          # ★ 包源（与 wheel 内容 1:1，见下节）
├── browser-workspace/              # ★ 应用层【源】（git 跟踪；运行时副本在 BH_HOME）
│   ├── apps/                     #   8 个插件源：x-monitor / x-supervisor / x-worker /
│   │                             #   x-search / web-fetch / google-search / bing-search / cookies
│   └── domain-skills/            #   97 个站点配方源（x/、github/、amazon/…106 md + 1 py）
├── interaction-skills/           # ★ 17 个浏览器操作专题源（uploads/cookies/iframes/…）
├── skills/browser-harness/       # Claude plugin 结构（SKILL.md + references/）
├── .claude-plugin/               #   plugin.json + marketplace.json
├── SKILL.md                      # ★ 技能正文权威源（≈18KB；包内副本由测试守护同步）
├── install.md                    # 一次性安装指引（随包分发为 references/install.md）
├── tests/unit/                   # 275 个测试：daemon/helpers/admin/rmux/run/js/recorder/
│                                 #   skills 防漂移 / 插件合并加载 / app 路由…
├── docs/                         # 文档体系（ohmyagents 规范）
│   ├── guide/                    #   G001-G004：文档/研究/工作流/经验沉淀细则
│   ├── research/                 #   S001-S008：rmux、defuddle、浏览器隔离、无头接管、钥匙串…
│   ├── proven/                   #   P0001-P0002：已实证方案
│   ├── mistakes/                 #   M101-M110：profile 污染、升级锁、symlink、CRLF、限流误报、单实例竞态、Windows 无 SIGKILL…
│   ├── references/               #   R001-R005：R003=插件开发与测试规范
│   └── diary/ · assets/          #   日记与截图
├── AGENTS.md / INDEX.md / GOAL.md / PLAN.md / ROADMAP.md / TODO.md / CHANGELOG.md
├── mcp_server.py                 # 可选 MCP 封装
├── browser-harness               # repo 内开发用 launcher（uv run 包装）
└── pyproject.toml / uv.lock      # 版本、依赖、package-data（references 三类）
```

### 2. pip 包结构（wheel = src/browser_harness/）

```text
browser_harness/                  # 薄核心：框架，不含任何应用逻辑
├── run.py            # CLI 入口：子命令分发；管道执行；插件路由（注入 APP_ARGS/APP_FILE）
├── daemon.py         # CDP WS 持有 + IPC 中继（TCP loopback；每 BU_NAME 一个 daemon）
├── helpers.py        # 预导入助手（page_info/js/cdp/click_at_xy/scroll/wait_*）
│                     #   + browser_helpers 合并加载（包内置打底、workspace 按函数覆盖）
├── admin.py          # ensure_daemon 自愈（agent Chrome 冷启动自动拉起）+ Chrome 生命周期
│                     #   + doctor / --update / .env 加载（<BH_HOME>/.env 优先）
├── _ipc.py           # IPC 帧协议 + 端口/pid/日志路径（TCP token 防护）
├── paths.py          # BH_HOME 路径体系（BH_HOME/BH_CONFIG_DIR/BH_RUNTIME_DIR/BH_TMP_DIR…）
├── browsers.py       # browsers / current 资源视图 + [inspect-toggle] 盲区探测
├── rmux.py           # rmux 会话管理（label 原子隔离、kill-server）——框架核心
├── skills.py         # skills [sync]：三落位分发器 + 内容哈希比对
├── recorder.py / video.py / video_render.py / video-template.html   # 录制与视频导出
├── browser_helpers.py  # 内置应用函数：google/bing_search、extract_*_content、setup_browser_apps
├── macos.py          # macOS 远程调试权限批准
├── SKILL.md          # 技能正文（test_skill_packaged 守护 == repo 根）
└── references/       # ★ 分发母本（只读）
    ├── install.md                #   安装指引
    ├── interaction/   (17 文件)  #   操作专题（与 interaction-skills/ 同步守护）
    ├── apps/          (8 文件)   #   插件母本（与 browser-workspace/apps/ 同步守护）
    └── domain-skills/ (107 文件) #   站点配方母本（同上；106 md + 1 py）
```

### 3. 部署后的磁盘结构（三线落位）

**A. 包本体**（uv tool 安装，只读）

```text
D:\ohmyenv\uv-tools\browser-harness\
├── browser-harness.exe                     # 全局命令
└── Lib\site-packages\browser_harness\      # 与上节 wheel 1:1
```

**B. 运行时数据**（`BH_HOME` = `C:\Users\<user>\.config\browser-harness\`）

```text
BH_HOME/
├── .env                    # ★ BU_CDP_URL=http://127.0.0.1:9223 —— 默认 daemon 永久钉住
│                           #   agent Chrome；用户浏览器即使开了 inspect 开关也不会被连
│                           #   （BH_CHROME_HEADLESS 等 chrome-mode 管理的键也在此——
│                           #   勿手改，用 browser-harness chrome-mode 翻转）
├── agent-chrome-profile/   # agent 专属 Chrome user-data-dir（X 登录态；调试端口 9223）
├── runtime/                # 每 daemon 一对：bu-default.pid/.port、bu-x-monitor.pid/.port
├── tmp/                    # bu-*.log（daemon 日志）、shot.png、调试截图/PDF
└── browser-workspace/        # ★ 应用层（活数据；skills sync 只增不删）
    ├── apps/               #   8 个插件运行时（browser-harness <app名> 即执行）
    │   ├── x-monitor.py        # 启动器：拉起 Chrome + 钉 env + rmux ensure（非阻塞）
    │   ├── x-supervisor.py     # 自愈监督：心跳检查 + 异常重拉 worker（会话 x-supervisor）
    │   ├── x-worker.py         # 抓取 worker：空闲门控刷新时间线 → x_tweets.db（BU_NAME=x-monitor）
    │   ├── x-search.py         # 推文库查询（--stats/--recent/--since/--author/--csv…）
    │   ├── web-fetch.py        # defuddle 正文提取（--text/--json/--current/--browser）
    │   ├── cookies.py          # 会话 cookie 跨设备导出/导入（S007；默认拒全量导、0600 落盘）
    │   └── google-search.py / bing-search.py   # 搜索 → 自动接正文提取
    ├── domain-skills/      #   97 站点配方运行时（BH_DOMAIN_SKILLS=1 时 goto_url 自动匹配）
    ├── x_tweets.db (+wal/shm)  # 推文库（WAL；author=显示名，handle 单列）
    ├── x_worker.heartbeat      # worker 心跳（supervisor 判活依据）
    └── x_supervisor{,.stderr,.stdout}.log      # 监督日志
    （browser_helpers.py 按需创建：想自定义时才建，缺省用包内置最新版）
```

**C. Agent CLI 技能**（`skills sync` 产物，各 19 文件）

```text
~\.claude\skills\browser-harness\     ~\.codex\skills\browser-harness\
└── SKILL.md + references\{install.md, interaction\*.md}
    # apps 与 domain-skills 故意不进技能目录 —— 它们属于 workspace
```

### 4. 数据流与防漂移

```text
repo 源（git）                wheel references 母本           部署落位
──────────────  ──拷贝/发布──▶  ──────────────────  ──sync──▶  ─────────────────
SKILL.md                       browser_harness/SKILL.md        C 线技能目录（19 文件）
interaction-skills/    →       references/interaction/    →    （并入技能包）
browser-workspace/apps/  →       references/apps/           →    B 线 apps/（8 插件）
browser-workspace/domain-skills/ → references/domain-skills/  →  B 线 domain-skills/
        └── tests/unit/test_skill_packaged.py 逐对守护，漂移即红
```

### 5. 运行时拓扑

```text
browser-harness <命令/脚本/插件>
   ├─ default daemon ──┐
   ├─ x-monitor daemon ─┴─▶ agent Chrome（9223，BH_HOME/.env 钉住）
   │                        └─ 持有 X 登录态的 profile
   └─ rmux 会话：x-supervisor（监督）→ x-monitor（worker 抓取）
日常 Chrome（Profile 3）：无调试端口或 inspect 开关 —— 无论哪种都永不被连
```

可用环境变量覆盖默认位置：

```powershell
$env:BH_HOME                 # 根数据目录（全局）
$env:BH_BROWSER_WORKSPACE      # workspace 目录（默认 <BH_HOME>/browser-workspace；旧名 BH_AGENT_WORKSPACE 兼容，v0.6.8 前旧目录自动改名迁移）
$env:BH_AGENT_CHROME_PROFILE # agent Chrome profile
$env:BH_AGENT_CDP_PORT       # agent Chrome 调试端口（默认 9223；WSL mirrored 网络建议 9224）
$env:BH_CHROME_HEADLESS      # 1=强制无头 0=保窗；不设时无 DISPLAY 的 Linux 自动无头（chrome-mode 管理的键）
$env:BH_CHROME_EXTRA_FLAGS   # 透传给 agent Chrome 的额外启动 flag
$env:BH_IDLE_TIMEOUT         # 持久任务闲置超时秒数（默认 1800=30 分钟，0 关闭）：daemon 无请求超时自退，最后一个 daemon 连带关 agent Chrome（x-monitor 轮询自动续活）
$env:BH_LOCK_GRACE           # daemon 单实例锁等待宽限秒数（默认 90，须大于启动最坏 ~75s；超时退出并报 holder pid）
$env:BH_IPC_TIMEOUT          # 普通 CDP 往返响应超时秒数（默认 5）
$env:BH_NAVIGATE_TIMEOUT     # goto_url/new_tab 的 Page.navigate 响应超时秒数（默认 30；超时只做死锁兜底——响应丢失由事件流判成功/失败，静默到点=未知，Issue #3）
$env:BH_SCREENSHOT_TIMEOUT   # 截图响应超时秒数（默认 60）
$env:BU_CDP_URL              # CDP http 地址（钉住浏览器）
$env:BU_CDP_WS               # CDP websocket 地址
$env:BU_NAME                 # daemon 名（每个长跑插件应有专属 daemon）
$env:X_DB / X_HEARTBEAT / X_SUPERVISOR_LOG   # x-monitor 插件的数据落点
```

升级（CLI 与插件一起更新，一条命令闭环）：

```powershell
browser-harness --update -y        # 停栈 → 升级 → 铺装插件/技能 → 恢复 x-monitor
browser-harness skills sync        # 独立铺装（--update 已内置，单独重铺时用）
```

手动 `uv tool install` 前需先停运行栈（rmux + daemon，见 M102）；`--update` 自 v0.6.0 起自动处理。

## 技能路由链（安装的 SKILL → domain-skills 加载）

从 Claude Code / Codex 装载的 SKILL.md 到真正读取站点配方，是一条"文档指路 + 运行时提示"的双通道链路：

```text
① 技能触发                 ② SKILL.md 文本指路                ③ agent 解析路径              ④ 读取执行
─────────                ─────────────────                 ──────────────               ──────────
任务涉及网页               三处接力指令：                      $BH_BROWSER_WORKSPACE          通读该目录全部 .md
→ frontmatter            · 开头强制令：BH_DOMAIN_SKILLS=1    的解析规则写在 Workspace      → 按 "Do this first"
  description 命中          时先读 domain-skills/<dir>/      章节：<BH_HOME>/browser-     工作流动手
→ SKILL.md 全文注入       · Workspace 章节：$BH_BROWSER_     workspace（BH_HOME 默认
  上下文                    WORKSPACE = <BH_HOME>/browser-   ~/.config/browser-harness）
· 底部 Domain Skills        workspace                       → agent 拼出绝对路径
  章节：<dir> 命名规则 +     （BH_BROWSER_WORKSPACE 环境变量
  goto_url 动态提示          可覆盖）
```

关键事实：

- **`$BH_BROWSER_WORKSPACE` 不是变量插值，是 agent 读文档自己拼的**；技能副本里故意不含 domain-skills 实体（只有路由说明），实体永远在 workspace。
- **目录命名 = hostname 去掉 `www.` 后的首标签**：`github.com` → `github/`，`www.bing.com` → `bing/`；**子域名自成一站** —— `maps.google.com` → `maps/`（不是 `google/`），所以 `gmail` 是独立目录。
- **动态通道**：设 `BH_DOMAIN_SKILLS=1` 后 `goto_url()` 返回值带 `domain_skills: [文件名…最多10个 .md]`；配套 `.py` 脚本不在提示里，需列目录发现。
- **默认关闭**：未设 `BH_DOMAIN_SKILLS=1` 时 SKILL 明令 "ignore domain skills"；该变量只硬控 goto_url 提示，"读文件"靠指令约束 agent 行为。

## 命令使用

以下示例的输出均为 v0.4.0 实机验收时截取（非虚构）。

### 诊断与状态（核心）

```powershell
PS> browser-harness doctor
  platform          Windows 11
  version           0.4.0 (installed)
  latest release    0.4.0
  [ok  ] chrome running
  [ok  ] daemon alive
  [ok  ] active browser connections — 2      # default + x-monitor 双 daemon
        default — active page: 🐴 … / X
        x-monitor — active page: 🐴 主页 / X — https://x.com/home
  [ok  ] rmux — rmux 0.10.0

PS> browser-harness browsers                  # 实例/标签页/[inspect-toggle] 盲区探测
PS> browser-harness current                   # daemon 当前附着目标
PS> browser-harness doctor --json             # 机器可读（healthy/version/browser_ready）
```

### 插件（workspace apps，`skills sync` 安装后可用）

```powershell
# X 监控：启动（幂等，非阻塞）
PS> browser-harness x-monitor
x-monitor running (isolated Chrome on 9223, rmux session 'x-supervisor')

# 推文库统计
PS> browser-harness x-search --stats
total_tweets: 798
distinct_authors: 498
posted_range: 2026-08-02T12:43:14.000Z -> 2026-09-01T05:31:01.000Z

# 关键词搜索（author=显示名，handle 独立成列）
PS> browser-harness x-search Kubernetes --limit 1
author: Darryl Ruggles | @RDarrylR | posted: 2026-09-01T05:30:13.000Z
text: Kubernetes pods run 24/7 but many APIs sit idle most of the time...

# 最近抓取 / 时间窗 / 按作者过滤（--author 匹配显示名或 @handle，需搭配主模式）
PS> browser-harness x-search --recent --limit 5
PS> browser-harness x-search --since 1h --group-by hour
PS> browser-harness x-search --recent --author Rainmaker --limit 2
author: Massimo | @Rainmaker1973 | posted: 2026-09-01T04:00:00.000Z

# 网页正文提取（默认 markdown；另有 --text / --json / --current / --browser）
PS> browser-harness web-fetch https://example.com
# Example Domain
This domain is for use in documentation examples...

# 搜索引擎（跑在已登录的 agent Chrome，前 3 条自动接正文提取）
PS> browser-harness google-search "rust tokio"
[1] Tokio - An asynchronous Rust runtime
PS> browser-harness bing-search "python asyncio"
[1] asyncio — Asynchronous I/O — Python 3.14.7 documentation
```

未安装插件时命令报 usage —— 先跑 `browser-harness skills sync`。

### 管道脚本（核心能力：Python 直驱浏览器）

```powershell
PS> @'
info = page_info()                     # {'url': …, 'title': 🐴 …, 'w': 506, 'h': 106}
t = new_tab("https://example.com")     # 新标签 + 附着（马标记🐴，不切换可见页）
wait_for_load()
print(js("document.title"))            # 🐴 Example Domain
c = extract_page_content(markdown=True)# defuddle 提取：17 words | engine: pydefuddle
print(capture_screenshot())            # 返回 PNG 文件路径（非 base64）
close_tab(t)
'@ | browser-harness
```

预导入助手：`page_info / js / cdp / list_tabs / new_tab / switch_tab / activate_tab / close_tab / click_at_xy / scroll / fill_input / press_key / upload_file / wait_for_element / wait_for_render / wait_for_load / wait_for_network_idle / extract_page_content / extract_url_content / web_fetch / google_search / bing_search / run_app / setup_browser_apps / capture_screenshot / drain_events / http_get`（全部经 daemon，永远只碰 agent Chrome；`web_fetch` 纯 HTTP 起步、bot 墙升级浏览器，`run_app` 可在脚本内调任意 CLI 子命令）。等待判官优先级：已知目标 → `wait_for_element`；一般就绪 → `wait_for_render`（渲染静默 + 合成器心跳，网络态≠渲染态）；`wait_for_load` 适合静态页；`wait_for_network_idle` 仅在等待对象确实是某个数据请求时用（长轮询/beacon 永不 idle）。

### 技能与插件分发

```powershell
PS> browser-harness skills
  claude   up to date    ~\.claude\skills\browser-harness
  codex    up to date    ~\.codex\skills\browser-harness
  workspace up to date   …\browser-workspace\domain-skills  [107 domain-skills]
  workspace up to date   …\browser-workspace\apps           [8 apps]
```

### rmux 会话管理（框架核心）

```powershell
browser-harness rmux list|status|new|ensure|send|keys|capture|kill|kill-server|version
PS> browser-harness rmux status
running: True
sessions: x-monitor, x-supervisor

browser-harness rmux capture x-supervisor   # 看 x-monitor 监督日志
browser-harness rmux kill x-monitor         # 停抓取 worker（supervisor 自愈重拉）
browser-harness rmux kill x-supervisor      # 停整个监控栈
```

`kill-server` 只销毁本项目 `browser-harness` label 的 rmux 服务，不碰其他程序。

## 二次开发

包是**薄核心**（daemon / helpers / rmux / 诊断 / skills），应用一律做成 `browser-workspace/apps/` 下的插件。按改动深度分三层：

| 层 | 改哪里 | 谁生效 / 怎么生效 |
| --- | --- | --- |
| **不改代码** | `<BH_HOME>/browser-workspace/` 下自加：新 app 文件、新 domain-skill 站点、`browser_helpers.py` 里按函数名覆盖内置 helper | 即写即用；`skills sync` 只增不删，永不覆盖你的自加内容 |
| **改插件** | repo `browser-workspace/apps/<app>.py`（git 源） | 拷入 `src/browser_harness/references/apps/` → 测试 → 发版 → 目标机 `--update` 铺装生效 |
| **改核心** | repo `src/browser_harness/`（daemon/helpers/admin 等） | 走同一发版链路；CDP 面与安全约束见 `AGENTS.md`（最小改动、不扩大攻击面） |

**开发环境**：

```bash
git clone https://github.com/raystyle/browser-harness && cd browser-harness
./browser-harness --version      # 跑当前工作树（环境自动准备：.venv 优先，否则 uv run 兜底；BH_HOME 按平台隔离：Windows <repo>/.browser-harness-dev-win、其余 .browser-harness-dev，不污染装机数据，见 R006）
# 共享 checkout（同目录多平台/WSL 混用）勿混用同一 .venv——平台不符的残留 venv 会让 uv 报错，整删 .venv 重建即可
uv run --with pytest python -m pytest tests/unit -q    # 单测（集成测试需 live browser）
```

**发版闭环**（完整清单见 R003）：改源 → 拷包（防漂移测试锁着这步）→ 测试全绿 → 版本 +1 + CHANGELOG → `git push origin main` + tag + Release → 发版机跑 `--update -y` 自验（接力路径 + doctor + 栈恢复）。

规范细节（插件类型、入口约定、测试门槛、已知边界）：[docs/references/R003-插件开发与测试规范.md](docs/references/R003-插件开发与测试规范.md)。

## 文档

- [AGENTS.md](AGENTS.md)：开发 / 交互 / 安全规范。
- [SKILL.md](SKILL.md)：agent 操作路由。
- [INDEX.md](INDEX.md)：项目唯一索引。
- `docs/proven/`、`docs/research/`、`docs/mistakes/`：方案、研究、错误沉淀。
