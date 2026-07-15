# 用户手册

## 项目简介

Trace 是一个只读的船司 Track & Trace 查询工具。它从公司只读库读取最近订单中的船司和柜号，根据船司进入不同的官网 HTTP/浏览器路线，并在控制台输出统一 JSON 报告。

## 安装/准备

请在本机 Conda `py312` 环境中安装依赖：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

根目录需要有本地配置文件：

```text
prod-db.yml
```

该文件只用于读取公司只读库连接信息，不应修改或提交。

## 启动/使用

查询最近 7 天订单，最多处理 20 个去重柜号：

```bash
python -m trace_api_probe
```

只查询某一家船司：

```bash
python -m trace_api_probe --carrier YML --days 7 --limit 1
```

使用无界面浏览器运行支持无头模式的网页路线，例如 MSC：

```bash
python -m trace_api_probe --carrier MSC --headless --limit 1
```

万海当前需要有界浏览器。在 Linux 无桌面服务器上与 HMM 一样通过 Xvfb 运行：

```bash
xvfb-run -a python -m trace_api_probe --carrier WAN_HAI --days 7 --limit 1
```

HMM 必须使用有界浏览器，不要传 `--headless`：

```bash
python -m trace_api_probe --carrier HMM --days 7 --limit 1
```

Linux 服务器没有图形桌面时，通过 Xvfb 提供虚拟显示器：

```bash
xvfb-run -a python -m trace_api_probe --carrier HMM --days 7 --limit 1
```

## Docker 安全部署

项目提供了包含 Python、Playwright Chromium、Xvfb 和系统字体的镜像。它是一次性批处理容器，不是 HTTP 服务，不需要开放端口。镜像默认通过 Xvfb 启动，因此 HMM 和万海的有界浏览器路线可以直接运行。

在服务器上准备 Docker Engine 和 Compose plugin 后，将本仓库与未提交的 `prod-db.yml` 放在同一目录，执行：

```bash
docker compose build
docker compose run --rm trace
```

`prod-db.yml` 只作为 Compose secret 以只读方式挂载到容器，不会复制进镜像。容器默认使用非 root 用户、只读根文件系统、独立临时文件系统、禁止提权、丢弃 Linux capabilities，并限制 1 GiB 内存和 256 个进程。脱敏运行日志、连续失败状态和任务锁保存在 Docker volume `trace_state` 中；不需要状态时可以用 `docker compose down -v` 清理。

默认命令查询最近 7 天最多 20 个柜号。临时联调可以覆盖参数，例如：

```bash
docker compose run --rm trace --carrier HMM --limit 1
docker compose run --rm trace --carrier MSC --headless --limit 1
docker compose run --rm trace --container HMMU4706485 --carrier HMM
```

生产环境建议使用宿主机 systemd timer 或受控的 CI 定时触发 `docker compose run --rm trace`，并限制服务器出站访问范围；不要把 `prod-db.yml` 写入镜像、提交 Git 或放进公开日志。该容器没有 Web API，若需要浏览器界面或远程调用，应另行设计鉴权层，不要直接把 CLI 暴露到公网。

### 查看运行效果

当前项目没有网页界面。人工验证时，直接运行一条低频查询，终端会打印包含 `summary`、`normalized` 和 `raw` 的完整 JSON：

```bash
cd /opt/trace
docker compose build
docker compose run --rm trace --carrier HMM --limit 1
```

完整 JSON 包含柜号和官网原始响应，只应在受控终端查看，不要转发到公开日志。命令结束后容器自动删除；Docker 镜像和 `trace_state` 状态卷会保留。

定时任务默认不把完整 JSON 写入 systemd journal。查看最近 20 次脱敏运行指标：

```bash
cd /opt/trace
docker compose run --rm --no-deps -T --entrypoint sh trace \
  -c 'tail -n 20 /var/lib/trace/trace-runs.jsonl'
```

每行包含运行时间、查询范围、成功/失败数量、重试次数和平均耗时，不包含柜号、原始响应或数据库凭证。

### 配置 systemd 定时运行

仓库提供的模板假定项目位于 `/opt/trace`，并且 `docker` 位于 `/usr/bin/docker`。如果服务器路径不同，先修改 `deploy/systemd/trace.service` 中的 `WorkingDirectory`、`ConditionPathExists` 和 Docker 路径。

安装并启动定时器：

```bash
cd /opt/trace
sudo install -m 0644 deploy/systemd/trace.service /etc/systemd/system/trace.service
sudo install -m 0644 deploy/systemd/trace.timer /etc/systemd/system/trace.timer
sudo systemctl daemon-reload
sudo systemctl enable --now trace.timer
```

默认每天北京时间 02:10 触发，并随机延迟最多 5 分钟；服务器错过执行时间后会在下次启动时补跑一次。首次部署应先手动触发并观察：

```bash
sudo systemctl start trace.service
sudo systemctl status trace.service --no-pager
sudo journalctl -u trace.service -n 100 --no-pager
systemctl list-timers trace.timer
```

