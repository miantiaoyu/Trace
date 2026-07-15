# 头程追踪表设计草案

本文只描述数据模型和查询流程，不包含建表 SQL，也不改变当前程序的只读行为。表名 `trace_first_leg` 只是暂定名，最终以业务库命名规范为准。

## 设计目标

- 以 ERP 中的一条来源记录为一个追踪对象，而不是只以柜号作为主键。
- 保存船司本次成功查询得到的最新原始 JSON。
- 将业务最关心的字段提升为可直接筛选、排序和统计的列。
- 能区分新订单、尚未到达最终目的地的待追踪记录和已完成记录。
- 官网查询失败或解析失败时保留上一份有效业务快照，不用错误结果覆盖好数据。

## 记录粒度和身份

建议一行代表一条 ERP 来源记录的“当前追踪快照”。当前代码从 `trobs.po_cabinet_combination` 使用的来源字段是：

| 业务含义 | 来源字段 | 目标字段建议 |
| --- | --- | --- |
| ERP 记录身份 | `id` | `erp_record_id` |
| 船司原始值 | `shipping_company` | `erp_shipping_company` |
| 规范化船司 | 查询归一化结果 | `carrier_code` |
| 柜号 | `cabinet_no` | `container_no` |
| ERP 更新时间 | `update_time` | `erp_update_time` |
| ERP 创建时间 | `create_time` | `erp_create_time` |

建议唯一约束使用 `(environment, erp_record_id, container_no)`。柜号可能被后续运输重复使用，不能把 `container_no` 单独作为唯一业务键。若 ERP 中存在比当前 `id` 更稳定的订单/订舱主键，应优先替换 `erp_record_id`。

## 建议字段

### 标识和来源

| 字段 | 类型方向 | 说明 |
| --- | --- | --- |
| `id` | BIGINT 主键 | 头程追踪表自身主键 |
| `environment` | VARCHAR | `test` 或 `prod`，防止环境数据混用 |
| `erp_record_id` | BIGINT | ERP 来源记录 ID |
| `erp_shipping_company` | VARCHAR | ERP 原始船司值，便于回溯 |
| `carrier_code` | VARCHAR | 统一船司代码，例如 `HMM`、`MAERSK` |
| `container_no` | VARCHAR | 清理空白并大写后的柜号 |
| `erp_update_time` | DATETIME | ERP 来源记录更新时间 |
| `erp_create_time` | DATETIME | ERP 来源记录创建时间 |

### 统一业务快照

| 字段 | 类型方向 | 说明 |
| --- | --- | --- |
| `departure_time` | DATETIME | 出发时间；优先保存明确的实际出发事件 |
| `departure_time_type` | VARCHAR | `ACTUAL`、`EXPECTED` 或空；不能把预计时间伪装成实际时间 |
| `origin_location` | VARCHAR | 起始地点/起运港 |
| `destination_location` | VARCHAR | 最终目的地/目的港 |
| `destination_eta` | DATETIME | 最终目的地预计到达时间 |
| `current_event_time` | DATETIME | 当前状态对应的事件时间 |
| `current_status` | VARCHAR | 当前运输状态 |
| `current_location` | VARCHAR | 当前地点、码头或场站 |
| `current_mode` | VARCHAR | `Vessel`、`Truck`、`Rail` 等 |
| `vessel_name` | VARCHAR | 当前或下一相关船名 |
| `voyage` | VARCHAR | 当前或下一相关航次 |
| `imo` | VARCHAR | IMO 船舶编号，来源没有时为空 |
| `is_arrived_destination` | TINYINT(1) | 是否已明确到达最终目的地，核心筛选字段 |
| `destination_arrived_at` | DATETIME | 明确到达/提柜/还空箱等实际事件时间 |
| `destination_arrival_evidence` | VARCHAR | 判定依据，例如官网状态文本或事件名称 |

`is_arrived_destination` 只有在来源返回明确的实际证据时才置为 `1`，例如目的港卸船、提柜、还空箱或明确交付完成。只有 ETA、目的地字段或预计事件时必须保持 `0`。

### 查询状态和原始数据

| 字段 | 类型方向 | 说明 |
| --- | --- | --- |
| `query_status` | VARCHAR | `success`、`partial_success`、`query_failed`、`route_unavailable` 等 |
| `query_route` | VARCHAR | 实际使用的船司路线 |
| `last_queried_at` | DATETIME | 最近一次尝试时间 |
| `last_success_at` | DATETIME | 最近一次取得官网原始数据的时间 |
| `next_query_at` | DATETIME | 下一次允许/计划查询时间，支持限速和失败退避 |
| `last_attempts` | INT | 最近一次查询尝试次数 |
| `last_error_type` | VARCHAR | 最近一次失败类型 |
| `last_error_message` | VARCHAR/TEXT | 脱敏后的失败信息，不保存密码、Cookie 或完整响应 |
| `raw_response_json` | JSON | 最近一次成功取得的船司原始 JSON |
| `normalized_schema_version` | VARCHAR | 统一摘要契约版本，例如 `1.1` |
| `coverage_json` | JSON | 当前摘要覆盖情况，例如是否有 ETA、船舶、当前位置 |
| `created_at` | DATETIME | 头程记录首次创建时间 |
| `updated_at` | DATETIME | 头程记录最后更新时间 |

`raw_response_json` 保存最新成功原始返回；`query_failed` 不应清空上一份有效原始数据和业务快照。若需要保留每一次查询的历史原始 JSON，应另建“查询历史表”，不要把一列不断追加成数组。

## 查询流程

每轮任务建议分两组取数：

1. **新订单**：ERP 来源记录在头程表中不存在。
2. **未到达待追踪**：头程表已存在，`is_arrived_destination = 0`，并且 `next_query_at` 为空或已到期。

已到达记录默认不再重复查询。任务应允许人工或特殊参数强制重查，但不能让普通定时任务因为 ERP 更新时间变化而无限重复已完成记录。

查询成功后更新统一字段、`raw_response_json`、状态和时间；查询失败只更新失败元数据和下次重试时间；原始数据已取得但归一化失败时保存原始 JSON，统一字段保留上一份有效值并标记 `partial_success`。

## 索引建议

- 唯一索引：`environment + erp_record_id + container_no`
- 待追踪索引：`environment + is_arrived_destination + next_query_at`
- 船司批量索引：`environment + carrier_code + is_arrived_destination`
- 柜号查询索引：`environment + container_no`
- 运维查询索引：`environment + query_status + last_queried_at`

## 需要你确认的事项

1. ERP 的 `id` 是否能稳定代表一条订单/柜号业务记录？如果不能，需要提供订单号或订舱号作为业务键。
2. `departure_time` 是否只接受实际出发时间，还是允许在没有实际事件时暂存预计出发时间？
3. `raw_response_json` 只保留最新一次，还是需要完整查询历史？完整历史需要第二张表。
4. `destination_location` 是目的港，还是最终交付地点/仓库？两者可能不同。
5. 结果表是否和 ERP 同在 `oms` 库，还是放到单独的追踪库/ schema？
6. 是否允许为结果表创建专用写账号，而不是使用 ERP 查询账号？

在以上事项确认前，不生成 SQL，也不修改当前只读查询流程。
