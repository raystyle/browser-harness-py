# M101 Chrome 的 --user-data-dir 引号导致 profile 污染

> 分类错误。登记日 2026-08-31。关联 S004、P0002。

## 现象

启动「独立 Chrome」时，用户的 Profile 3 cookie 被清空（只剩几条 google.com），X 等所有网站登录态丢失。

## 根因

PowerShell `Start-Process -ArgumentList '--user-data-dir="D:\...\agent-chrome-profile" ...'` 中，引号被错误处理，Chrome 收到的 user-data-dir 参数失效，意外使用了默认 user-data-dir（用户的 Profile 3），触发了 Chrome 的 cookie 清理。

## 正确处理

- 独立 profile 的 `--user-data-dir` 参数不带引号：`--user-data-dir=D:\browser-harness\agent-chrome-profile`。
- 启动后立即用进程命令行校验 `--user-data-dir` 确实指向独立目录，且没有另一个 Chrome 主进程误用默认 profile。
- 独立 Chrome 的 profile 目录加入 `.gitignore`。
- agent 浏览器与用户浏览器彻底分离：用户 Chrome 用默认 profile，agent 用独立 profile + 独立端口（9223）。

## 教训

- 凡是「隔离 profile」的启动参数，都要验证最终进程的真实命令行，不能只看启动动作成功。
- 涉及用户数据（cookie/profile）的操作，先验证目标目录，再执行。
