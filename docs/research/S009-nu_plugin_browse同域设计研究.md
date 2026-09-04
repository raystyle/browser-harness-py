# S009 nu_plugin_browse 同域设计研究

> 研究原型过程（为什么）。登记日 2026-09-04。
> 来源：用户定向「参考研究学习 D:\sourcecode\opensource\nu_plugin_browse」。
> 对象：Nushell 无头浏览器插件（Rust + chaser-oxide CDP），本地源码通读 + README 全读；与 browser-harness 同域（CDP 驱动真实 Chrome），设计互为镜鉴。

## 结论速览

- **done 协议（binding）是最值得偷的设计**：插件注入 `window.__browse_done(payload)`，页面侧脚本（init script / 站点 SDK）就绪即调用，把 JSON 写进 `<meta name="__browse_done">` 标签；Rust 侧用**隔离世界轮询 meta 标签**取信号——零 `Runtime.enable`、零额外 CDP 事件订阅，完全隐蔽。[实证: 本地源码 `src/page.rs` DONE_HELPER_JS/DONE_POLL_JS]
- **等待结束原因是一等公民（`idle` 六值枚举）**：`skipped | network-idle | timeout | binding | deadline | ""`——不返回 bool,返回「**哪个机制结束了等待**」。网络空闲只是并列机制之一（且仅 `--trace` 时启用）,deadline 是最外层硬截止。与我们「事件判官、超时兜底、未知≠失败」原则同构,但契约化更彻底。
- **frozen 是一等状态**：会话状态 `open | frozen | closed`,frozen = 进程在但 CDP 无响应——与我们 `wait_for_render` 的 rAF 心跳辨别「渲染器冻死 vs 已静默」同一根问题(冻死与就绪在「无事件」上同形,必须靠活性信号区分),他们放在会话级,我们放在页面级。[推断: 语义对照;其探针实现细节未逐行核]
- **分层关闭与我们 v0.6.10 同构**：`browse close` 走 CDP `Browser.close` 优雅关闭,frozen 状态才按端口强杀进程——优雅优先、强杀兜底,与我们的 `meta:close_browser` → pid 路径完全同路。[实证: README close 节 + status 节]
- **Runtime.enable 是可检测的反爬信号,他们默认不开**：只在 `--debug`（要 console 捕获/异常捕获）时启用;隔离世界 eval（`CreateIsolatedWorld`）为默认 stealth 路径。**对照:我们 daemon attach 即四域全开（Page/DOM/Runtime/Network）**,对反爬敏感站点是更大的暴露面——值得按需化。[推断: 暴露面对照;未实测各域启用对 bot 检测的边际贡献]
- `--url` 走 `browser.new_page()` 绕过 CDP `Page.navigate`——x.com 等检测并阻止 CDP 程序化导航的站点的解法;我们的 `new_tab`（createTarget+goto）是近亲但没把这条例外写成显式姿势。
- 会话管理三件套与我们撞设计：命名规则 `[a-zA-Z0-9_-]`、per-session 目录、fs4 排他锁防并发——与 BU_NAME + BH_HOME + 内核锁逐条对应,印证两套独立演化收敛到同构。[实证: README 会话管理节]

## 对 browser-harness 的可落地清单

按价值排序,均未实施（避免读研究当排期）：

1. **done 协议原语**：helpers 注入 `__bh_done(payload)`（meta 标签通道 + 隔离世界/普通 `js` 轮询）,`wait_for_done(timeout)` 与 `wait_for_render` 并列——已知目标的**任务真值**判官（页面自己宣告就绪并交数据）,比通用静默判定更强;X 滚动采集、SPA 数据抓取类任务直接受益。
2. **等待原因枚举**:`wait_*` 族返回值从 bool 升级为「结束原因」（found/settled/frozen/deadline/ipc-retry）——bool 把「到点未知」压扁了,枚举才不丢信息。可与既有三态原则合并成一页契约。
3. **域启用按需化**：daemon 默认四域全开改为「attach 时 Page,首次 drain_events/network 调用时 Network,js 时 Runtime」的懒启用,缩小反爬信号面。需评估对我们 helpers 使用模式的摩擦（几乎每个脚本都 js,Runtime 懒启用收益主要在纯导航/截图流）。
4. **x.com 类站点的 new_page 直开姿势**：SKILL 记档「CDP navigate 被站点检测时,用 Target.createTarget 带 URL 直开」为 Gotcha 条目（我们现在只有 new_tab 顺带覆盖）。

## 差异与取舍（为何不照搬）

- 他们是**每次调用起进程的插件**（Nu 插件模型),无长驻 daemon——会话状态靠 profile 目录 + 文件锁跨进程协调;我们有长驻 daemon(事件缓冲、会话亲和、看门狗),两端约束不同,他们的扁平契约(所有 key 恒存在 + sentinel 默认)在跨进程边界上必要,我们进程内调用的返回形状自由度更高。
- 指纹预设（--profile windows-gamer 等）是 stealth 维度,我们当前边界明确不做深度 stealth（最小 CDP surface 原则,AGENTS Security 节）,仅记录不采纳。
- 一次性模式默认自动关浏览器 = 我们 `--once` 隔离栈的缩小版(无登录克隆、无端口预留——单会话无并发,不需要)。

## 探索过程

1. README 全读（579 行,中文,含完整命令矩阵/等待策略表/错误契约/测试分层 113 项）。
2. 源码定位验证三机制:`src/page.rs:46/63`(done 协议 meta 通道注入与轮询 JS)、`src/commands/browse_status.rs:114`(frozen 判定)、close 分层(README 节 + status 语义)。
3. 与 browser-harness 现状逐条对照(见结论速览),产出可落地清单四条挂本档,未入 TODO 队列(用户定向再排期)。