`trace.service` 是一次性任务，成功结束后显示 `inactive (dead)` 属于正常现象，退出码应为 0。查询出现部分成功或失败时程序退出码为 1，systemd 会将本轮标记为失败；详细的脱敏统计仍可从 `trace-runs.jsonl` 查看。

修改执行时间时编辑 `/etc/systemd/system/trace.timer` 的 `OnCalendar`，然后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart trace.timer
systemctl list-timers trace.timer
```

暂停定时运行：

```bash
sudo systemctl disable --now trace.timer
```

手动指定柜号进行单条联调，不读取数据库：

```bash
python -m trace_api_probe --carrier YML --container YMMU7349033
```

`--limit 0` 表示不限制最近时间窗口内的记录数。入口会按 `update_time DESC, id DESC` 读取 `trobs.po_cabinet_combination`，删除柜号中的空白字符后转为大写，并按规范化柜号去重。程序不会写库，也不会保存返回文件。

批量运行会按船司路线使用默认的最小访问间隔、超时和重试策略。可按本次命令覆盖默认值：

```bash
python -m trace_api_probe --timeout-seconds 90 --max-attempts 2 --min-interval-seconds 5
```

统一摘要使用 Pydantic schema `1.1` 做严格校验。命令行输出仍是普通 JSON，调用方接口不需要依赖 Pydantic；契约不匹配会被隔离为当前柜号的 `partial_success`，并保留已经取得的 `raw`。

## 定时任务保护与运行观测

统一入口默认创建 `.trace-api-probe.lock` 任务锁。上一轮仍在运行时，新一轮会立即以明确错误退出，避免两个批次同时访问官网。可用 `--lock-timeout-seconds` 设置等待时间，或用 `--lock-file` 指定服务器上的固定锁路径。

以下命令额外写入脱敏 JSONL 指标和船司健康状态：

```bash
python -m trace_api_probe --days 7 --limit 20 \
  --run-log var/trace-runs.jsonl \
  --health-state var/trace-health.json \
  --alert-threshold 3
