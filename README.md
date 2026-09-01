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
