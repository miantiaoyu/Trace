# 第三方集装箱追踪 API 可行性报告

更新时间：2026-07-10

## 结论摘要

如果官方船司 API 申请不到，第三方聚合 API 是最现实的替代路线。它比网页爬取稳定，也比逐家申请船司 API 快。当前最值得优先验证的是：

1. **ShipsGo**：价格公开、覆盖广、按 credit 计费，适合先低成本试跑。
2. **Terminal49**：API/数据能力强，覆盖北美进口链路尤其完整；价格公开但不便宜。
3. **Vizion**：文档和船司覆盖表清楚，覆盖你列的大多数船司；价格需要询价。
4. **SeaVantage**：功能完整，含 AIS/预测 ETA；但 API 在 Professional 档，需询价。

不建议第一批优先选 project44、FourKites 这类大型企业平台，除非你们后续要做完整供应链可视化、D&D、协同和 BI。它们通常销售周期长、报价不透明、集成重。

## 你的船司覆盖基准

本报告按你之前列出的船司检查：

- APL / CMA CGM
- COSCO
- Evergreen
- HMM
- Hapag-Lloyd
- KMTC
- MSC
- Maersk
- ONE
- OOCL
- SeaLead
- SM Line
- Wan Hai
- Yang Ming
- ZIM

## 价格与覆盖对比

| 服务商 | 公开价格 | API 是否明确 | 船司覆盖判断 | 适合程度 |
|---|---:|---|---|---|
| ShipsGo | 500 credits = 1000 美元；注册有 3 个免费 credit；1 次 tracking 消耗 1 credit | 明确有 Container Tracking API | 页面显示 160+ shipping lines，覆盖 MSC、Maersk、CMA、Hapag、COSCO、ONE、Evergreen、HMM、Yang Ming、Wan Hai、ZIM、OOCL、APL、KMTC、Sea Lead、SM Line 等 | 高 |
| Terminal49 | 免费档；Pay As You Go 为 10 美元/container；Enterprise 询价 | API 在 Pay As You Go/Enterprise 明确包含，免费档 API 受限 | 覆盖 98%+ 全球箱量；支持 CMA、COSCO、Evergreen、Hapag、HMM、Maersk、MSC、ONE、OOCL、SeaLead、SM Line、Wan Hai、Yang Ming、ZIM；KMTC 未在公开支持表中找到 | 高，但成本偏高 |
| Vizion | 公开文档显示 Core/Professional 功能差异，但未公开金额 | API 产品成熟，文档清楚 | 支持 98% 全球海运；支持 APL、CMA、COSCO、Evergreen、Hapag、HMM、KMTC、Maersk、MSC、ONE、OOCL、Sea-Lead、SM Line、Wan Hai、Yang Ming、ZIM；其中 Sea-Lead booking 不支持，SM Line booking coming soon | 高 |
| SeaVantage | Free 5 containers/月；Starter/Business 有公开月费；Professional 100+ containers/API 需联系销售 | API 只在 Professional 档明确可用 | 宣称 all major carriers / 50+ carriers；页面示例含 MSCU、MAEU、HLCU、CMAL、ONEY 等，未公开完整逐船司矩阵 | 中高 |
| GoComet | API 页面写明需联系销售 | 有 Container Tracking API | 宣称支持 hundreds of global carriers；未找到逐船司公开矩阵 | 中 |
| project44 | 需询价 | 有 Ocean Visibility API | 宣称 98%+ global ocean freight，直接集成/EDI/AIS/港口事件；未找到完整逐船司公开矩阵 | 中，偏企业级 |
| FourKites | 需询价 | 平台型能力强，但不是轻量 API 优先 | 宣称 Ocean Freight Visibility / Dynamic Ocean；未找到逐船司公开矩阵 | 中低，偏企业级 |
| MarineTraffic / Kpler Containers API | 需联系 sales@kpler.com | 有 Containers API，需 API key | 更偏 AIS + container intelligence；未找到完整船司覆盖矩阵 | 中，适合补 AIS/船位 |
| SeaRates | Web 追踪价格公开：29/99/279 美元每月；页面说明 web access 不适用于 integration | 集成/API 需另询 | 宣称 600+ supported carriers；但 API 价格和能力需确认 | 中低 |
| JSONCargo | 公开套餐：约 99/199/349 欧元/月，另有按 request 计价；页面宣称有 Container/Bill of Lading/Vessel API | API key 自助倾向较强 | 宣称覆盖 95% global carriers，支持 Maersk、CMA、COSCO、Hapag 等；需实测你列的小船司 | 中 |

