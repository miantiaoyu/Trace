# 项目状态

## 项目定位

Trace 当前从 ERP 源表读取拼柜号、船司和柜号，按船司选择已验证的官网 HTTP/浏览器路线，输出统一 JSON 报告；可选将最新快照写入 `oms.headway`，不修改 ERP 源表。

## 当前功能

- 新增 `crawler_lab/browser_dom_probe.py`：通过官方 URL 参数读取 COSCO 与 ONE 的结构化 DOM 事件表，并校验柜号回显和页面结果契约。
- 新增 `PROJECT_EXPERIENCE.md`，维护船司路径发现、DOM Provider 容错和排查结论。
- 已验证 SM Line（SML）公开柜号查询：通过临时 `JSESSIONID` 会话可获取状态、船期和轨迹明细原始 JSON。
- 新增 `crawler_lab/sm_line_probe.py`，按官网页面定义的会话和请求顺序进行低频查询。
- 已验证阳明海运（YML）官网公开查询接口：可用柜号直接获取原始 JSON，无需 API 凭证。
- 新增 `crawler_lab/yang_ming_probe.py`，调用
  `https://www.yangming.com/api/CargoTracking/GetTracking` 并打印 `ctStatusInfo` 和
  `dcsaStatusInfo` 原始返回。
- 已验证长荣海运（Evergreen）官网公开柜号查询：通过普通 HTTP POST 获取结果页，可提取柜型、最新动态和地点，无需浏览器或验证码。
- 新增 `crawler_lab/evergreen_probe.py`，以表头和柜号回显作为结果契约，避免依赖页面视觉坐标。
- 已验证马士基（Maersk）官网追踪页：可在新浏览器会话中获得页面自身请求的完整原始 JSON，包含起讫港、集装箱事件、船名航次、状态与 ETA。
- 新增 `crawler_lab/maersk_probe.py`，等待官网页面的 `/synergy/tracking/` 响应并校验柜号回显；不提取或伪造 API 凭证。
- 已验证 MSC 官网追踪页：可通过标准浏览器输入柜号并捕获页面自身 `TrackingInfo` 响应，返回原始 JSON，包含提单号、起讫港、事件、船名航次与 ETA。
- 新增 `crawler_lab/msc_probe.py`，使用 Playwright 驱动官网表单并等待 `/api/feature/tools/TrackingInfo` 的 `POST 200` 响应；默认使用可见浏览器，支持切换 `chromium` 或 `msedge`。
- 已验证万海（Wan Hai）官网查询：`cec/#/cargotracking` 新站入口在当前环境会先经过前置校验，但同一浏览器会话预热旧站后，可进入 `tracking_query.xhtml` 并通过标准表单 POST 取得集装箱列表结果。
- 新增 `crawler_lab/wan_hai_probe.py`，先用 Playwright 预热官网会话，再以低频 HTTP POST 提交柜号查询，打印结果表头与原始行数据；如果结果行中带出 Booking/B/L 编号，会继续用官网 `Book No. / BL no.` 模式查询一层摘要。
- 已验证 HMM 官网新版 Track & Trace：有界 Chromium 可直接按柜号查询，页面 `POST /e-service/general/trackNTrace/selectTrackNTrace.do` 返回追踪 HTML，包含节点、集装箱动态、船名航次与 ETA。
- `crawler_lab/hmm_probe.py` 使用官网页面生成的 CSRF 表单请求，输出结构化结果表和原始 HTML；同时输出表头与区块识别诊断，柜信息表契约变化时明确失败。HMM 明确不使用无头浏览器。

