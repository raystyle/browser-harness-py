# M104 Linux 下 Chrome 重写 cmdline 导致 NUL 切分失效

> 分类：进程枚举。首犯 2026-09-01（WSL 适配，`browsers` 视图）。

## 现象

`browsers` 资源视图的 Linux 枚举（`/proc/<pid>/cmdline` 按 `\0` 切分 argv）对正在运行的 Chrome 主进程返回空——进程明明在跑、端口也活着。

## 根因

Chrome 在 Linux 上启动后会**重写自己的 cmdline**（规范化 flags、隐藏内部参数），重写后的 `/proc/<pid>/cmdline` 是**空格连接的一整串**，不再是 NUL 分隔的 argv。按 `\0` 切分只会得到一个含全部 flags 的元素，argv[0] 解析、`--type=` 子进程过滤全部失效。

[实证: WSL 内 /proc/6334/cmdline 读出单元素 `/opt/google/chrome/chrome --user-data-dir=... --headless=new ...`，ps 显示同一形态]

## 处理

切分后若只剩一个元素且含空格，再按空格切一次（`browsers._chrome_instances_linux`）：

```python
argv = [a.decode("utf-8", errors="replace") for a in raw.split(b"\0") if a]
if len(argv) == 1 and " " in argv[0]:
    argv = argv[0].split()
```

局限：重写后的 cmdline 不带引号，`--user-data-dir` 值含空格时会切错（Windows 路径挂载点如 `/mnt/c/Users/xxx yyy`）。当前场景 profile 路径无空格，先接受。

## 预防

任何「读 `/proc/*/cmdline` 解析 Chrome 参数」的代码都必须同时处理 NUL 分隔与空格连接两种形态；新写解析先拿真实运行中的 Chrome 验证，不要只用普通进程（如 sleep）做样本。