## 单个平台分析

### 1. ShipsGo

**可行性：高。**

公开价格最清楚：ShipsGo pricing 页面显示 500 credits 总价 1000 美元，注册有 3 个免费 credit。其 FAQ 说明每次 tracking request 消耗 1 credit，按 B/L 查询时即使一票多柜也只消耗 1 credit，credit 有效期 1 年。

**覆盖：高。**

ShipsGo carrier 页面列出 160+ shipping lines，并在页面中能看到你列的大多数船司：MSC、Maersk、CMA CGM、Hapag-Lloyd、COSCO、ONE、Evergreen、HMM、Yang Ming、Wan Hai、ZIM、OOCL、APL、KMTC、Sea Lead、SM Line。

**风险点：**

- 要确认 API 是否能直接按 container number 查询并返回原始事件，而不是只创建 tracking 任务后异步更新。
- credit 计费模型对批量历史数据不一定便宜。
- 需要确认同一个柜号重复查询是否重复扣 credit，还是创建后可无限刷新。

**技术问题：**

- 适合新增 `ShipsGoProvider`。
- 当前项目已有“读库取柜号 -> Provider -> 打印 JSON”的结构，接入成本低。
- 需要先用 3 个免费 credit 试 3 家船司的真实柜号。

### 2. Terminal49

**可行性：高，但成本偏高。**

Terminal49 pricing 页面显示免费档、Pay As You Go 和 Enterprise。Pay As You Go 为 10 美元/container，包含 API endpoints 和 webhooks；免费档有 container tracking，但 API endpoints 标为 limited。页面中“免费每月 50 shipments”和功能区“Track 10 shipments each month”存在口径不一致，需要向销售确认。

**覆盖：高，但注意 HMM/KMTC。**

Terminal49 shipping lines 页面显示覆盖 98%+ global container volume，支持 container / B/L / booking 查询，并列出 CMA、COSCO、Evergreen、Hapag、HMM、Maersk、MSC、ONE、OOCL、SeaLead、SM Line、Wan Hai、Yang Ming、ZIM 等。其 API data sources 页面更谨慎地标注 HMM 为 Partial，且 “No container numbers”；KMTC 未在公开支持列表中找到。

**风险点：**

- 单价 10 美元/container 对大批量可能很贵。
- 北美进口链路优势明显；如果你们不是北美为主，需要实测亚洲/欧洲链路质量。
- HMM 柜号查询能力需要重点验证。

**技术问题：**

- 如果选择 Terminal49，建议先用免费档/试用创建少量 tracking request。
- 程序上应支持异步任务模型：创建 tracking request 后再轮询/接 webhook。

### 3. Vizion

**可行性：高。**

Vizion 文档成熟，支持 container tracking、webhooks、auto-carrier identification、DCSA event/location codes。价格没有公开金额，但公开了 Core 与 Professional 的功能差异。

**覆盖：高。**

Vizion supported carriers 页面显示支持 98% global ocean shipments。你列出的船司中，APL、CMA、COSCO、Evergreen、Hapag-Lloyd、HMM、KMTC、Maersk、MSC、ONE、OOCL、Sea-Lead、SM Line、Wan Hai、Yang Ming、ZIM 均在表内。注意：

- Sea-Lead：支持，但 booking 不支持。
- SM Line：支持，booking 为 coming soon。
- Wan Hai：有备注，开船后 120 天以上 B/L 或 booking 数据可能不可用。

