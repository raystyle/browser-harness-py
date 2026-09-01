# R005 macOS 无头模式接管验收指引

> 开发测试参考（要做什么、怎么做）。登记日 2026-09-01，Windows 侧交接落档。
> 背景：无头模式已在 WSL（S006/S007）与 Windows（R004 路径 A）双侧实证；本文是队列目标「Linux/macOS 接管」的 macOS 半，供在 Mac（`ssh ray@lan-mac`）上接管验收。
> 前置已完成（Windows 侧 2026-09-01 夜）：Windows/WSL 栈均已停净；X 会话 cookie 已导出并 scp 到 Mac `~/cookies-x-win.json`（12 条，auth_token/ct0/twid 齐，文件含活凭证，导入后建议删除）。

## 第一步 代码先行（关键差异）

> 状态更新（2026-09-01 深夜）：Windows 侧已 `git push origin main`，origin 即 v0.6.6 代码——路 1 已是现实路径，Mac `uv tool install` 直接拿到。下表留档备查。

v0.6.6 的无头能力（`BH_CHROME_HEADLESS`、`BH_AGENT_CDP_PORT`）与 cookies 插件在落档时**只存在于 Windows 开发机的本地提交里，origin 还是 v0.6.5**（发版被暂缓）。Mac 拿到代码三条路任选：

| 路 | 命令 | 说明 |
| --- | --- | --- |
| 1 推 origin 后直装（推荐） | Windows 侧 `git push origin main`；Mac 侧 `uv tool install git+https://github.com/raystyle/browser-harness` | 推 main 是日常开发动作，不是发版（无 tag/Release）；git 源装默认分支头，即 v0.6.6 代码 |
| 2 bundle 搬运 | Windows 侧 `git bundle create bh.bundle origin/main..main` → scp → Mac `git clone bh.bundle` | 完全离线 |
| 3 只差 cookies 插件时 | 单独 `scp cookies.py`（`agent-workspace/apps/cookies.py`）到 Mac，用工具 venv 的 python 直接跑 | 路径 A 验收（0.6.5 即可）+ 手动无头拉起，仅 cookie 导入需要这一个文件 [实证: Windows 侧同法绕过 0.6.5 无插件] |

Mac 上工具 venv 的 python：`$(uv tool dir)/browser-harness/bin/python`（macOS 是 `bin/`，Windows 是 `Scripts\`）。

## 第二步 环境

```bash
# Chrome 路径（代码 Darwin 分支自动找）：
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
```

- `.env`（BH_HOME 下）：`BU_CDP_URL=http://127.0.0.1:9223`；**必须显式 `BH_CHROME_HEADLESS=1`**——自动无头只在无 `DISPLAY` 的 Linux 触发，Mac 有显示器 [实证: `_headless_flags` 逻辑，R004 同因]。端口 9223 默认即可（独立机器，无 mirrored 网络撞口问题）。
- 授权：专用 agent profile + 启动 flag 本身即授权，无头/有头都不需要 mac-approve 或 Allow 弹窗（mac-approve 只用于用户自己的 Chrome 走 chrome://inspect 的场景，S006/R004 已注）。

## 第三步 验收（四条，同 R004）

1. 无头拉起（装的是 v0.6.6 代码时 x-monitor 会自动无头拉起，`BH_CHROME_HEADLESS=1` 生效即可跳过手动；0.6.5 则手动）：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="$HOME/.config/browser-harness/agent-chrome-profile" \
  --remote-debugging-port=9223 --headless=new --disable-gpu \
  --disable-background-timer-throttling --disable-renderer-backgrounding \
  --disable-backgrounding-occluded-windows \
  --disable-features=IntensiveWakeUpThrottling,CalculateNativeWinOcclusion \
  about:blank &
```

2. 登录态导入（新 profile 首次，或复用迁移文件）：`chmod 600 ~/cookies-x-win.json`，然后 `python cookies.py import --file ~/cookies-x-win.json --endpoint http://127.0.0.1:9223`（或装好 v0.6.6 后 `browser-harness cookies import --file ...`）；验证 `web-fetch https://x.com/home` 停在主页即登录生效。
3. `browser-harness --doctor` 全绿；`/json/version` 的 UA 带 `HeadlessChrome`。
4. `browser-harness x-monitor` → `x-search --stats` 两轮（10 分钟一轮）total_tweets 有增量；屏幕无 Chrome 窗口。

## 注意事项

- **勿多侧并跑**：同一 X 账号只在一侧跑 x-monitor（Windows/WSL 已停，Mac 接管期间独占，S007）。
- 无头 UA `HeadlessChrome` 对 X 时间线无影响 [实证: WSL 11 分钟 +27 推、Windows 两轮 +2、Mac 两轮 +17]；个别反爬站点用 `BH_CHROME_EXTRA_FLAGS=--user-agent=...` 覆盖。
- 停栈收尾：`browser-harness rmux kill-server` + 停双 daemon（`--reload` 停 default；x-monitor daemon 用 python 调 `restart_daemon('x-monitor')`）；手动拉的无头 Chrome 按 pid 停，勿 `pkill chrome` 连用户 Chrome 一起杀。
- 验收通过后：macOS 半即完成，GOAL/TODO 队列目标「Linux/macOS 接管」整体收口；v0.6.6 发版（tag+Release+`--update` 自验链路）另行定时。

## 验收结果（2026-09-01 Mac 侧实跑）

四条全过，macOS 半收口 [实证: lan-mac，macOS 26.5.2 / Chrome 152.0.7977.65 / 工具 0.6.6 git 源]：

| 项 | 结果 |
| --- | --- |
| 无头拉起 | 手动命令拉起 9223，UA `HeadlessChrome/152.0.0.0`；Keychain/CVDisplayLink 报错为无头噪音，非致命 |
| 登录态导入 | 11/11 cookie 导入；web-fetch 首击「Try again」为反爬回退，水合后 DOM 有账号按钮、标题「🐴 主页 / X」；迁移文件导入后已删 |
| doctor | 全绿（chrome/daemon/连接/rmux 五项 ok） |
| x-monitor | 首分钟 25 推；两轮 25→42（+17）；后续 42→61；屏幕无 Chrome 窗口 |

**两条关键修订（被验收实证推翻/收敛，详见 S008）**：

1. **第三步的手动拉起命令在 macOS 有钥匙串坑**：从 shell 直拉二进制的进程拿不到钥匙串密钥（`errKCInteractionNotAllowed`），CDP 导入的 cookie 落盘即废——Chrome 重启登录态全丢 [实证]。**拉起一律交给 x-monitor / daemon / `chrome-mode`（`open -na` 走 LaunchServices）**；手动命令仅用于临时验证（接受登录不持久）。
2. **登录态录入的标准姿势 = 有头人工登录**：`browser-harness chrome-mode headed` → 窗口里人工登录 → `browser-harness chrome-mode headless` 值守。有头写入的登录态可跨无头重启继承 [实证: 翻转重启后 LOGGED_IN]；cookie 导入仅在「Chrome 长期不重启」场景可用。

另：用户 Chrome 未运行时点 Dock 可能激活到无窗口的无头 agent 实例（同应用身份），表象「Chrome 打不开」——`open -na "Google Chrome"` 拉回用户实例（S008）。
