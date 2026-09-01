# S008 macOS 无头接管与钥匙串登录态持久化研究

> 研究原型过程（为什么）。登记日 2026-09-01，Mac 侧（lan-mac，macOS 26.5.2 / Chrome 152.0.7977.65）。
> 来源：R005 接管验收实跑 + 验收中暴露的登录态丢失问题与修复闭环。
> 姊妹篇：S006（WSL2 无头适配，Linux 侧镜像）、S007（cookie 跨设备迁移）、R004（Windows 无头路径 A）。

## 结论速览

- **macOS 无头接管四条验收全过**（无头拉起 / cookie 导入登录 / doctor 全绿 / x-monitor 两轮增量 25→42），Linux/macOS 接管队列目标整体收口。[实证: 2026-09-01 Mac 本机，详见 R005 验收结果]
- **macOS 上 CDP 导入的 cookie 只保进程生命周期**：`Network.setCookie` 注入后当即可用（监控全程有效），但 Chrome 重启后登录态丢失。[实证: 导入后同进程 LOGGED_IN；`chrome-mode` 翻转（重启 Chrome）后 NOT_LOGGED_IN、`twid` 消失]
- 根因是**钥匙串加密**：Chrome 在 macOS 用登录钥匙串的 `Chrome Safe Storage` 密钥加密 cookie 落盘。从 shell 直接拉起二进制（R005 原手动命令）的进程拿不到该密钥（启动日志 `errKCInteractionNotAllowed`，无头也弹不了授权框），落盘上下文不对，新进程解不开即弃。[推断: 由启动日志错误码 + 前后行为差异推得，未直接解剖 Cookies 库密文]
- **登录态的正确录入方式 = 有头人工登录一次**：GUI 上下文（LaunchServices 拉起）的 Chrome 用真钥匙串密钥落盘；此后 daemon 用 `open -na`（同样走 LaunchServices）拉起的无头 Chrome 能解开，**无头重启继承登录态成立**。[实证: 有头登录 → `chrome-mode headless` 重启 → 主页 + LOGGED_IN]
- 由此沉淀 `chrome-mode` 命令（v0.6.6）：`status|headed|headless` 三态，一条命令完成 .env 重写 + 按 pid 精确停 agent Chrome + 双 daemon 重启 + x-monitor 自动恢复；所有 app 无差别继承模式。[实证: Mac 本机 headed/headless 往返翻转各两次]
- **macOS 同 bundle 双实例的 Dock 混淆**：agent 无头 Chrome 与用户 Chrome 是同一应用身份。用户 Chrome 未运行时点 Dock，激活到无窗口的无头实例，表象为「Chrome 打不开」；`open -na "Google Chrome"` 即可拉回用户实例。[实证: 本机复现并解除]

## 与 Linux/Windows 的差异对照

| 维度 | WSL2/Linux（S006/S007） | Windows（R004） | macOS（本文） |
| --- | --- | --- | --- |
| cookie 落盘加密 | 固定口令方案，无用户钥匙串 | DPAPI（会话内可用） | 登录钥匙串（上下文敏感） |
| CDP 导入 cookie 跨重启 | 存活 [实证: S007 迁移后 x-monitor 随起随用] | 未单独验证 | **丢失**（直拉二进制上下文）[实证: 本文] |
| 无头拉起方式 | 二进制直跑即可 | 二进制直跑即可 | **必须 LaunchServices（`open -na`）**，daemon 已是此路；手动直跑仅进程内有效 |
| 登录录入 | cookie 导入即可 | cookie 导入即可 | **有头人工登录**（或导入后永不重启 Chrome） |

## 探索过程

### 阶段 1：R005 验收（按 Windows 侧交接指引执行）

- `uv tool install git+…`（origin main 已含 v0.6.6 代码）→ `skills sync` 铺装 8 apps。
- `.env`：`BU_CDP_URL=http://127.0.0.1:9223` + `BH_CHROME_HEADLESS=1`（Mac 有显示器，必须显式）。
- 四条验收逐条过：手动无头拉起（UA `HeadlessChrome/152`）→ cookie 11/11 导入 → web-fetch/管道自动化双路验证登录（「Try again」首击页是反爬回退，水合后账号按钮在）→ doctor 全绿 → x-monitor 25→42（+17）。
- 迁移文件 `~/cookies-x-win.json` 按指引导入后删除（含活凭证）。