```

运行日志只记录查询范围、成功/失败数量、尝试次数、重试次数和耗时，不记录柜号、原始响应或数据库连接信息。某船司连续达到 3 轮没有成功结果时，报告的 `alerts` 字段和标准错误会输出告警。默认不传 `--run-log` 与 `--health-state` 时不写这些文件。

输出报告包含 `query`、`summary` 和 `results`。`summary` 分别统计 `success`、`partial` 和 `failed`。每条 `results` 记录包含数据库样本信息、归一化船司、路线、执行次数、状态、`normalized` 统一摘要和 `raw` 原始返回；网页受限、超时或解析异常只影响当前柜号，不会让其他记录消失。

`normalized` 的固定字段包括：

```text
current: 当前时间、状态、地点、运输方式
next_expected: 下一条预计事件
vessel: 船名、航次、IMO
origin / destination / destination_eta
events: 统一事件列表；每条事件包含 time_type、船名、航次和 IMO 等来源字段
coverage: 当前来源实际提供了哪些字段
```

原始 `raw` 永远保留。字段不足时摘要填 `null` 或空数组，不能用推测值补齐。

各船司发船前、在途和已到目的地阶段的真实样本覆盖情况见 `TRACKING_STAGE_VALIDATION_REPORT.md`。该报告只保存脱敏状态和字段结构，不保存完整生产柜号或原始 HTML。

事件时间类型：

- `ACTUAL`：船司确认已经发生的事件，可以用于判断当前状态。
- `EXPECTED`：船期、ETA 或系统预测的未来事件，可能随航线和港口情况变化，不能当作当前位置。
- `null`：来源没有提供足够信息区分实际与预计，程序不自行猜测。

当来源同时提供两类事件时，`current` 取时间最新的 `ACTUAL`，`next_expected` 取当前状态之后时间最早的 `EXPECTED`。顶层船名航次优先来自当前实际事件，其次来自下一预计事件。

## 查询状态与故障隔离

- `success`：官网查询和统一解析均成功。
- `partial_success`：官网原始数据已经取得，但统一解析发生异常；保留 `raw` 和空摘要，后续柜号继续执行。
- `query_failed`：当前柜号的官网查询失败或重试耗尽。
- `internal_error`：当前柜号发生未预期的路由异常；异常被单柜隔离，后续柜号继续执行。
- `route_unavailable`：船司已识别，但没有稳定自动化路线。

每个真实查询在独立 Python 子进程中运行。超过硬超时后父进程会终止该子进程，浏览器崩溃或页面卡死不会阻塞整个批次。

## 默认限速与重试

| 路线 | 最小间隔 | 单次硬超时 | 最大尝试次数 |
| --- | ---: | ---: | ---: |
| 阳明、SM Line、长荣 | 2 秒 | 45 秒 | 2 |
| COSCO、ONE | 4 秒 | 60 秒 | 2 |
| 马士基、MSC | 6 秒 | 90 秒 | 2 |
| 万海 | 8 秒 | 120 秒 | 1 |
| HMM | 12 秒 | 90 秒 | 2 |

只有可恢复错误才重试，包括硬超时、连接中断、浏览器访问失败、HTTP 429 和 HTTP 5xx。柜号无数据、页面契约变化、参数错误、验证码或访问拒绝不会重试。重试等待采用指数退避并加入最多 1 秒随机抖动，同时取同船司剩余限速时间与退避时间的较大值；默认退避从 2 秒开始，最大 30 秒，没有无限重试。实际等待时长记录在 `execution.retry_delays_seconds`。

## 常见问题

### 会写公司数据库吗？

不会。程序只读取 `trobs.po_cabinet_combination`，不执行写入语句。

### 会爬船司网页吗？

部分路线会通过标准 HTTP 或 Playwright 读取船司官网公开查询结果；不绕验证码、不导出或复用外部 Cookie、不伪造返回。

### 会保存返回文件吗？

默认不会，只在控制台输出 JSON 报告。显式传入 `--run-log` 或 `--health-state` 时只保存脱敏运行指标和连续失败计数，不保存柜号或官网原始返回。

## 爬虫实验

维运网页面探测：

```bash
python crawler_lab/http_probe.py
```

抽取维运网前端接口线索：

```bash
python -m crawler_lab.endpoint_probe
```

调用维运网识别/跳转链接接口：

```bash
python -m crawler_lab.weiyun_api_probe --number CMAU4616180
python -m crawler_lab.weiyun_api_probe --number GVTU5148354 --carrier-code MSK
```

查看维运网船司来源表：

```bash
python -m crawler_lab.weiyun_carriers
```

当前维运网实验结论：它可以识别柜号格式、对部分柜号自动识别船司、返回船司来源表，并生成船司官网查询链接；它不是直接返回轨迹事件的数据源。使用优先级是自动识别优先，船司映射表兜底。

### 长荣官网查询

长荣支持直接按柜号查询，无需 API 凭证：

```bash
E:\miniconda\envs\py312\python.exe -m crawler_lab.evergreen_probe --container EGHU9204414
```

命令会打印官网结果表的表头和数据行。当前验证返回柜型、最新动态和地点。

### 马士基官网查询

马士基无需 API 凭证，可通过官网追踪页读取该页面返回的原始 JSON：

```bash
E:\miniconda\envs\py312\python.exe -m crawler_lab.maersk_probe --container GVTU5148354
```

输出包含始发地、目的地、集装箱事件、船名航次、状态和 ETA。该命令需要 Playwright Chromium，且不会保存 Cookie 或结果文件。

### MSC 官网查询

MSC 可通过官网标准查询页读取页面自身返回的原始 JSON：

```bash
E:\miniconda\envs\py312\python.exe -m crawler_lab.msc_probe --container TLLU8937468
```

默认使用可见浏览器，尽量贴近人工查询流程。如果想改用系统 Edge：

```bash
E:\miniconda\envs\py312\python.exe -m crawler_lab.msc_probe --container TLLU8937468 --browser-channel msedge
```

输出为官网 `TrackingInfo` 的原始 JSON，当前已验证包含提单号、起讫港、事件、船名航次和 ETA。脚本只读取页面自身返回的数据，不导出 Cookie，不做请求头伪装，也不保存本地结果文件。

### HMM 官网查询

HMM 的新版 Track & Trace 支持直接按柜号查询，统一入口会使用页面自身的 CSRF 表单请求并返回结果表及原始 HTML：

```bash
python -m crawler_lab.hmm_probe --container HMMU4706485
```

当前 HMM 在无头浏览器模式下无法稳定访问，脚本会拒绝 `--headless`。服务器需要运行在 Windows 桌面会话，或 Linux 的 Xvfb 虚拟显示器中；不需要人工点击或登录。

HMM 的 `normalized` 会提取始发地、目的地、目的地 ETA、船名、航次和轨迹事件。事件表 `Mode` 列如果是船名航次，例如 `GSL CHLOE 2610N`，会转换为 `mode=Vessel`、`vessel=GSL CHLOE`、`voyage=2610N`。

HMM 的 `raw.parse_diagnostics` 会列出页面表格数量、表头，以及是否识别到航线、柜摘要、船舶航段和事件区块。柜摘要契约缺失时查询会明确失败，避免官网改版后静默输出空结果。

### 万海官网查询

万海当前可用的是官网旧站路径，不直接抓 `cec/#/cargotracking`：

```bash
E:\miniconda\envs\py312\python.exe -m crawler_lab.wan_hai_probe --container WHSU6376250
```

脚本会先用标准浏览器会话预热官网，再向 `tracking_query.xhtml` 发送标准表单 POST。当前已验证能返回结果表头和原始数据行，包含柜号、时间、当前状态、堆场/码头、航次、船名和 More detail 文本。如果 More detail 中带出 Booking/B/L 编号，脚本会继续查询一层摘要，返回装船日期、航次和船名。

## 注意事项

- 不要提交 `prod-db.yml`。