- 当前数据库方向固定：使用 `prod-db.yml` 只读查询阿里正式 ERP，使用 `test-db.yml` 写入内网测试 `oms.headway`；不提供测试/正式模式切换。
- `oms.headway` 建表定义已包含表备注和全部字段的中文备注；已建表可通过 `sql/headway_add_comments.sql` 只补充备注。
- 支持从 `trobs.po_cabinet_combination.cabinet_no` 查询最近 N 天的柜号，按 `update_time DESC, id DESC` 排序并按拼柜号聚合；`shipping_order` 是订舱号，不用于当前柜号追踪。
- 柜号在路由前统一清理空白、转为大写并校验 ISO 6346 格式及校验位；无效柜号返回 `source_data_error`，不访问船司官网且不写入 `oms.headway`。
- 阳明 ETA 会去除 `ETA at <port>:` 文本前缀后再转换为数据库时间；长荣可容错真实页面的合并表头，并提取当前状态、地点、船名航次和页面 ETA。
- `query_failed` 会写入失败摘要并将 `next_query_at` 设为一小时后；到期后重新入选，成功时按原拼柜号 upsert 业务快照并清除旧错误。
- 有限 `--limit` 时已到期的重查记录优先于 ERP 新单，避免失败记录在持续新单下长期饥饿；HMM 瞬时失败的第二次尝试使用 20–25 秒退避。
- 支持完整船司字段归一化，已覆盖数据库常见的中英文、简称、BCO/NVO 写法；HMM 对历史乱码后缀使用 `HMM%` 数据库前缀兜底。
- 统一入口按船司路线执行最低访问间隔、硬超时和有限重试；每次查询在独立 Provider 子进程中运行，超时会终止该次进程，避免浏览器和网络请求残留。查询、路由和归一化均按单柜隔离，单条异常不会终止整个批次。
- 统一摘要由 Pydantic 数据契约校验，当前 schema 为 `1.2`；新增实际出发时间、最终卸船港和目的港实际卸船标志，未知字段和非法类型会在归一化边界明确失败。
- 统一入口提供跨平台任务锁，默认使用 `.trace-api-probe.lock` 防止两次定时任务重叠；可选输出脱敏 JSONL 运行指标和船司连续失败状态。运行日志不包含柜号、原始响应或数据库连接信息。
- 瞬时故障重试采用指数退避与随机抖动，并同时遵守同船司最小访问间隔；执行元数据保留每次重试等待时长。
- HMM、长荣和万海的 HTML 表格统一由 Selectolax 容错解析，仍以表头、柜号回显和关键区块作为页面契约，不依赖表格序号或视觉坐标。
- 输出同时保留 `raw` 原始返回和 `normalized` 固定摘要。已接入的阳明、SM Line、长荣、COSCO、ONE、马士基、MSC、万海、HMM 均有统一事件映射；来源能区分时输出 `ACTUAL/EXPECTED`，并分别计算 `current` 与 `next_expected`。
- 归一化异常返回 `partial_success` 并保留原始数据；未预期路由异常返回 `internal_error`。报告汇总分别统计成功、部分成功、跳过和失败；纯跳过轮次不增加连续失败次数。
- 新增 `trace_api_probe/tracking.py` 统一路由模块：
  - 阳明、SM Line、长荣、COSCO、ONE、马士基、MSC、万海、HMM 进入已验证路线。
  - CMA CGM、OOCL、ZIM、TS Lines、Hapag-Lloyd、KMTC、SeaLead、APL 返回明确的路线不可用状态。
- `python -m trace_api_probe` 是统一入口，单条失败会进入结果报告并继续后续柜号。
- 支持命令行手动传入柜号，跳过数据库取样本。
- 输出包含查询条件、汇总统计、数据库样本信息、路线、状态、错误和 `raw` 原始返回。
- 新增 `crawler_lab/` 实验目录，用于验证爬虫和网页自动化路线。
- 已验证维运网公开页面可用纯 HTTP 读取，并能从前端 JS 中抽取接口线索。
- 已验证维运网公开 API 可返回船司来源表、柜号格式识别结果和船司官网跳转链接。

## 技术栈与运行方式

- Python 命令行工具。
- 运行依赖：`PyMySQL`、`Playwright`、`Pydantic`、`filelock`、`Selectolax`。
- 测试使用 Python 标准库 `unittest`，覆盖任务锁、ISO 6346 柜号校验、跳过状态、脱敏日志、连续失败告警、指数退避和随机抖动。
- 支持用户本机 Conda `py312` 环境，也提供包含 Chromium 与 Xvfb 的 Docker/Compose 运行包。

