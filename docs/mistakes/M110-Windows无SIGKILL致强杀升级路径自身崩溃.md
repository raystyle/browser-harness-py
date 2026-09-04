# M110 Windows 无 SIGKILL 致强杀升级路径自身崩溃

## 现象

`_stop_agent_chrome` 的强杀升级分支（SIGTERM 等待超时后补 SIGKILL）在 Windows 上从未生效——`signal.SIGKILL` 在 Windows Python 里不存在，该分支一执行就 `AttributeError`。潜伏至今无人察觉：Windows 的 `os.kill(pid, SIGTERM)` 本就是 `TerminateProcess` 无条件杀，首轮即死，升级分支从未真正运行过。[实证: 2026-09-04 新增单测 test_stop_agent_chrome_skips_normalization_when_chrome_survives 首跑即炸]

## 根因

跨平台信号语义想当然：POSIX 的「SIGTERM 礼貌 → SIGKILL 强杀」两段式照搬到 Windows，而 Windows 的 signal 模块只有 CTRL_C_EVENT/CTRL_BREAK_EVENT，`os.kill` 其余值一律 TerminateProcess——两段在 Windows 是同一个动作，且 SIGKILL 常量直接缺失。

## 处理（当日）

升级分支改 `getattr(signal, "SIGKILL", signal.SIGTERM)`——POSIX 语义不变（真 SIGKILL），Windows 回退 SIGTERM（即 TerminateProcess 重发，本来也无更强手段）。

## 预防

Windows 路径的「未被走过的分支」等于未测试的分支：os/signal/subprocess 这类平台分叉 API，单测要专门逼出冷分支（本例正是让 `_agent_chrome_running` 恒 True 强行走升级路径才发现）。写平台分支代码时反过来想：每个分支在另一平台存在吗？
