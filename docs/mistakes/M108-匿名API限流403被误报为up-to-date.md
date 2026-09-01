# M108 匿名 API 限流 403 被误报为 up to date

> 分类：升级链路。首犯发现 2026-09-01（v0.6.6 发版自验时）。

## 现象

v0.6.6 Release 已发布（API `releases/latest` 实测返回 `v0.6.6`），已装 0.6.5 的 CLI 跑 `browser-harness --update -y` 却输出 `browser-harness is up to date (0.6.5)`，不升级。doctor 同样显示 `latest release 0.6.5`。[实证: 2026-09-01 发版机]

## 根因

`_latest_release_tag` 的重拉（M/v0.6.3 修复强制的那次）urllib 匿名请求撞上 **GitHub API 匿名配额 403**（本机 60/60 耗尽；gh CLI 带认证不受影响，掩盖了现场）→ `except Exception: return cache.get("tag")` 回退缓存 0.6.5 → `0.6.5 > 0.6.5` 不成立 → 判定 up to date。**限流瞬态失败与"确认没有新版"不可区分**，缓存回退路径把前者伪装成了后者。M102/M103 一族的老朋友：失败被静默吞掉、报了乐观结论。

## 处理（当日）

不阻塞发版：等配额重置（≤1h）后重试 `--update` 即真升级；本机走外部 `uv tool install --force`（栈已停、无进程持锁，M102 认可形态）+ `skills sync` 恢复 0.6.6 副本（旧 CLI 的 sync 曾把 claude/codex 副本降回 0.6.5 内容，升级后 resync 即愈）。

## 预防 / 修复方向（TODO 挂起）

- `_latest_release_tag` 区分"拿到答案"与"拿到回退"：显式 `--update` 场景下重拉失败应打印 `check failed (rate limited/offline) — falling back to cache, retry later`，不裸报 up to date。
- 可选：403 限流时读响应头 `x-ratelimit-reset` 提示具体等待时长；或对 `--update` 提供 `--force` 旁路（跳过判定直接升级）。
- 发版自验脚本别在同一 IP 上反复匿名打 API（本日多版本连发是配额耗尽的诱因）；gh 已认证环境用 `gh api` 交叉核对现场。
