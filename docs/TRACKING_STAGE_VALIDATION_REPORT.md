# 船司运输阶段样本验证报告

验证日期：2026-07-14

## 目的与口径

本轮从公司只读库按更新时间选取不同时间切片的柜号，再以船司官网当前返回的实际状态判断运输阶段。数据库记录只用于发现候选柜号，不用订单时间直接推断运输阶段。

报告不保存完整柜号、原始 HTML、Cookie 或完整业务单号，只记录脱敏样本编号、状态摘要、字段覆盖和失败类型。完整原始返回只在查询进程内用于解析验证。

阶段定义：

- 发船前：提空箱、重箱进场、出口堆场接收等尚未离开始发港的状态。
- 在途：已装船、离开始发港、转运港装卸或转运港离港。
- 已到目的地：目的港卸船、提柜、还空箱或明确交付完成。

## 阶段覆盖结果

| 船司 | 发船前 | 在途 | 已到目的地 | 有效样本结果 | 主要字段覆盖 |
| --- | --- | --- | --- | --- | --- |
| 马士基 | `GATE-OUT` | `CONTAINER DEPARTURE` | `CONTAINER RETURN` | 3/3 成功 | current、next_expected、起讫地、ETA、船名航次、事件 |
| HMM | `Export Truck Gate In to Terminal` | `Vessel Departure from T/S Port` | `Import Empty Container Returned` | 6/6 成功 | current、起讫地、ETA、船名航次、完整历史事件 |
| ONE | `Gate In to Outbound Terminal` | `Departure from Transshipment Port` | `Empty Container Returned from Customer` | 5/5 成功 | current、next_expected、船名航次、事件；无统一 ETA |
| COSCO | `重箱进场` | `离开始发港` | `还空箱` | 4/4 成功 | current、运输方式、最新事件；当前页面仅返回有限事件字段 |
| 阳明 | `Received at Origin` | `Departure by Vessel at Port terminal` | `Empty Returned` | 3/3 成功 | current、next_expected、船名航次、ETA、DCSA 事件 |
| MSC | `Export received at CY` | `Full Transshipment Loaded` | `Empty received at CY` | 5/6 成功 | current、next_expected、起讫地、ETA、船名航次、IMO、事件 |
| 长荣 | 未找到有效样本 | `Loaded (FCL) on vessel` / `Transship container loaded on vessel` | `Discharged (FCL)` / `Empty container returned` | 6/6 成功 | 官网只返回单条最新状态、地点及部分船舶列 |
| 万海 | 未找到有效样本 | 未找到有效样本 | 目的港卸船、提柜、空箱可用 | 4/5 成功 | current、场站；Booking 摘要可补船名航次，无完整历史事件和 ETA |
| SM Line | `Gate In to Outbound Terminal` | 数据库无样本 | 数据库无样本 | 1/1 成功，使用 2 次尝试 | current、next_expected、起讫地、ETA、船名航次、事件 |

`有效样本结果` 只统计最终用于阶段或结构验证的样本，不代表全量生产成功率。MSC 的失败样本为官网明确返回 `No results found`；万海的失败样本为历史柜号未出现结果表。这两类失败均被单柜隔离，后续查询继续执行。

## 各船司观察

### 马士基

- 三个阶段均能稳定返回官网 JSON，全部一次成功。
- 发船前样本包含实际 `GATE-OUT` 和未来预计离港、到港节点。
- 在途样本包含多港口、多船舶和实际/预计事件。
- 完成样本以 `CONTAINER RETURN` 结束，不再输出过期的 `next_expected`。
- 单条耗时约 20 至 25 秒，主要成本是启动浏览器并等待官网 JSON。

### HMM

- 三个阶段均可通过有界 Chromium 获取 HTML 表格。
- 页面保持 8 至 9 张核心业务表，事件数量随阶段从 2 条增加到 9 至 11 条。
- HMM 事件表只表达已发生轨迹；未来计划通过航段表和 ETA 表达，因此 `next_expected` 通常为空。
- 查询本身约 3 至 13 秒；同船司连续查询会遵守 12 秒最小间隔。
- 历史柜号可能已经被新一票运输复用，数据库旧记录时间不能证明官网当前结果属于原订单。

