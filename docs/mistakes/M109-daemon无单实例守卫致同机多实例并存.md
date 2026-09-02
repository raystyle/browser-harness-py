# M109 daemon 无单实例守卫致同机多实例并存

> 分类：daemon 生命周期。首犯发现 2026-09-02（Issue #1，ome 升级停栈前进程快照）。

## 现象

`ome install browser-harness --force` 停栈实测前，进程快照发现 **4 个并存 `-m browser_harness.daemon` 实例**：2 个 venv 底座（`D:\ohmyenv\uv-tools\...\Scripts\python.exe`）+ 2 个裸 python 底座（PATH 命中系统 `D:\ohmyenv\python\python.exe`）。daemon 语义为「下次调用时重启」，历次调用各拉起一份、退出路径不收敛，跨会话累积陈货。[实证: 2026-09-02 Issue #1 本机快照]

## 根因

启动守卫只有 `daemon.py __main__` 的一次 ping（`already_running()`），防不住并发，三层叠加：

1. **TOCTOU 窗口 ~75s**：ping 之后 → 写 PID → `get_ws_url()`（Chrome 不在可死等 30s）→ CDP 握手（`LOCAL_HANDSHAKE_TIMEOUT=45s` 等 Allow 弹窗）→ 才 bind IPC 端点。窗口期内并发的第二个调用方（另一 CLI 会话 / x-monitor / chrome-mode 翻转）ping 不通，各自再拉一份。
2. **赢家通吃、输家变僵尸**：Windows 侧 `serve()` 绑临时端口后覆写 `.port` 文件，最后绑的赢，先前实例端口号永久丢失——进程活着但不可达；POSIX 侧第二次 bind 会 unlink 第一个的 socket 路径，同样孤儿化。
3. **PID 文件被覆写**：每次启动 `open(PID, "w")`，`restart_daemon()` 只能经 port 文件找到赢家，僵尸躲过每次「重启」→ 跨会话累积。双解释器底座说明 venv shim（`sys.executable -m`）与裸 `python -m` 两条启动路径并存，同源 runtime 目录互相踩文件。[实证: 上述快照；推断: 三层链条由代码读出，2026-09-02 修复时核对]

## 处理（当日）

内核级单实例锁，`_ipc.acquire_lock()` + `daemon.claim_single_instance()`：

- POSIX `fcntl.flock` / Windows `msvcrt.locking`（LockFileEx），**进程死亡 OS 自动释放**——崩溃的 holder 不留陈锁，无需陈锁回收逻辑；锁只盖文件字节 0，元数据写在偏移 1（LockFileEx 会挡住他进程对被锁字节的读），争抢方可无等待读到 holder 的 pid + 解释器路径。
- `__main__` 流程改为：ping 通（含无锁的旧版 daemon）→ 照旧退出 0；锁被占且无响应 → 有界等待（`BH_LOCK_GRACE`，默认 90s > 合法启动 ~75s）等在途 holder 起来或死亡后自己接管；超时 → 退出 1 并报 holder pid 供人工清理。LOG 截断与 PID 写入挪到持锁之后，共享文件恢复单写者。
- 锁按 `_runtime_stem` 键控（`bu-<NAME>.lock`），named daemon 各自一把互不干扰；`BH_RUNTIME_DIR` 隔离目录天然各锁各的。

E2E（本机，隔离 BU_NAME + 不可达 CDP 端点）：争抢方短 grace 超时退出并准确报出 holder pid；长 grace 方在 holder 死后无缝接管、日志单写者；正常生命周期结束后 PID 文件清理、仅留惰性锁文件（内容含 pid + 解释器底座）。单测 222 绿（锁互斥/跨进程/claim 三分支）。[实证: 2026-09-02 本机]

## 预防

- daemon 只经 `browser-harness` CLI（venv shim）拉起；裸 `python -m browser_harness.daemon` 非支持路径（解释器底座混跑的来源）。
- 旧版无锁 daemon 与新版并存的过渡窗内（升级未停栈），锁对新旧互不生效，仍可能 1 旧 + 1 新；`--update` 的停栈前置已覆盖此场景。
- TODO 队列「chrome-mode 翻转双拉起竞态」与本条同族（翻转要并发重启双 daemon），守卫落地后该竞态应随之消失，保留观察。