**风险点：**

- 价格需询价。
- 部分小船司或 booking 查询能力有限。
- Professional 才有 Container Trace，即包含经纬度、速度、航向等更细 AIS/船位能力。

**技术问题：**

- 最适合做标准化 API 接入。
- 可以先只用 container tracking，不启用 Professional 的 Container Trace。
- 若你只输入柜号，Vizion 的 auto-carrier identification 可能减少船司字段清洗成本。

### 4. SeaVantage

**可行性：中高。**

SeaVantage pricing 页面有 Free Trial、Starter、Business、Professional。Free Trial 为 5 containers/月；Starter/Business 为小批量控制台方案；Professional 明确写 100+ containers、API + Screen Embedding、Contact Sales。

**覆盖：中高。**

SeaVantage 宣称覆盖 all major carriers / 50+ carriers，Cargo Insight 页面展示 REST API、2 小时刷新、Core API 和 Extended API。页面示例覆盖 MSCU、MAEU、HLCU、CMAL、ONEY 等主流船司，但没有看到完整公开矩阵。

**风险点：**

- API 不在低价档，需 Professional 询价。
- 完整船司矩阵不公开，需要用你的船司列表问销售确认。
- 如只要节点+ETA，Extended API 可能过重。

**技术问题：**

- Core API 已足够验证 shipment data、vessel/voyage、ATD/ATA/ETA/PTA、container milestones。
- Extended API 才有 AIS vessel position、历史轨迹、速度航向。

### 5. GoComet

**可行性：中。**

GoComet 有 Container Tracking API 页面，说明可实时 tracking、data integration、customizable alerts，但 pricing plans 需要联系销售。

**覆盖：中。**

公开页面宣称支持 hundreds of global carriers，但没有找到逐船司矩阵。

**风险点：**

- 价格不透明。
- 不清楚是否适合纯 API 小工具，还是更偏平台订阅。
- 需要用你的实际船司列表向销售确认。

### 6. project44

**可行性：中，偏企业级。**

project44 Ocean Visibility 文档说明其通过 direct carrier integrations、EDI、AIS、port event monitoring 提供端到端可视化，并支持 container number、booking number、BOL reference 等最小输入。

**覆盖：高但需询价确认。**

project44 页面宣称覆盖 98%+ global ocean freight、700+ ports、5000+ vessels，但未找到公开逐船司矩阵。

**风险点：**

- 价格通常需要销售流程。
- 集成和商务周期可能偏长。
- 对当前“先看 API 原始返回”的目标过重。

### 7. FourKites

**可行性：中低，偏企业级。**

FourKites Dynamic Ocean 更像完整平台，覆盖实时 tracking、自动文档、D&D、异常管理、协同等。

**风险点：**

- 价格需询价。
- 不适合第一版轻量 API 探测。
- 接入重，销售周期长。

### 8. MarineTraffic / Kpler Containers API

**可行性：中。**

MarineTraffic Containers API 文档显示需要联系 Kpler sales 获取 access/API key，API header 为 `X-Container-API-Key`，并有 500 requests/min rate limit。

**定位：**

更适合作为 AIS/船位增强，而不是替代所有柜号追踪。它可以补“船现在的经纬度”，但前提仍然是能把柜号关联到船名/IMO/MMSI。

### 9. JSONCargo

**可行性：中。**

JSONCargo 公开价格较友好，页面显示 99/199/349 欧元每月级别，包含 Container tracking API、B/L API、Vessel tracking API 等；另有按 request 计价。

**风险点：**

- 品牌和企业级背书弱于 Vizion/project44/Terminal49。
- 对你列出的区域性船司需要逐个实测。
- 适合低成本实验，不建议直接作为最终唯一数据源。

## 船司覆盖矩阵