### ONE

- 页面通过颜色图标区分 Actual 与 Estimated：蓝色 A 为实际，粉色 E 为预计。
- 地点、码头和船名只在部分行展示，后续行需要继承同一阶段上下文。
- 修正后可以稳定得到当前实际状态和下一预计节点。
- 单条约 7 至 8 秒，三个阶段均有有效样本。

### COSCO

- 当前页面样本通常只提供一条最新动态，无法重建完整时间线。
- DOM 文本会用制表符把地点与运输方式连接，解析器现已拆分。
- 三阶段均能识别，但船名航次和 ETA 覆盖不足。

### 阳明

- `dcsaStatusInfo` 比旧 `ctStatusInfo` 语义更完整，提供 `Actual/Estimated` 分类。
- `tsMode` 使用 `<BR />` 拼接运输方式、船名和航次，现已结构化拆分。
- 查询速度快，三个阶段均有有效样本。

### MSC

- JSON 同时包含实际事件、预计离港/到港、起讫地、船名航次和 IMO。
- 一个历史柜号官网明确无结果，程序不重试确定性的无数据响应。
- 完成样本仍可能保留早于当前状态的预计事件；现已过滤，不再错误显示为下一节点。

### 长荣

- 官网只返回一条最新状态，而不是完整事件列表。
- 当前数据库候选中覆盖装船、转运装船、卸船和还空箱，未找到发船前样本。
- `Method` 样本值为数字代码，含义尚未确认，测试数据中应保留原值而不猜测。

### 万海

- 当前列表只返回最新状态；Booking 摘要可补船名和航次。
- 可验证目的港卸船、提柜和空箱可用状态，未找到发船前及明确在途样本。
- 历史柜号可能不再返回结果表，属于确定性单柜失败。

### SM Line

- 数据库历史窗口内只有一个去重柜号，目前处于发船前阶段。
- 原始 JSON 能区分实际与预计事件，并提供完整计划时间线。
- 本轮第一次请求出现可恢复错误，第二次成功，验证了有限重试机制。

## 本轮发现并修复的问题

1. 数据库中存在 `WANHAI 万海` 写法，原 SQL 别名未覆盖，导致按船司查询返回 0。
2. 柜号可能包含内部空格，例如 `EGHU 9204414`；现统一删除所有空白后查询。
3. ONE 原抓取器丢失 Actual/Estimated 图标语义，并且未继承地点、码头和船名上下文。
4. COSCO DOM 使用制表符连接地点和运输方式，原解析会把两者合并。
5. 阳明旧映射未使用 DCSA Actual/Estimated 数据，且船名航次保留 HTML 换行标签。
6. 已完成运输可能保留过期预计节点；现在只有晚于当前实际事件的预计节点才进入 `next_expected`。

## 建议测试夹具

后续测试数据应从本报告对应结构脱敏构造，不复制生产柜号或完整原始 HTML：

- `maersk_pre_departure.json`：实际进场 + 多条未来预计事件。
- `maersk_completed.json`：最后实际事件为还空箱，包含过期预计事件。
- `hmm_pre_departure_tables.json`：航线、柜摘要、航段和两条陆运事件。
- `hmm_transshipment_tables.json`：两段船舶航程和多条转运事件。
- `hmm_completed_tables.json`：目的港提柜及还空箱事件。
- `one_actual_expected_rows.json`：A/E 元数据、地点继承、船名继承和目的地两列表格变体。
- `yang_ming_dcsa.json`：Actual/Estimated DCSA 事件及 `<BR />` 船舶字段。
- `msc_completed_with_stale_estimate.json`：完成事件晚于预计节点。
- `evergreen_latest_status_rows.json`：装船、卸船和还空箱单行变体。
- `wan_hai_latest_and_booking_summary.json`：最新状态 + Booking 船名航次摘要。
- `sm_line_actual_expected.json`：`actTpCd=A/E` 混合时间线。

测试夹具只保留字段结构和经过替换的业务文本；柜号、提单号、订舱号、封条号、场站内部编码等应使用虚构值。
