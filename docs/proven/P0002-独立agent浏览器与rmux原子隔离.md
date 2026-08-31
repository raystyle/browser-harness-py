# P0002 独立 agent 浏览器与 rmux 原子隔离

- 状态：已完成
- 日期：2026-08-31
- 关联：S004、M101

## 背景与问题

X 监控 worker 需要操作浏览器，但直接 attach 用户 Chrome 会干扰用户（缩窗 / 最小化 / 切标签 / 抢焦点）；rmux 也需与其他程序的 rmux 服务隔离。

## 目标与非目标

- 目标：
  - agent 用独立 Chrome（独立 profile + 独立端口），用户 Chrome 不受影响。
  - rmux 只维护自己的 `browser-harness` label，不碰其他程序的 rmux。
- 非目标：不改用户 Chrome 的 profile/会话。

## 方案

- 独立 Chrome：`--user-data-dir=...\agent-chrome-profile --remote-debugging-port=9223` + anti-throttle flags。
- worker 连独立 Chrome：`BU_CDP_URL=http://127.0.0.1:9223`。
- 启动脚本：`agent-workspace/start-x-monitor.ps1`。
- rmux label 隔离：`-L browser-harness`；`rmux_binary()` 优先 `AppData\Local\rmux`；`kill-server` 只清自己 label。

## 备选方案

- CDP 复制 cookie：被 M144 授权拦住（见 S004）。
- Win32 缩窗：HWND 查找不可靠（见 S004）。
- 空闲检测前台刷：导致监控停止抓取（见 S004）。

## 实施步骤

1. 建独立 profile，启动独立 Chrome（9223）。
2. 独立 Chrome 手动登录 X。
3. worker 改连 BU_CDP_URL=9223，重启监控。
4. 验证窗口隔离 + 10 分钟稳定。

## 实施过程与经验

- 独立 Chrome 缩成 520×200 小窗 + 最小化；用户 Chrome 窗口尺寸不变。
- `rmux kill-server` 后 ohmyagents 的 daemon 仍在，我们的 daemon 正确销毁。
- 10 分钟采样：双 session 存活、心跳新鲜、数据增长。

## 验收标准

- 独立 Chrome 缩窗 / 最小化只作用于 agent 窗口，用户 Chrome 不动。
- `rmux kill-server` 不误伤其他 label。
- 10 分钟采样稳定通过。
