# 项目状态

## 项目定位

Trace 当前是一个只读的船司 Track & Trace 查询工具：从公司只读库读取最近订单中的船司和柜号，按船司选择已验证的官网/API 路线，输出统一 JSON 报告和原始返回数据。

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

- 支持从根目录 `prod-db.yml` 读取公司只读库连接配置。
- 支持从 `trobs.po_cabinet_combination` 查询最近 N 天的有效柜号，按 `update_time DESC, id DESC` 排序并按柜号去重。
- 支持完整船司字段归一化，已覆盖数据库常见的中英文、简称、BCO/NVO 写法。
- 新增 `trace_api_probe/tracking.py` 统一路由模块：
  - 阳明、SM Line、长荣、COSCO、ONE、马士基、MSC、万海进入已验证路线。
  - CMA CGM 进入官方 API 凭证路线。
  - OOCL、ZIM、TS Lines、Hapag-Lloyd、KMTC、SeaLead、HMM、APL 返回明确的路线不可用状态。
- `python -m trace_api_probe` 是统一入口，单条失败会进入结果报告并继续后续柜号。
- 支持命令行手动传入柜号，跳过数据库取样本。
- 输出包含查询条件、汇总统计、数据库样本信息、路线、状态、错误和 `raw` 原始返回。
- 缺少官方 API 凭证时会把凭证错误写入该条结果，不爬网页、不伪造返回、不写数据库。
- 新增 `crawler_lab/` 实验目录，用于验证爬虫和网页自动化路线。
- 已验证维运网公开页面可用纯 HTTP 读取，并能从前端 JS 中抽取接口线索。
- 已验证维运网公开 API 可返回船司来源表、柜号格式识别结果和船司官网跳转链接。

## 技术栈与运行方式

- Python 命令行工具。
- 运行依赖：`PyMySQL`。
- 测试使用 Python 标准库 `unittest`。
- 目标运行环境：用户本机 Conda `py312` 环境。

## 关键目录/文件

- `trace_api_probe/`：命令行工具源码。
- `crawler_lab/`：爬虫与网页自动化实验脚本。
- `tests/`：单元测试。
- `requirements.txt`：运行依赖。
- `.gitignore`：忽略本地敏感配置和 Python 缓存。
- `prod-db.yml`：本地只读数据库配置文件，必须只读使用，不提交。

## 当前限制

- 默认每次最多查询 20 个去重柜号；传 `--limit 0` 才查询最近窗口内的全部柜号。
- 第一版不做可视化、不落库、不保存 JSON 文件、不解析或标准化船司原始返回。
- 维运网目前只验证到“识别/跳转链接生成”，未直接返回集装箱轨迹事件。
- MSC 当前走的是官网标准页面流程，不是公开 API 凭证接入；结果仍受官网页面结构、Cookie 弹窗和低频访问策略影响。
- 万海当前走的是“标准浏览器预热 + 官网表单 POST”路径，不依赖维运网，也不绕过官网校验脚本；但新站 `cec` 入口和 Booking/B/L 弹窗 redirect 页在当前环境仍不适合作为直接抓取入口。

## 已知风险

- 官方船司 API 的实际认证方式可能因开通账号而异。
- 官网页面路线受页面结构、Cookie 弹窗、浏览器环境、验证码、CDN 策略和官网维护状态影响；结果中会保留失败原因。
- `prod-db.yml` 包含敏感信息，应只保留在本地并由 `.gitignore` 排除。

## 给下一个模型的快速上下文

运行前先安装依赖，然后使用 `python -m trace_api_probe --days 7 --limit 1` 验证统一入口。该命令只读公司数据库，逐条查询并在控制台输出 JSON 报告。
