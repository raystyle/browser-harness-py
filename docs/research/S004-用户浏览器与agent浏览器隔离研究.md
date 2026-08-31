# S004 用户浏览器与 agent 浏览器隔离研究

> 研究原型过程（为什么）。登记日 2026-08-31。
> 来源：本机 Chrome Dev 154 / rmux 0.10.0 / browser-harness daemon 实测。

## 结论速览

- agent 直接 attach 用户手动打开的 Chrome（默认 Profile 3），缩窗 / 最小化 / 切标签 / 抢焦点都会作用在用户窗口上，严重干扰用户。
- 正确做法：agent 用**独立 profile + 独立调试端口**的 Chrome，worker 通过 `BU_CDP_URL` 只连这个独立实例；用户 Chrome 完全不碰。
- 会话复用优先「独立 profile 手动登录一次」；CDP 导出 cookie 再导入会被 Chrome 144+ 默认 profile 的 M144 授权拦住，不推荐。

## 探索过程（含失败尝试）

### 尝试 1：空闲检测前台刷

- 思路：用户活跃（有键鼠）时不前台刷，空闲时才刷。
- 结果：X 网页版在页面 hidden 时自己不推新帖，空闲检测导致「用户一活跃就完全不抓」，监控名存实亡。放弃。

### 尝试 2：Win32 SetWindowPos 缩窗

- 思路：用 Win32 突破 CDP 的最小窗口尺寸（约 516×186）。
- 结果：`Chrome_WidgetWin_0` 主窗口在最大化等状态下 GetWindowRect 不可靠，HWND 查找会找错窗口，缩窗没生效。放弃，改回 CDP `Browser.setWindowBounds`（分两步：先 windowState=normal，再设 bounds）。

### 尝试 3：CDP 导出 cookie 导入独立 profile

- 思路：从用户 Chrome `Network.getAllCookies` 导出 x.com cookie，再 `Network.setCookie` 导入独立 Chrome。
- 结果：用户 Chrome 是默认 profile，Chrome 144+ 对 ws 连接弹 M144「Allow remote debugging?」授权，未授权直接 ConnectionRefused，导出失败。放弃。

### 最终方案：独立 profile + 手动登录

- 独立 Chrome：`--user-data-dir=D:\browser-harness\agent-chrome-profile --remote-debugging-port=9223` + anti-throttle flags。
- worker 用 `BU_CDP_URL=http://127.0.0.1:9223` 只连独立 Chrome。
- 会话：独立 Chrome 打开 x.com 手动登录一次（写在独立 profile，不影响用户 Profile 3）。

## 关键实测

- 独立 Chrome 窗口被 worker 缩成 520×200 贴右下角 + 最小化；用户 Chrome 保持 1536×808 不受影响。
- 10 分钟采样：rmux 双 session 全程 alive，心跳新鲜，推文 383→391 持续增长。

## 坑与教训

- `--user-data-dir` 参数不能带引号（PowerShell Start-Process 引号处理导致解析出错，曾意外指向默认 profile，清空用户 cookie）→ 见 M101。
- 独立 Chrome 的 profile 目录加入 `.gitignore`，避免把 cookie 等敏感数据提交进仓库。