| 船司 | ShipsGo | Terminal49 | Vizion | SeaVantage | 备注 |
|---|---|---|---|---|---|
| APL | 支持 | 支持 | 支持 | 未逐项公开 | APL 常归 CMA CGM brand |
| CMA CGM | 支持 | 支持 | 支持 | 主流支持 | 重点试点 |
| COSCO | 支持 | 支持 | 支持 | 主流支持 | 重点关注中文船司名归一化 |
| Evergreen | 支持 | 支持 | 支持 | 主流支持 |  |
| HMM | 支持 | 公开页支持，但 API data source 标 Partial | 支持 | 未逐项公开 | Terminal49 需重点验证 container number |
| Hapag-Lloyd | 支持 | 支持 | 支持 | 主流支持 |  |
| KMTC | 支持 | 未找到 | 支持 | 未逐项公开 | Terminal49 风险较高 |
| MSC | 支持 | 支持 | 支持 | 主流支持 | 重点试点 |
| Maersk | 支持 | 支持 | 支持 | 主流支持 | 重点试点 |
| ONE | 支持 | 支持 | 支持 | 主流支持 |  |
| OOCL | 支持 | 支持 | 支持 | 未逐项公开 |  |
| SeaLead | 支持 | 支持 | 支持，但 booking 不支持 | 未逐项公开 | 柜号查询需实测 |
| SM Line | 支持 | 支持 | 支持，booking coming soon | 未逐项公开 | 柜号查询需实测 |
| Wan Hai | 支持 | 支持 | 支持，有 120 天数据备注 | 未逐项公开 |  |
| Yang Ming | 支持 | 支持 | 支持 | 未逐项公开 |  |
| ZIM | 支持 | 支持 | 支持 | 未逐项公开 |  |

## 推荐验证方案

### 方案 A：低成本快速验证

优先选 **ShipsGo**。

步骤：

1. 注册 ShipsGo。
2. 用 3 个免费 credit 测 Maersk、CMA、MSC 各 1 个柜号。
3. 如果返回字段足够，再购买最小 credit 包。
4. 在现有项目里新增 `ShipsGoProvider`。

适合原因：

- 价格公开。
- 覆盖你列出的船司较完整。
- 不需要复杂企业销售流程。

主要风险：

- 异步 tracking 模型可能不是一次请求立即返回完整事件。
- 重复查询和刷新是否扣费需确认。

### 方案 B：API 能力和覆盖优先

优先选 **Vizion**。

步骤：

1. 联系 Vizion 要试用 key。
2. 要求确认你列出的 15 家船司均可按 container number 查询。
3. 用你库里真实柜号跑一批样本。
4. 若字段完整，再接入 webhooks。

适合原因：

- 文档成熟。
- 船司覆盖表公开且详细。
- 对 container、MBL、booking、auto-carrier identification 支持清楚。

主要风险：

- 价格不公开。
- 部分船司 booking 能力有限，但你当前输入是柜号，影响较小。

### 方案 C：北美进口链路优先

优先选 **Terminal49**。

步骤：

1. 开免费档或试用。
2. 先测 HMM、KMTC、SeaLead、SM Line 这些容易有覆盖差异的船司。
3. 如果北美港口、terminal、rail、LFD 重要，再考虑 Pay As You Go。

适合原因：

- 价格公开。
- API、webhooks、terminal、rail、AIS 能力完整。

主要风险：

- 10 美元/container 成本较高。
- HMM/KMTC 覆盖需验证。

### 方案 D：平台级可视化

候选：project44、FourKites、SeaVantage Professional。

适合：

- 你们要的不只是 API 原始返回，而是完整供应链可视化。
- 需要 D&D、terminal、rail、预测 ETA、异常管理、协同、BI。

不适合当前第一版：

- 销售周期长。
- 成本不透明。
- 接入比当前目标重。

## 技术接入建议

当前项目已经有 Provider 结构，下一步建议新增一个第三方 Provider，而不是推翻现有代码。

建议接口：

```text
python -m trace_api_probe --carrier MAERSK --provider shipsgo
python -m trace_api_probe --carrier CMA_CGM --provider vizion
python -m trace_api_probe --carrier MSC --provider terminal49
```

