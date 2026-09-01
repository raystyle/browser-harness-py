# S007 会话 cookie 跨设备迁移研究

> 研究原型过程（为什么）。登记日 2026-09-01。
> 来源：WSL2 无头栈 + Windows agent Chrome 实测（Chrome 152 / 154）。

## 结论速览

- **agent Chrome → agent Chrome 的会话 cookie 迁移可行**：`Storage.getCookies` 导出 → 文件 → `Storage.setCookies` 导入，X 登录态（auth_token/ct0/twid）跨机生效。[实证: 2026-09-01 Windows 9223 导出 12 条 x.com/twitter.com cookie，导入 WSL 9224 后 x.com/home 停在主页、账号切换按钮存在，未被重定向到登录页]
- **S004 的「CDP cookie 导出导入不推荐」结论有适用边界**：那次失败是默认 profile 的 M144「Allow remote debugging」弹窗拦了 ws 连接；两端都是专用 agent Chrome（`--remote-debugging-port` + 独立 user-data-dir）时根本没有这个门。S004 的结论修正为「默认 profile 不可行，专用 profile 可行」。[实证: WSL 直连 9223 Storage.getCookies 一次成功]
- mirrored 网络（WSL2）下导出甚至不需要跨机拷文件：WSL 直接连 `127.0.0.1:9223` 读 Windows 侧 agent Chrome。跨物理机时拷 `.json` 文件即可。

## 落地形态

`browser-harness cookies` 应用（apps/cookies.py，2026-09-01 进 main）：

```bash
browser-harness cookies export --domain x.com --domain twitter.com   # 从 BH_COOKIE_EXPORT_ENDPOINT（默认 9223）
browser-harness cookies import --file <path>                          # 到 BU_CDP_URL（本机 agent Chrome）
```

- 文件格式 `browser-harness-cookies/1`，0600 权限，落 `<BH_HOME>/cookies-<host>-<ts>.json`，gitignore 双模式兜底。
- 导出默认拒绝全量导（防整站会话意外落盘），要 `--domain` 或显式 `--all`。
- 导入后**复读验证**（set 后 getCookies 对账 name+domain+path），返回 `N/M`；批量 `Storage.setCookies` 失败自动降级逐条 `Network.setCookie`。
- sanitize：只透传 set 系字段（size/session/sourceSnapshotURL 是只读输出字段）；sameSite 仅接受 Strict/Lax/None。

## 注意事项

- 同一 X 账号在两台 agent Chrome 同时登录是两个并发会话，x-monitor 双侧同跑会重复抓取且互相抢限流；迁移后应只在一侧跑监控。[推断: 未实测双跑]
- cookie 有时效（X 会话约数月），过期重导即可；`auth_token` 是等效密码，文件即凭证，勿提交勿外传。[经验]
- `Network.setCookie`/`Storage.setCookies` 对 partitionKey（CHIPS）cookie 的接受度随版本波动，导入对账的 `N<M` 场景多为这类记录，重试通常无解、影响面小。[推断: 本轮 12 条全过，未覆盖失败样本]
