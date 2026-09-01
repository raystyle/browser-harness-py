# M102 CLI 升级前运行中的进程锁住 venv

> 环境错误。登记日 2026-09-01。关联 R003 发布清单第 6 步、v0.4.1 / v0.5.1。

## 现象

`uv tool install --upgrade --force` 失败：`failed to remove directory D:\ohmyenv\uv-tools\browser-harness\Scripts: 拒绝访问 (os error 5)`。两次实证（v0.4.1、v0.5.1）。

## 根因

升级要替换 venv 的 `Scripts\` 目录，但仍有 python 进程从该目录运行，Windows 拒绝删除被占用文件。锁住者不止一类（[实证] 两轮各见一种）：

- v0.4.1：rmux 栈里的 x-worker / x-supervisor（`rmux kill-server` 前）。
- v0.5.1：default daemon（`python.exe -m browser_harness.daemon`，PID 实查）。**rmux kill-server 不会停 daemon**，daemon 是独立常驻进程。

## 正确处理

升级 CLI 前按序停干净，再装：

```powershell
browser-harness rmux kill-server                       # 停 x-supervisor / x-worker
Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "D:\ohmyenv\uv-tools\browser-harness*" }   # 实查残留
Stop-Process -Id <残留PID> -Force                       # 通常是 default daemon
uv tool install --upgrade --force git+https://github.com/raystyle/browser-harness@main
```

升级后恢复：`browser-harness x-monitor`（幂等重拉 Chrome 附着 + rmux 栈 + daemon）。

## 教训

- 「停栈」≠ 只停 rmux：daemon 也是运行栈的一部分，升级前以进程实查为准，不以命令清单为准。
- Windows 上 venv 文件锁的表现是「拒绝访问 (os error 5)」，见到即查占用进程，不要反复重试安装。