新增环境变量：

```text
SHIPSGO_API_KEY
VIZION_API_KEY
TERMINAL49_API_KEY
SEAVANTAGE_API_KEY
```

Provider 行为：

1. 从只读库取 `shipping_company + cabinet_no`。
2. 船司名归一化。
3. 调第三方 API。
4. 打印原始 JSON。
5. 不写库、不保存文件。

## 风险清单

| 风险 | 影响 | 缓解方式 |
|---|---|---|
| 第三方覆盖页面写支持，但真实柜号查不到 | 数据缺口 | 每家船司至少取 3-5 个真实柜号试跑 |
| 柜号需要搭配船司/SCAC 才能查 | 查询失败 | 保留船司归一化和 carrier code 映射 |
| API 是异步创建 tracking，不是同步返回事件 | 第一版看不到完整返回 | CLI 支持 create 后轮询一次 status |
| 重复 tracking 扣费 | 成本失控 | 先记录请求 ID；同柜号复用第三方 tracking reference |
| BCO/NVO 导致第三方拿不到完整状态 | 数据不完整 | 同时准备 B/L 或 booking 作为备用输入 |
| 小船司覆盖不稳定 | 状态缺失 | 优先测 KMTC、SeaLead、SM Line、Wan Hai |
| 价格页只适用于 dashboard，不适用于 API | 预算误判 | 报价时明确问 API、webhook、批量查询是否包含 |

## 采购/试用时要问的问题

发给供应商时建议直接问：

```text
We need to track our own ocean containers by container number.

Please confirm:
1. Do you support API tracking by container number?
2. Do you support these carriers: APL/CMA CGM, COSCO, Evergreen, HMM, Hapag-Lloyd, KMTC, MSC, Maersk, ONE, OOCL, SeaLead, SM Line, Wan Hai, Yang Ming, ZIM?
3. Is the API synchronous or asynchronous?
4. Do repeated refreshes of the same container consume additional credits?
5. Do you return raw carrier events, normalized events, or both?
6. Do you return vessel name, voyage, ETA, POL/POD, event location, and event time?
7. Do you support webhook updates?
8. What is the smallest paid plan or trial for API testing?
9. Are dashboard plans separate from API plans?
10. Can we test with 10 real container numbers before purchasing?
```

## 我的建议

短期最稳：

1. **先试 ShipsGo**：成本和覆盖最容易验证。
2. **并行问 Vizion**：覆盖矩阵最清楚，适合正式 API。
3. **如果你们北美进口占比高，再试 Terminal49**。
4. 暂不优先 project44/FourKites，除非你们决定做平台级供应链可视化。

如果只选一个先接入当前代码，我建议从 **ShipsGoProvider** 开始。

## 资料来源

- ShipsGo Pricing：https://shipsgo.com/pricing
- ShipsGo Carriers：https://shipsgo.com/ocean/carriers
- ShipsGo API Docs：https://api.shipsgo.com/docs/v2/
- Terminal49 Pricing：https://terminal49.com/pricing
- Terminal49 Shipping Lines：https://terminal49.com/shipping-lines
- Terminal49 API Data Sources：https://terminal49.com/docs/api-docs/useful-info/api-data-sources-availability
- Vizion Supported Carriers：https://docs.vizionapi.com/docs/supported-carriers
- Vizion Pricing Plans：https://docs.vizionapi.com/docs/plans
- SeaVantage Pricing：https://www.seavantage.com/pricing
- SeaVantage Cargo Insight：https://www.seavantage.com/cargo-insight
- GoComet Container Tracking API：https://www.gocomet.com/container-tracking-api
- project44 Ocean Visibility：https://developers.project44.com/guides/shippers/visibility/ocean/p2p/overview
- MarineTraffic Containers API：https://container-tracking.marinetraffic.com/v2/
- SeaRates Tracking Pricing：https://www.searates.com/pricing/tracking-system
- JSONCargo Pricing：https://jsoncargo.com/pricing-plans/
