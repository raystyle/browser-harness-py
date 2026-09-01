# R004 Windows 无头模式测试指引

> 开发测试参考（要做什么、怎么做）。登记日 2026-09-01。
> 背景：WSL2 侧无头全链路已实证（S006/S007）；本文在 Windows 侧复测同一能力。目标机：`C:\Users\ray\.config\browser-harness`（BH_HOME）、Chrome Dev 154（`C:\Program Files\Google\Chrome Dev\Application\chrome.exe`）、已装 browser-harness 0.6.5。

## 两条路径

| 路径 | 前提 | 说明 |
| --- | --- | --- |
| A 手动无头拉起 | 现装 0.6.5 即可，**不用等发版** | 手动以无头参数启动 agent Chrome（9223）；x-monitor 检测到 9223 已应答就跳过自启、直接接管 [实证: WSL 侧同机制] |
| B 全自动无头 | 发版 v0.6.6+（含 `BH_CHROME_HEADLESS`） | `.env` 加一行，x-monitor 自动以无头拉起 |

## 路径 A：手动无头拉起（pwsh 7）

1. 确认 9223 空闲（WSL 栈已停，正常应无响应）：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9223/json/version -TimeoutSec 3
# 期望：连接被拒 → 空闲
```

2. 无头启动 agent Chrome（复用既有 profile，X 登录态已在里面）：

```powershell
$chrome = "C:\Program Files\Google\Chrome Dev\Application\chrome.exe"
$prof   = "$env:USERPROFILE\.config\browser-harness\agent-chrome-profile"
Start-Process $chrome -ArgumentList @(
    "--user-data-dir=$prof",
    "--remote-debugging-port=9223",
    "--headless=new", "--disable-gpu",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-features=IntensiveWakeUpThrottling,CalculateNativeWinOcclusion",
    "about:blank"
)
```

3. 验证 CDP 通、确为无头（UA 带 `HeadlessChrome`）：

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:9223/json/version).Content
```

4. 起监控栈并验证增量：

```powershell
browser-harness --doctor          # chrome running / daemon alive 全绿
browser-harness x-monitor         # 检测到 9223 已运行，直接接管
browser-harness browsers          # [agent] ... port=9223
browser-harness x-search --stats  # 10 分钟一轮，total_tweets 有增量
```

## 路径 B：发版后全自动

`C:\Users\ray\.config\browser-harness\.env` 追加：

```
BH_CHROME_HEADLESS=1
```

Windows 有显示器，无显示自动检测不会触发，必须显式写 [实证: `_headless_flags` 仅在 DISPLAY/WAYLAND_DISPLAY 均空的 Linux 自动无头]。之后 `browser-harness x-monitor` 一条命令即无头全栈。

## 验收标准

- `--doctor` 全绿；`/json/version` 的 UA 是 `HeadlessChrome/154...`。
- `x-search --stats` 两轮之间 total_tweets 有增量（10 分钟一轮）。
- 桌面无 Chrome 窗口弹出（这就是无头的意义）。

## 注意事项

- **共享 checkout 的 .venv 陷阱**：`D:\browser-harness\.venv` 已被 WSL 侧 uv 重建为 Linux venv。Windows 上不要 `uv --directory D:\browser-harness run ...`（会把 venv 再重建回 Windows 版，WSL 侧下次又要重建，互相拆台）。Windows 一律用已安装的 `browser-harness`。
- **无头 UA**：`HeadlessChrome` 对 X 时间线抓取无影响 [实证: WSL 侧 11 分钟 +27 推]；个别反爬站点如被区别对待，发版后用 `BH_CHROME_EXTRA_FLAGS=--user-agent=...` 覆盖。
- **权限**：专用 profile + 启动 flag 本身即授权，无头/有头都不需要 chrome://inspect 开关或 Allow 弹窗（S006）。
- **回退**：路径 A 直接结束该 chrome 进程（或 `Stop-Process -Name chrome`——注意会连用户 Chrome 一起杀，建议按命令行精确匹配），再照常 `x-monitor` 会自动有头拉起；路径 B 删掉 `.env` 那行。x-monitor 停栈（`rmux kill-server`）不会关手动拉起的 Chrome，需单独处理。
- **勿双侧并跑**：Windows=9223、WSL=9224（各自 .env 已配好）；同一 X 账号两侧同时跑 x-monitor 会重复抓取+抢限流，只跑一侧（S007）。