## 关键目录/文件

- `trace_api_probe/`：命令行工具源码。
- `crawler_lab/`：爬虫与网页自动化实验脚本。
- `tests/`：单元测试。
- `requirements.txt`：运行依赖。
- `.gitignore`：忽略本地敏感配置和 Python 缓存。
- `prod-db.yml`：阿里正式 ERP 只读连接配置，不提交。
- `test-db.yml`：内网测试 `oms.headway` 写入连接配置，不提交。
- `Dockerfile`、`docker-compose.yml`：服务器批处理部署定义；源和目标数据库配置通过两个 Compose secret 只读挂载。
- `sql/headway.sql`、`sql/headway_add_comments.sql`、`trace_api_probe/headway.py`：头程当前快照表、已建表备注补齐脚本和 upsert 写入逻辑。

## 当前限制

- 命令行默认每次最多查询 20 个去重柜号；传 `--limit 0` 查询最近窗口内的全部柜号。上线 wrapper 默认使用 `--days 60 --limit 0`，ERP 新单只补 `headway` 中不存在的拼柜号，已入表未到达记录按 `next_query_at` 到期重查。
- 不做可视化；默认不写库，`--persist` 只更新 `oms.headway` 当前快照，不写 ERP 源表；原始 JSON 只保留最新一次。
- 维运网目前只验证到“识别/跳转链接生成”，未直接返回集装箱轨迹事件。
- MSC 当前走的是官网标准页面流程，不是公开 API 凭证接入；结果仍受官网页面结构、Cookie 弹窗和低频访问策略影响。
- 万海当前走的是“标准浏览器预热 + 官网表单 POST”路径，不依赖维运网，也不绕过官网校验脚本；但新站 `cec` 入口和 Booking/B/L 弹窗 redirect 页在当前环境仍不适合作为直接抓取入口。
- 万海当前可能返回 Incapsula 拦截页或在页面导航阶段挂起；程序会识别明确拦截页，其余情况仍由 Provider 硬超时终止并记为可到期重查的 `query_failed`。
- 万海在 2026-07-14 的真实回归中有界模式成功，无头模式停留在官网入口校验页；Linux 服务器运行万海时也应通过 Xvfb 提供虚拟显示器。
- HMM 当前必须使用有界浏览器；Linux 服务器需通过 Xvfb 提供虚拟显示器，传 `--headless` 会明确失败。
- Docker 运行包默认使用非 root 用户、只读根文件系统和资源限制，不暴露 HTTP 端口；Chromium 临时配置写入可写 `/tmp`，状态文件写入独立 Docker volume。
- 提供 Docker Compose 一次性容器运行方式；完整查询结果不进入调度日志，脱敏指标保存在状态卷。
- 源和目标连接分别使用固定的 `prod-db.yml` 和 `test-db.yml`，兼容简单 key/value 和 Spring `jdbc:mysql://` 数据源格式；不提供命令行或环境变量切换入口。
- 提供 XXL-JOB `SHELL` 任务 wrapper，测试环境可由统一调度平台调用 Docker 批处理，不要求 Python 进程注册为 Java executor。
- 测试配置模板使用 `oms` 数据库；`--persist` 模式按拼柜号 upsert `oms.headway`，不写 ERP 源表。
- 无效柜号返回 `source_data_error`，未适配船司返回 `route_unavailable`，无法识别船司返回 `unsupported_carrier`；三者计入 `skipped`，保留在本轮报告和逐条诊断日志中，但不写入 `oms.headway`。
- 支持 `--detail-log` 写入逐条 JSONL 诊断日志，记录样本、路线、错误摘要、核心字段缺失和写库决策；不保存官网 raw 原始响应。

## 最近验证

