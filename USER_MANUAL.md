# 用户手册

## 项目简介

Trace 是一个只读的船司 Track & Trace 查询工具。它从公司只读库读取最近订单中的船司和柜号，根据船司进入不同的官网/API 路线，并在控制台输出统一 JSON 报告。

## 安装/准备

请在本机 Conda `py312` 环境中安装依赖：

```bash
pip install -r requirements.txt
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

使用无界面浏览器运行 MSC、万海等网页路线：

```bash
python -m trace_api_probe --carrier MSC --headless --limit 1
```

手动指定柜号进行单条联调，不读取数据库：

```bash
python -m trace_api_probe --carrier YML --container YMMU7349033
```

`--limit 0` 表示不限制最近时间窗口内的记录数。入口会按 `update_time DESC, id DESC` 读取 `trobs.po_cabinet_combination`，并按柜号去重。程序不会写库，也不会保存返回文件。

输出报告包含 `query`、`summary` 和 `results`。每条 `results` 记录包含数据库样本信息、归一化船司、路线、状态和 `raw` 原始返回；网页受限或凭证缺失时会在对应记录中返回错误，不会让其他记录消失。

## API 凭证

当前 CMA CGM 仍走官方 API 凭证路线，未配置时对应记录会返回缺少凭证的错误。其他已验证船司优先走官网公开页面或官网自身请求，不需要额外 API 凭证。

支持的环境变量：

```text
MAERSK_API_KEY
MAERSK_CLIENT_ID
MAERSK_BEARER_TOKEN
MAERSK_TRACK_TRACE_URL
CMA_CGM_API_KEY
CMA_CGM_BEARER_TOKEN
CMA_CGM_TRACK_TRACE_URL
MSC_API_KEY
MSC_BEARER_TOKEN
MSC_TRACK_TRACE_URL
```

## 常见问题

### 会写公司数据库吗？

不会。程序只读取 `trobs.po_cabinet_combination`，不执行写入语句。

### 会爬船司网页吗？

部分路线会通过标准 HTTP 或 Playwright 读取船司官网公开查询结果；不绕验证码、不导出或复用外部 Cookie、不伪造返回。

### 会保存返回文件吗？

不会，只在控制台输出 JSON 报告。

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

### 万海官网查询

万海当前可用的是官网旧站路径，不直接抓 `cec/#/cargotracking`：

```bash
E:\miniconda\envs\py312\python.exe -m crawler_lab.wan_hai_probe --container WHSU6376250
```

脚本会先用标准浏览器会话预热官网，再向 `tracking_query.xhtml` 发送标准表单 POST。当前已验证能返回结果表头和原始数据行，包含柜号、时间、当前状态、堆场/码头、航次、船名和 More detail 文本。如果 More detail 中带出 Booking/B/L 编号，脚本会继续查询一层摘要，返回装船日期、航次和船名。

## 注意事项

- 不要提交 `prod-db.yml`。
- 不要把 API 凭证写入 `prod-db.yml`。
- 船司实际开通后的 API 地址或认证头可能不同，可通过环境变量覆盖默认地址。