### 阶段 2：双模切换需求（用户定向）与 chrome-mode 实现

- 用户定向：所有应用默认支持无头/有头双模，X 登录录入需有头。
- 既有机制盘点：`BH_CHROME_HEADLESS`（1/0/缺省自动）+ `.env` 以 `setdefault` 加载（进程环境可单次覆盖）；缺口 = 常驻 Chrome 没有一条命令的模式翻转（`_agent_chrome_running()` 幂等短路，改 env 不会重启）。
- 实现：`browser-harness chrome-mode [status|headed|headless]`——`.env` 为唯一事实源（重写键值），翻转时停双 daemon（它们在 spawn 时烘焙了旧 env）+ 按 pid 精确停 agent Chrome（`ps`/`/proc`/CIM 枚举按 user-data-dir 或端口匹配，绝不 `pkill chrome`）+ `ensure_daemon` 以新模式重拉 + x-monitor 幂等恢复。
- 顺带补齐 `browsers` 视图 Darwin 分支（`ps -axo pid=,args=`；macOS 可执行路径含空格，argv0 不能按空白切分，取首个 flag 之前的头部识别二进制名）。

### 阶段 3：登录态丢失与根因定位

- 现象：首次翻 headed 后 x.com 标题变「X。尽是新鲜事」（未登录落地页），DOM 无账号按钮，`document.cookie` 无 `twid`。
- 时间线还原：导入与全部监控成功都发生在**同一进程**（pid 79821，直拉二进制、钥匙串报错）；翻转杀掉该进程后登录态蒸发——「无头成功」从未跨过重启边界。
- 定性：内存会话（CDP 注入，即时生效）≠ 落盘持久化（钥匙串加密，上下文敏感）。macOS 是三者中唯一落盘加密依赖用户钥匙串的平台，见上表。

### 阶段 4：修复闭环（有头登录 → 无头继承）

- 用户在 headed 窗口人工登录一次（LaunchServices 上下文，真钥匙串密钥落盘）。
- `chrome-mode headless` 重启后：主页 + LOGGED_IN。[实证: 登录态跨无头重启存活]
- 结论：macOS 登录录入的标准姿势 = `chrome-mode headed` 人工登录 → `chrome-mode headless` 值守；cookie 导入仅适合「导入后 Chrome 长期不重启」的场景。

## 最终方案（Mac 值守机配置）

```bash
# ~/.config/browser-harness/.env
BU_CDP_URL=http://127.0.0.1:9223
BH_CHROME_HEADLESS=1        # 值守常态；chrome-mode 翻转会自动改写此键
```

- 拉起一律交给 `x-monitor` / daemon / `chrome-mode`（LaunchServices 路径）；**禁止从 shell 直拉 Chrome 二进制**（R005 手动命令已按此修订）。
- 登录录入：`browser-harness chrome-mode headed` → 人工登录 → `browser-harness chrome-mode headless`。
- 用户 Chrome「点不开」：先查是否有无头 agent 实例在顶包（`ps -axo pid=,args= | grep -v -- --type= | grep Chrome`），`open -na "Google Chrome"` 拉回用户实例。

## 遗留

- 翻转后偶见 Chrome 被二次拉起（疑似 flip 的 `ensure_daemon` 与 x-monitor 恢复各自的 ensure 竞态；后续翻转 pid 稳定，未再复现）——待观察，复现则修。
- agent Chrome 与用户 Chrome 同 bundle 身份的 Dock 激活混淆：候选解 = 独立应用副本（改 `CFBundleIdentifier`，如 Chrome Dev 之于 Chrome），工程量与升级维护成本待评估。
- 翻转期间的 stdout 缓冲导致子进程输出先于父进程提示出现（管道场景；终端场景行缓冲无此问题），纯观感，不修。