- 最近 7 天真实样本已成功验证：阳明、COSCO、ONE、马士基、HMM。
- SM Line、长荣、MSC、万海在该时间窗口无可用样本，未计为失败。
- 2026-07-14 对 3 个马士基真实样本核对了 JSON 顶层、柜、地点和事件字段，结构一致；事件同时包含 `ACTUAL` 与 `EXPECTED`。
- 2026-07-14 对 5 个 HMM 真实样本覆盖提空箱、进场、转运港卸船和转运港再装船状态；页面包含 8 至 9 张表，核心区块表头结构一致。增强解析后又对近期与转运样本完成官网回归。
- 2026-07-14 完成马士基时间语义回归：最新 `ACTUAL` 为当前状态，最早后续 `EXPECTED` 为下一预计节点，不再依赖官网数组顺序。
- 2026-07-14 使用真实官网样本完成 SM Line、长荣、MSC、万海统一映射回归。SM Line 与 MSC 可区分实际/预计事件；长荣来源未提供事件类型；万海当前列表提供最新实际状态并由 Booking 摘要补船名航次。
- 2026-07-14 完成已接入船司的运输阶段样本验证，结果记录于 `TRACKING_STAGE_VALIDATION_REPORT.md`。马士基、HMM、ONE、COSCO、阳明、MSC 覆盖发船前、在途和已到目的地；长荣缺发船前样本，万海缺发船前和明确在途样本，SM Line 仅有一个发船前数据库样本。
- 阶段验证期间补齐万海数据库别名、柜号内部空格清理、ONE Actual/Estimated 与上下文继承、COSCO 制表符拆分、阳明 DCSA 事件映射及过期预计节点过滤。
- 2026-07-14 完成 Selectolax 迁移后的官网回归：HMM 返回 9 张表并提取 2 个事件，长荣返回 1 条结果行，万海有界模式返回 1 条最新状态；统一摘要均通过 Pydantic schema `1.1` 校验。

## 90 天订单基线

统计口径：只读查询 `trobs.po_cabinet_combination`，筛选 `update_time` 最近 90 天且 `cabinet_no` 非空；订单量为记录数，柜量按 `cabinet_no` 去重。统计日期：2026-07-14。

| 船司 | 订单量 | 去重柜量 | 官网路线状态 |
| --- | ---: | ---: | --- |
| HMM | 417 | 416 | 可获取 |
| 马士基 | 225 | 225 | 可获取 |
| 万海 | 63 | 63 | 可获取 |
| OOCL | 59 | 59 | 不可获取：Cloudflare Turnstile |
| CMA CGM | 52 | 51 | 不可获取：暂无稳定官网路线 |
| Hapag-Lloyd | 51 | 51 | 不可获取：Cloudflare |
| ONE | 51 | 51 | 可获取 |
| COSCO | 41 | 41 | 可获取 |
| 长荣 | 39 | 39 | 可获取 |
| 阳明 | 33 | 33 | 可获取 |
| MSC | 21 | 21 | 可获取 |
| ZIM | 6 | 6 | 不可获取：Cloudflare |
| APL | 1 | 1 | 不可获取：暂无稳定官网路线 |
| KMTC | 0 | 0 | 不可获取：Akamai |
| SeaLead | 0 | 0 | 不可获取：官网服务维护 |
| SM Line | 0 | 0 | 可获取，但无 90 天样本 |
| TS Lines | 0 | 0 | 不可获取：验证码 |

## 已知风险

- 官网页面路线受页面结构、Cookie 弹窗、浏览器环境、验证码、CDN 策略和官网维护状态影响；结果中会保留失败原因。
- `prod-db.yml` 包含敏感信息，应只保留在本地并由 `.gitignore` 排除。
- `test-db.yml` 与正式配置一样只保留在对应服务器；`test-db.yml.example` 不含真实密码。
- `headway` 结果表需要先在目标环境执行 `sql/headway.sql`，并使用具备该表写权限的数据库账号。

## 给下一个模型的快速上下文

运行前先安装依赖，然后使用 `python -m trace_api_probe --days 7 --limit 1` 验证统一入口。该命令只读 ERP 源表并在控制台输出 JSON 报告；定时落库任务额外传入 `--persist`。
